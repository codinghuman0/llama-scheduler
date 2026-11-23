/* SPDX-License-Identifier: GPL-2.0 */
/*
 * Derived from Linux v6.17 tools/sched_ext/scx_simple.c lifecycle.
 * Direct loading and one-shot registration use narrow golden control-plane mechanisms.
 *
 * Copyright (c) 2022 Meta Platforms, Inc. and affiliates.
 * Copyright (c) 2022 Tejun Heo <tj@kernel.org>
 * Copyright (c) 2022 David Vernet <dvernet@meta.com>
 */
#define _GNU_SOURCE
#include <elf.h>
#include <errno.h>
#include <fcntl.h>
#include <getopt.h>
#include <limits.h>
#include <poll.h>
#include <sched.h>
#include <signal.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/signalfd.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/sysmacros.h>
#include <sys/time.h>
#include <sys/un.h>
#include <unistd.h>
#include <bpf/libbpf.h>
#include "llama_sched_uapi.h"
#include "llama_scx_state.h"

#ifndef BPF_OBJECT_PATH
#define BPF_OBJECT_PATH "build/llama_scx.bpf.o"
#endif
#define REGISTER_MAX 128
#define LIFECYCLE_POLL_MS 1000
#define TARGET_STOP_MS 5000

static bool verbose;

static int libbpf_print_fn(enum libbpf_print_level level, const char *format, va_list args)
{
	if (level == LIBBPF_DEBUG && !verbose)
		return 0;
	return vfprintf(stderr, format, args);
}

static void usage(const char *program)
{
	fprintf(stderr,
		"Usage: %s --phase-uid UID --phase-register-socket NAME\n"
		"          --server-exe ELF --marker-elf ELF [-v]\n"
		"  UID must be a normal user; the loader runs as root with SCHED_NORMAL.\n"
		"  The marker ELF must contain llama_scx_phase_v1; it may be a shared library.\n"
		"  -v  show libbpf debug messages\n"
		"  -h  show this help\n", program);
}

static int parse_number(const char *text, unsigned long maximum, unsigned long *value)
{
	char *end;

	if (!text[0])
		return -EINVAL;
	for (const char *p = text; *p; p++)
		if (*p < '0' || *p > '9')
			return -EINVAL;
	errno = 0;
	*value = strtoul(text, &end, 10);
	if (errno || *end || !*value || *value > maximum)
		return -EINVAL;
	return 0;
}

static int open_elf(const char *path, bool executable, struct stat *identity)
{
	Elf64_Ehdr header;
	int fd = open(path, O_RDONLY | O_CLOEXEC);
	int error;
	ssize_t length;

	if (fd < 0)
		return -errno;
	if (fstat(fd, identity)) {
		error = -errno;
		goto fail;
	}
	if (!S_ISREG(identity->st_mode) ||
	    (executable && !(identity->st_mode & (S_IXUSR | S_IXGRP | S_IXOTH)))) {
		error = -EACCES;
		goto fail;
	}
	length = pread(fd, &header, sizeof(header), 0);
	if (length != sizeof(header)) {
		error = length < 0 ? -errno : -ENOEXEC;
		goto fail;
	}
	if (memcmp(header.e_ident, ELFMAG, SELFMAG) ||
	    header.e_ident[EI_CLASS] != ELFCLASS64 || header.e_ident[EI_DATA] != ELFDATA2LSB ||
	    header.e_machine != EM_X86_64 || (header.e_type != ET_EXEC && header.e_type != ET_DYN)) {
		error = -ENOEXEC;
		goto fail;
	}
	return fd;
fail:
	close(fd);
	return error;
}

static int open_registration_socket(const char *name)
{
	struct sockaddr_un address = { .sun_family = AF_UNIX };
	const char *abstract_name = name[0] == '@' ? name + 1 : name;
	size_t length = strlen(abstract_name);
	socklen_t address_length;
	int fd;
	int error;

	if (!length || length > sizeof(address.sun_path) - 1)
		return -EINVAL;
	fd = socket(AF_UNIX, SOCK_SEQPACKET | SOCK_CLOEXEC | SOCK_NONBLOCK, 0);
	if (fd < 0)
		return -errno;
	memcpy(address.sun_path + 1, abstract_name, length);
	address_length = (socklen_t)(__builtin_offsetof(struct sockaddr_un, sun_path) + 1 + length);
	if (bind(fd, (struct sockaddr *)&address, address_length) || listen(fd, 1)) {
		error = -errno;
		close(fd);
		return error;
	}
	return fd;
}

