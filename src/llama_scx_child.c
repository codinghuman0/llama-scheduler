#define _GNU_SOURCE
/* SPDX-License-Identifier: GPL-2.0 */
/* Launch exactly one selected child under SCHED_EXT. */
#include <errno.h>
#include <fcntl.h>
#include <getopt.h>
#include <limits.h>
#include <signal.h>
#include <sched.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/syscall.h>
#include <sys/time.h>
#include <sys/types.h>
#include <sys/un.h>
#include <sys/wait.h>
#include <unistd.h>

#include "llama_sched_uapi.h"

#define SCX_STATE_PATH "/sys/kernel/sched_ext/state"
#define PHASE_REGISTER_VERSION 1
#define PHASE_REGISTER_MAX 128

static void usage(const char *program)
{
	fprintf(stderr,
		"Usage: %s [--dry-run --state-path FILE] [--phase-register-socket NAME] -- command [args...]\n"
		"  --dry-run          fork and exec without changing the child policy\n"
		"  --state-path FILE  test-only state file; requires --dry-run\n"
		"  --phase-register-socket NAME\n"
		"                     register the selected child for pid-specific uprobes\n"
		"  -h, --help         show this help\n",
		program);
}

static int scheduler_is_enabled(const char *path)
{
	char state[32] = {};
	int fd;
	ssize_t read_len;

	fd = open(path, O_RDONLY | O_CLOEXEC);
	if (fd < 0) {
		fprintf(stderr, "cannot read sched_ext state at %s: %s\n", path,
			strerror(errno));
		return -1;
	}
	read_len = read(fd, state, sizeof(state) - 1);
	if (read_len < 0) {
		fprintf(stderr, "cannot read sched_ext state at %s: %s\n", path,
			strerror(errno));
		close(fd);
		return -1;
	}
	close(fd);
	state[read_len] = '\0';
	if (read_len > 0 && state[read_len - 1] == '\n')
		state[--read_len] = '\0';
	if (strcmp(state, "enabled") == 0)
		return 1;
	fprintf(stderr, "sched_ext scheduler is not active (state: %s)\n", state);
	return 0;
}

static int wait_for_selected_child_exec(pid_t child)
{
	char parent_exe[PATH_MAX];
	char child_exe[PATH_MAX];
	char child_path[64];
	ssize_t parent_length;

	parent_length = readlink("/proc/self/exe", parent_exe, sizeof(parent_exe));
	if (parent_length <= 0)
		return -errno;
	if (snprintf(child_path, sizeof(child_path), "/proc/%ld/exe", (long)child) >=
	    (int)sizeof(child_path))
		return -EINVAL;
	for (int attempt = 0; attempt < 500; attempt++) {
		ssize_t child_length = readlink(child_path, child_exe, sizeof(child_exe));
		int policy = sched_getscheduler(child);

		if (policy == SCHED_EXT && child_length > 0 &&
		    (child_length != parent_length ||
		     memcmp(child_exe, parent_exe, (size_t)child_length)))
			return 0;
		if ((policy < 0 || child_length < 0) && errno == ESRCH)
			return -ESRCH;
		usleep(10000);
	}
	return -ETIMEDOUT;
}

static int register_phase_child(const char *name, pid_t child)
{
	struct sockaddr_un address = { .sun_family = AF_UNIX };
	struct timeval timeout = { .tv_sec = 5 };
	const char *abstract_name = name[0] == '@' ? name + 1 : name;
	char request[PHASE_REGISTER_MAX];
	char response[PHASE_REGISTER_MAX];
	socklen_t address_length;
	size_t name_length = strlen(abstract_name);
	unsigned int version;
	long acknowledged_child;
	int consumed = 0;
	int status;
	int request_length;
	ssize_t response_length;
	int fd;
	int error;

	if (!name_length || name_length > sizeof(address.sun_path) - 1)
		return -EINVAL;
	fd = socket(AF_UNIX, SOCK_SEQPACKET | SOCK_CLOEXEC, 0);
	if (fd < 0)
		return -errno;
	setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
	address.sun_path[0] = '\0';
	memcpy(address.sun_path + 1, abstract_name, name_length);
	address_length = (socklen_t)(offsetof(struct sockaddr_un, sun_path) + 1 + name_length);
	if (connect(fd, (struct sockaddr *)&address, address_length))
		goto fail;
	request_length = snprintf(request, sizeof(request), "REGISTER %u %ld",
		PHASE_REGISTER_VERSION, (long)child);
	if (request_length < 0 || request_length >= (int)sizeof(request)) {
		error = EMSGSIZE;
		goto fail_error;
	}
	if (send(fd, request, (size_t)request_length, MSG_NOSIGNAL) != request_length)
		goto fail;
	response_length = recv(fd, response, sizeof(response) - 1, MSG_TRUNC);
	if (response_length <= 0 || response_length >= (ssize_t)sizeof(response) ||
	    memchr(response, '\0', (size_t)response_length)) {
		error = response_length < 0 ? errno : EPROTO;
		goto fail_error;
	}
	response[response_length] = '\0';
	if (sscanf(response, "ACK %u %ld %d%n", &version, &acknowledged_child,
		   &status, &consumed) != 3 ||
	    consumed != response_length || version != PHASE_REGISTER_VERSION ||
	    acknowledged_child != (long)child) {
		error = EPROTO;
		goto fail_error;
	}
	close(fd);
	return status;
fail:
	error = errno;
fail_error:
	close(fd);
	return -error;
}