static int parse_registration(const char *message, size_t length, pid_t *tgid)
{
	const char prefix[] = "REGISTER 1 ";
	char text[REGISTER_MAX];
	unsigned long value;

	if (length >= sizeof(text) || length <= sizeof(prefix) - 1 ||
	    memchr(message, '\0', length) || memcmp(message, prefix, sizeof(prefix) - 1))
		return -EPROTO;
	memcpy(text, message, length);
	text[length] = '\0';
	if (parse_number(text + sizeof(prefix) - 1, INT_MAX, &value))
		return -EPROTO;
	*tgid = (pid_t)value;
	return 0;
}

static int target_alive(int pidfd, int wait_ms)
{
	struct pollfd target = { .fd = pidfd, .events = POLLIN };
	int result = poll(&target, 1, wait_ms);

	if (result < 0)
		return -errno;
	if (target.revents & (POLLIN | POLLHUP))
		return 0;
	if (target.revents & (POLLERR | POLLNVAL))
		return -EIO;
	return 1;
}

static int validate_target(pid_t tgid, const struct ucred *peer, uid_t uid,
			   const struct stat *server_identity)
{
	char path[64];
	char line[256];
	unsigned int pid = 0, leader = 0, parent = 0;
	unsigned int ids[4] = { UINT_MAX, UINT_MAX, UINT_MAX, UINT_MAX };
	struct stat executable;
	FILE *status;
	int error;
	int policy;

	snprintf(path, sizeof(path), "/proc/%d/status", tgid);
	status = fopen(path, "re");
	if (!status)
		return -errno;
	while (fgets(line, sizeof(line), status)) {
		if (sscanf(line, "Pid:%u", &pid) == 1 ||
		    sscanf(line, "Tgid:%u", &leader) == 1 ||
		    sscanf(line, "PPid:%u", &parent) == 1)
			continue;
		if (!strncmp(line, "Uid:", 4) &&
		    sscanf(line, "Uid:%u%u%u%u", &ids[0], &ids[1], &ids[2], &ids[3]) != 4) {
			fclose(status);
			return -EPROTO;
		}
	}
	error = ferror(status) ? -EIO : 0;
	fclose(status);
	if (error)
		return error;
	if (pid != (unsigned int)tgid || leader != pid || parent != (unsigned int)peer->pid)
		return -EPERM;
	for (unsigned int i = 0; i < 4; i++)
		if (ids[i] != uid)
			return -EACCES;
	policy = sched_getscheduler(tgid);
	if (policy != SCHED_EXT)
		return policy < 0 ? -errno : -EPERM;
	snprintf(path, sizeof(path), "/proc/%d/exe", tgid);
	if (stat(path, &executable))
		return -errno;
	if (executable.st_dev != server_identity->st_dev || executable.st_ino != server_identity->st_ino)
		return -ENOEXEC;
	return 0;
}

static int marker_is_mapped(pid_t tgid, const struct stat *marker_identity)
{
	char path[64];
	char *line = NULL;
	size_t capacity = 0;
	FILE *maps;
	int result = 0;

	snprintf(path, sizeof(path), "/proc/%d/maps", tgid);
	maps = fopen(path, "re");
	if (!maps)
		return -errno;
	while (getline(&line, &capacity, maps) >= 0) {
		unsigned long start, end, offset;
		unsigned long long inode;
		unsigned int device_major, device_minor;
		char permissions[5];

		if (sscanf(line, "%lx-%lx %4s %lx %x:%x %llu", &start, &end, permissions,
			   &offset, &device_major, &device_minor, &inode) == 7 &&
		    device_major == major(marker_identity->st_dev) &&
		    device_minor == minor(marker_identity->st_dev) &&
		    inode == marker_identity->st_ino && permissions[2] == 'x') {
			result = 1;
			break;
		}
	}
	if (ferror(maps))
		result = -EIO;
	free(line);
	fclose(maps);
	return result;
}