static void child_exec(char *const command[], int gate_fd, bool dry_run)
{
	char release;

	if (read(gate_fd, &release, sizeof(release)) != sizeof(release))
		_exit(EXIT_FAILURE);
	close(gate_fd);
	if (!dry_run) {
		struct sched_attr attr = {
			.size = sizeof(attr),
			.sched_policy = SCHED_EXT,
		};

		if (syscall(SYS_sched_setattr, 0, &attr, 0)) {
			fprintf(stderr, "child %ld: cannot enter SCHED_EXT: %s\n",
				(long)getpid(), strerror(errno));
			_exit(126);
		}
	}
	execvp(command[0], command);
	fprintf(stderr, "child %ld: execvp(%s): %s\n", (long)getpid(),
		command[0], strerror(errno));
	_exit(127);
}

int main(int argc, char **argv)
{
	enum {
		OPTION_PHASE_REGISTER_SOCKET = 1000,
	};
	static const struct option options[] = {
		{ "dry-run", no_argument, NULL, 'n' },
		{ "state-path", required_argument, NULL, 's' },
		{ "phase-register-socket", required_argument, NULL, OPTION_PHASE_REGISTER_SOCKET },
		{ "help", no_argument, NULL, 'h' },
		{ NULL, 0, NULL, 0 },
	};
	const char *state_path = SCX_STATE_PATH;
	const char *phase_register_socket = NULL;
	bool dry_run = false;
	bool custom_state_path = false;
	int gate[2];
	int parent_policy;
	int option;
	int state;
	pid_t child;
	int wait_status;
	char release = '1';

	while ((option = getopt_long(argc, argv, "ns:h", options, NULL)) != -1) {
		switch (option) {
		case 'n':
			dry_run = true;
			break;
		case 's':
			state_path = optarg;
			custom_state_path = true;
			break;
		case OPTION_PHASE_REGISTER_SOCKET:
			phase_register_socket = optarg;
			break;
		default:
			usage(argv[0]);
			return option != 'h';
		}
	}
	if (optind == argc) {
		fprintf(stderr, "missing command after --\n");
		usage(argv[0]);
		return EXIT_FAILURE;
	}
	if (!dry_run && custom_state_path) {
		fprintf(stderr, "--state-path is allowed only with --dry-run\n");
		return EXIT_FAILURE;
	}
	state = scheduler_is_enabled(state_path);
	if (state != 1)
		return EXIT_FAILURE;
	parent_policy = sched_getscheduler(0);
	if (parent_policy < 0) {
		fprintf(stderr, "cannot read parent scheduling policy: %s\n",
			strerror(errno));
		return EXIT_FAILURE;
	}
	if (pipe2(gate, O_CLOEXEC)) {
		fprintf(stderr, "pipe2: %s\n", strerror(errno));
		return EXIT_FAILURE;
	}
	child = fork();
	if (child < 0) {
		fprintf(stderr, "fork: %s\n", strerror(errno));
		close(gate[0]);
		close(gate[1]);
		return EXIT_FAILURE;
	}
	if (child == 0) {
		close(gate[1]);
		child_exec(&argv[optind], gate[0], dry_run);
	}
	close(gate[0]);
	printf("parent_pid=%ld parent_policy=%d child_pid=%ld mode=%s\n",
	       (long)getpid(), parent_policy, (long)child,
	       dry_run ? "dry-run" : "sched_ext");
	fflush(stdout);
	if (write(gate[1], &release, sizeof(release)) != sizeof(release)) {
		fprintf(stderr, "cannot release child %ld: %s\n", (long)child,
			strerror(errno));
		close(gate[1]);
		kill(child, SIGKILL);
		waitpid(child, NULL, 0);
		return EXIT_FAILURE;
	}
	close(gate[1]);
	if (phase_register_socket) {
		int registration_error = dry_run ? 0 : wait_for_selected_child_exec(child);

		if (!registration_error)
			registration_error = register_phase_child(phase_register_socket, child);
		if (registration_error) {
			fprintf(stderr, "cannot register child %ld for phase uprobes: %s\n",
				(long)child, strerror(-registration_error));
			kill(child, SIGKILL);
			waitpid(child, NULL, 0);
			return EXIT_FAILURE;
		}
		printf("phase_uprobe_registered_tgid=%ld\n", (long)child);
		fflush(stdout);
	}
	if (waitpid(child, &wait_status, 0) < 0) {
		fprintf(stderr, "waitpid: %s\n", strerror(errno));
		return EXIT_FAILURE;
	}
	if (sched_getscheduler(0) != parent_policy) {
		fprintf(stderr, "parent scheduling policy changed unexpectedly\n");
		return EXIT_FAILURE;
	}
	if (WIFEXITED(wait_status))
		return WEXITSTATUS(wait_status);
	if (WIFSIGNALED(wait_status))
		return 128 + WTERMSIG(wait_status);
	return EXIT_FAILURE;
}