static int send_ack(int fd, pid_t tgid, int status)
{
	char response[REGISTER_MAX];
	int length = snprintf(response, sizeof(response), "ACK 1 %d %d", tgid, status);
	ssize_t sent;

	if (length < 0 || length >= (int)sizeof(response))
		return -EMSGSIZE;
	sent = send(fd, response, (size_t)length, MSG_NOSIGNAL);
	return sent == length ? 0 : sent < 0 ? -errno : -EIO;
}

static int register_child(int client, uid_t uid, const struct stat *server_identity,
			  const struct stat *marker_identity, const char *marker_path,
			  struct bpf_program *phase_program,
			  volatile struct llama_scx_control_state *state,
			  struct bpf_link **phase_link, int *target_pidfd)
{
	LIBBPF_OPTS(bpf_uprobe_opts, options, .func_name = "llama_scx_phase_v1", .retprobe = false);
	struct timeval timeout = { .tv_sec = 1 };
	struct ucred peer;
	socklen_t peer_length = sizeof(peer);
	struct bpf_link *link = NULL;
	char request[REGISTER_MAX];
	pid_t tgid = 0;
	int pidfd = -1;
	int error;
	int alive;
	int policy;
	ssize_t length;
	bool initialized = false;

	if (setsockopt(client, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)) ||
	    setsockopt(client, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout))) {
		error = -errno;
		goto fail;
	}
	if (getsockopt(client, SOL_SOCKET, SO_PEERCRED, &peer, &peer_length) || peer_length != sizeof(peer)) {
		error = -EPERM;
		goto fail;
	}
	if (peer.uid != uid) {
		error = -EACCES;
		goto fail;
	}
	policy = sched_getscheduler(peer.pid);
	if (policy != SCHED_OTHER) {
		error = policy < 0 ? -errno : -EPERM;
		goto fail;
	}
	length = recv(client, request, sizeof(request), MSG_TRUNC);
	if (length <= 0 || length >= (ssize_t)sizeof(request)) {
		error = length < 0 ? -errno : -EMSGSIZE;
		goto fail;
	}
	error = parse_registration(request, (size_t)length, &tgid);
	if (error)
		goto fail;
	pidfd = syscall(SYS_pidfd_open, tgid, 0);
	if (pidfd < 0) {
		error = -errno;
		goto fail;
	}
	error = validate_target(tgid, &peer, uid, server_identity);
	if (error)
		goto fail;
	/* Exec can precede the dynamic linker's executable DSO mapping. Wait only at startup. */
	for (int attempt = 0; attempt < 100; attempt++) {
		error = marker_is_mapped(tgid, marker_identity);
		if (error)
			break;
		alive = target_alive(pidfd, 10);
		if (alive <= 0) {
			error = alive < 0 ? alive : -ESRCH;
			break;
		}
	}
	if (error != 1) {
		error = error < 0 ? error : -ENOENT;
		goto fail;
	}
	error = validate_target(tgid, &peer, uid, server_identity);
	if (error)
		goto fail;
	alive = target_alive(pidfd, 0);
	if (alive <= 0 || state->exit_kind) {
		error = alive < 0 ? alive : -ESRCH;
		goto fail;
	}
	state->current_phase = LLAMA_SCX_PHASE_UNKNOWN;
	state->selected_tgid = (__u32)tgid;
	initialized = true;
	link = bpf_program__attach_uprobe_opts(phase_program, tgid, marker_path, 0, &options);
	if (!link) {
		error = -(errno ?: EIO);
		goto fail;
	}
	alive = target_alive(pidfd, 0);
	if (alive <= 0 || state->exit_kind) {
		error = alive < 0 ? alive : -ESRCH;
		goto fail;
	}
	error = send_ack(client, tgid, 0);
	if (error)
		goto fail;
	*phase_link = link;
	*target_pidfd = pidfd;
	fprintf(stderr, "llama_scx: registered tgid=%d uid=%u\n", tgid, (unsigned int)uid);
	return 0;
fail:
	bpf_link__destroy(link);
	if (initialized) {
		state->selected_tgid = 0;
		state->current_phase = LLAMA_SCX_PHASE_UNKNOWN;
	}
	if (pidfd >= 0)
		close(pidfd);
	send_ack(client, tgid, error);
	return error;
}

static int stop_target(int pidfd)
{
	int alive = target_alive(pidfd, 0);

	if (alive <= 0)
		return alive;
	if (syscall(SYS_pidfd_send_signal, pidfd, SIGTERM, NULL, 0) && errno != ESRCH)
		return -errno;
	alive = target_alive(pidfd, TARGET_STOP_MS);
	if (alive <= 0)
		return alive;
	if (syscall(SYS_pidfd_send_signal, pidfd, SIGKILL, NULL, 0) && errno != ESRCH)
		return -errno;
	alive = target_alive(pidfd, TARGET_STOP_MS);
	return alive > 0 ? -ETIMEDOUT : alive;
}

int main(int argc, char **argv)
{
	enum { OPT_UID = 1000, OPT_SOCKET, OPT_SERVER, OPT_MARKER };
	static const struct option options[] = {
		{ "phase-uid", required_argument, NULL, OPT_UID },
		{ "phase-register-socket", required_argument, NULL, OPT_SOCKET },
		{ "server-exe", required_argument, NULL, OPT_SERVER },
		{ "marker-elf", required_argument, NULL, OPT_MARKER },
		{ "help", no_argument, NULL, 'h' },
		{ NULL, 0, NULL, 0 },
	};
	const char *socket_name = NULL, *server_path = NULL, *marker_path = NULL;
	struct bpf_object *object = NULL;
	struct bpf_map *data_map, *ops_map;
	struct bpf_program *phase_program;
	struct bpf_link *scheduler_link = NULL, *phase_link = NULL;
	volatile struct llama_scx_control_state *state = MAP_FAILED;
	struct stat server_identity, marker_identity;
	char marker_fd_path[64];
	sigset_t signals;
	uid_t uid = 0;
	int signal_fd = -1, listener = -1, pidfd = -1, server_fd = -1, marker_fd = -1;
	int error = 0, option, policy;
	long page_size = 0;

	while ((option = getopt_long(argc, argv, "vh", options, NULL)) != -1) {
		unsigned long value;

		switch (option) {
		case OPT_UID:
			if (parse_number(optarg, UINT_MAX - 1UL, &value) || (uid_t)value != value) {
				fprintf(stderr, "invalid non-root --phase-uid\n");
				return EXIT_FAILURE;
			}
			uid = (uid_t)value;
			break;
		case OPT_SOCKET: socket_name = optarg; break;
		case OPT_SERVER: server_path = optarg; break;
		case OPT_MARKER: marker_path = optarg; break;
		case 'v': verbose = true; break;
		default:
			usage(argv[0]);
			return option == 'h' ? EXIT_SUCCESS : EXIT_FAILURE;
		}
	}
	if (!uid || !socket_name || !server_path || !marker_path || optind != argc) {
		usage(argv[0]);
		return EXIT_FAILURE;
	}
	policy = sched_getscheduler(0);
	if (getuid() || geteuid() || policy != SCHED_OTHER) {
		fprintf(stderr, "loader requires root and SCHED_NORMAL\n");
		return EXIT_FAILURE;
	}
	libbpf_set_print(libbpf_print_fn);
	sigemptyset(&signals);
	sigaddset(&signals, SIGINT);
	sigaddset(&signals, SIGTERM);
	if (sigprocmask(SIG_BLOCK, &signals, NULL)) {
		error = -errno;
		goto out;
	}
	signal_fd = signalfd(-1, &signals, SFD_CLOEXEC | SFD_NONBLOCK);
	if (signal_fd < 0) {
		error = -errno;
		goto out;
	}
	server_fd = open_elf(server_path, true, &server_identity);
	marker_fd = open_elf(marker_path, false, &marker_identity);
	if (server_fd < 0 || marker_fd < 0) {
		error = server_fd < 0 ? server_fd : marker_fd;
		goto out;
	}
	/* Attach through the held marker fd so pathname replacement cannot change its inode. */
	snprintf(marker_fd_path, sizeof(marker_fd_path), "/proc/self/fd/%d", marker_fd);
	listener = open_registration_socket(socket_name);
	if (listener < 0) {
		error = listener;
		goto out;
	}
	object = bpf_object__open_file(BPF_OBJECT_PATH, NULL);
	if (!object) {
		error = -(errno ?: EIO);
		goto out;
	}
	data_map = bpf_object__find_map_by_name(object, ".data");
	ops_map = bpf_object__find_map_by_name(object, "llama_ops");
	phase_program = bpf_object__find_program_by_name(object, "llama_phase");
	if (!data_map || !ops_map || !phase_program ||
	    bpf_map__value_size(data_map) != sizeof(struct llama_scx_control_state) ||
	    !(bpf_map__map_flags(data_map) & BPF_F_MMAPABLE)) {
		error = -EINVAL;
		goto out;
	}
	error = bpf_object__load(object);
	if (error)
		goto out;
	page_size = sysconf(_SC_PAGESIZE);
	if (page_size <= 0) {
		error = -EINVAL;
		goto out;
	}
	state = mmap(NULL, (size_t)page_size, PROT_READ | PROT_WRITE, MAP_SHARED, bpf_map__fd(data_map), 0);
	if (state == MAP_FAILED) {
		error = -errno;
		goto out;
	}
	scheduler_link = bpf_map__attach_struct_ops(ops_map);
	if (!scheduler_link) {
		error = -(errno ?: EIO);
		goto out;
	}
	fprintf(stderr, "llama_scx: partial weighted-vtime scheduler active; waiting for selected child\n");
	for (;;) {
		struct pollfd fds[2] = {
			{ .fd = signal_fd, .events = POLLIN },
			{ .fd = pidfd >= 0 ? pidfd : listener, .events = POLLIN },
		};
		int result;

		/* Coarse terminal lifecycle check; never read phase or collect metrics. */
		if (state->exit_kind) {
			fprintf(stderr, "llama_scx: scheduler exited kind=%u\n", state->exit_kind);
			error = -ECANCELED;
			break;
		}
		result = poll(fds, 2, LIFECYCLE_POLL_MS);
		if (result < 0) {
			if (errno == EINTR)
				continue;
			error = -errno;
			break;
		}
		if ((fds[0].revents | fds[1].revents) & (POLLERR | POLLNVAL)) {
			error = -EIO;
			break;
		}
		if (fds[0].revents & POLLIN) {
			struct signalfd_siginfo info;

			if (read(signal_fd, &info, sizeof(info)) != sizeof(info))
				error = -(errno ?: EIO);
			break;
		}
		if (!(fds[1].revents & (POLLIN | POLLHUP)))
			continue;
		if (pidfd >= 0)
			break;
		int client = accept4(listener, NULL, NULL, SOCK_CLOEXEC);
		if (client < 0) {
			if (errno == EAGAIN || errno == EINTR)
				continue;
			error = -errno;
			break;
		}
		result = register_child(client, uid, &server_identity, &marker_identity,
			marker_fd_path, phase_program, state, &phase_link, &pidfd);
		close(client);
		if (result)
			fprintf(stderr, "llama_scx: registration rejected: %s\n", strerror(-result));
		else {
			close(listener);
			listener = -1;
		}
	}
out:
	if (listener >= 0)
		close(listener);
	if (pidfd >= 0) {
		int stop_error = stop_target(pidfd);

		if (stop_error) {
			fprintf(stderr, "llama_scx: selected child cleanup failed: %s\n", strerror(-stop_error));
			error = error ?: stop_error;
		}
	}
	int detach_error = bpf_link__destroy(phase_link);
	if (detach_error)
		error = error ?: detach_error;
	if (state != MAP_FAILED) {
		state->selected_tgid = 0;
		state->current_phase = LLAMA_SCX_PHASE_UNKNOWN;
	}
	detach_error = bpf_link__destroy(scheduler_link);
	if (detach_error)
		error = error ?: detach_error;
	if (state != MAP_FAILED)
		munmap((void *)state, (size_t)page_size);
	bpf_object__close(object);
	if (pidfd >= 0)
		close(pidfd);
	if (marker_fd >= 0)
		close(marker_fd);
	if (server_fd >= 0)
		close(server_fd);
	if (signal_fd >= 0)
		close(signal_fd);
	if (error)
		fprintf(stderr, "llama_scx: %s\n", strerror(-error));
	return error ? EXIT_FAILURE : EXIT_SUCCESS;
}
