/* SPDX-License-Identifier: GPL-2.0 */
/* Direct-libBPF loader for the scheduler and optional phase sources. */
#define _GNU_SOURCE
#include <errno.h>
#include <getopt.h>
#include <inttypes.h>
#include <libgen.h>
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
#include <stddef.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <sys/un.h>
#include <sys/utsname.h>
#include <time.h>
#include <unistd.h>

#include <linux/types.h>
#include <bpf/bpf.h>
#include <bpf/libbpf.h>

#include "llama_instrumentation.h"
#include "llama_sched_uapi.h"

#define BPF_OBJECT_PATH "build/llama_scx_simple.bpf.o"
#define EXIT_DUMP_LEN 32768
#define PHASE_PROTOCOL_VERSION 1
#define PHASE_MESSAGE_MAX 128
#define PHASE_REGISTER_VERSION 1
#define PHASE_REGISTER_MAX 128
#define STATUS_INTERVAL_MS 1000

struct exit_record {
	int kind;
	long long exit_code;
	char reason[128];
	char message[1024];
};

struct runtime_data {
	struct exit_record exit_record;
	char exit_dump[EXIT_DUMP_LEN];
};

struct task_totals {
	uint64_t count;
	uint64_t runtime_ns;
	uint64_t queue_wait_ns;
	uint64_t migration_count;
};

struct phase_control {
	bool enabled;
	int listener_fd;
	int client_fd;
	uid_t allowed_uid;
	__u32 client_tgid;
	__u32 last_client_tgid;
	__u32 latest_phase;
	__u64 latest_sequence;
};

struct phase_uprobe_control {
	bool enabled;
	int listener_fd;
	uid_t allowed_uid;
	const char *binary_path;
	__u32 target_tgid;
	__u32 last_target_tgid;
	struct bpf_link *begin_link;
	struct bpf_link *end_link;
};

static bool verbose;
static volatile sig_atomic_t exit_requested;

static int libbpf_log(enum libbpf_print_level level, const char *format,
		      va_list args)
{
	if (level == LIBBPF_DEBUG && !verbose)
		return 0;
	return vfprintf(stderr, format, args);
}

static void request_exit(int signal_number)
{
	(void)signal_number;
	exit_requested = 1;
}

static void usage(const char *program)
{
	fprintf(stderr,
		"Usage: %s [-f] [-v] [-o DIRECTORY] [PHASE SOURCE]\n"
		"  -f  preserve scx_simple FIFO mode (default is weighted vtime)\n"
		"  -v  print libbpf debug output\n"
		"  -o  create this empty instrumentation output directory\n"
		"  --phase-socket NAME --phase-uid UID\n"
		"      use the legacy abstract SOCK_SEQPACKET phase source\n"
		"  --phase-uprobe ELF --phase-register-socket NAME --phase-uid UID\n"
		"      attach semantic decode markers to one registered selected child\n"
		"  -h  show this help\n",
		program);
}

static const char *phase_name(__u32 phase)
{
	switch (phase) {
	case LLAMA_PHASE_PREFILL:
		return "PREFILL";
	case LLAMA_PHASE_DECODE:
		return "DECODE";
	case LLAMA_PHASE_MIXED:
		return "MIXED";
	default:
		return "UNKNOWN";
	}
}

static int parse_uid(const char *text, uid_t *uid)
{
	char *end = NULL;
	unsigned long long value;

	errno = 0;
	value = strtoull(text, &end, 10);
	if (errno || !text[0] || !end || *end || (uid_t)value != value)
		return -EINVAL;
	*uid = (uid_t)value;
	return 0;
}

static int64_t monotonic_ms(void)
{
	struct timespec now;

	if (clock_gettime(CLOCK_MONOTONIC, &now))
		return 0;
	return (int64_t)now.tv_sec * 1000 + now.tv_nsec / 1000000;
}

static void phase_control_init(struct phase_control *control)
{
	memset(control, 0, sizeof(*control));
	control->listener_fd = -1;
	control->client_fd = -1;
	control->latest_phase = LLAMA_PHASE_UNKNOWN;
}

static int phase_control_open(struct phase_control *control, const char *name, uid_t uid)
{
	struct sockaddr_un address = { .sun_family = AF_UNIX };
	const char *abstract_name = name[0] == '@' ? name + 1 : name;
	const char *operation = "socket";
	socklen_t address_length;
	size_t name_length = strlen(abstract_name);
	int fd;
	int error;

	if (!name_length || name_length > sizeof(address.sun_path) - 1) {
		fprintf(stderr, "phase control: invalid socket name @%s: errno=%d (%s)\n",
			abstract_name, EINVAL, strerror(EINVAL));
		return -EINVAL;
	}
	fd = socket(AF_UNIX, SOCK_SEQPACKET | SOCK_CLOEXEC | SOCK_NONBLOCK, 0);
	if (fd < 0)
		goto fail;
	address.sun_path[0] = '\0';
	memcpy(address.sun_path + 1, abstract_name, name_length);
	address_length = (socklen_t)(offsetof(struct sockaddr_un, sun_path) + 1 + name_length);
	operation = "bind";
	if (bind(fd, (struct sockaddr *)&address, address_length))
		goto fail;
	operation = "listen";
	if (listen(fd, 4))
		goto fail;
	control->enabled = true;
	control->listener_fd = fd;
	control->allowed_uid = uid;
	fprintf(stderr, "phase control: listening on @%s uid=%u\n",
		abstract_name, (unsigned int)uid);
	return 0;
fail:
	error = errno;
	fprintf(stderr, "phase control: %s @%s failed: errno=%d (%s)\n",
		operation, abstract_name, error, strerror(error));
	if (fd >= 0)
		close(fd);
	return -error;
}

static void phase_control_close_client(struct phase_control *control, int phase_map_fd)
{
	if (control->client_tgid && phase_map_fd >= 0 &&
	    bpf_map_delete_elem(phase_map_fd, &control->client_tgid) && errno != ENOENT)
		fprintf(stderr, "cannot delete phase state for tgid %u: %s\n",
			control->client_tgid, strerror(errno));
	if (control->client_fd >= 0)
		close(control->client_fd);
	control->client_fd = -1;
	control->client_tgid = 0;
}

static void phase_control_close(struct phase_control *control, int phase_map_fd)
{
	phase_control_close_client(control, phase_map_fd);
	if (control->listener_fd >= 0)
		close(control->listener_fd);
	control->listener_fd = -1;
}

static void phase_control_accept(struct phase_control *control)
{
	struct ucred credentials;
	socklen_t credentials_length = sizeof(credentials);
	int client_fd;
	int policy;

	client_fd = accept4(control->listener_fd, NULL, NULL, SOCK_CLOEXEC | SOCK_NONBLOCK);
	if (client_fd < 0) {
		if (errno != EAGAIN && errno != EWOULDBLOCK)
			fprintf(stderr, "phase client accept failed: %s\n", strerror(errno));
		return;
	}
	if (control->client_fd >= 0) {
		fprintf(stderr, "rejecting extra phase client\n");
		close(client_fd);
		return;
	}
	if (getsockopt(client_fd, SOL_SOCKET, SO_PEERCRED, &credentials,
		       &credentials_length) || credentials_length != sizeof(credentials)) {
		fprintf(stderr, "rejecting phase client: SO_PEERCRED failed\n");
		close(client_fd);
		return;
	}
	if (credentials.uid != control->allowed_uid) {
		fprintf(stderr, "rejecting phase client pid %d uid %u (expected uid %u)\n",
			credentials.pid, (unsigned int)credentials.uid,
			(unsigned int)control->allowed_uid);
		close(client_fd);
		return;
	}
	policy = sched_getscheduler(credentials.pid);
	if (policy != SCHED_EXT) {
		fprintf(stderr, "rejecting phase client pid %d: scheduler policy is %d, not SCHED_EXT\n",
			credentials.pid, policy);
		close(client_fd);
		return;
	}
	control->client_fd = client_fd;
	control->client_tgid = (__u32)credentials.pid;
	control->last_client_tgid = control->client_tgid;
	control->latest_phase = LLAMA_PHASE_UNKNOWN;
	control->latest_sequence = 0;
	fprintf(stderr, "registered phase client tgid %u\n", control->client_tgid);
}

static int phase_control_send_ack(struct phase_control *control, __u64 sequence, int status)
{
	char response[PHASE_MESSAGE_MAX];
	int length;
	ssize_t sent;

	length = snprintf(response, sizeof(response), "ACK %u %" PRIu64 " %d",
			  PHASE_PROTOCOL_VERSION, (uint64_t)sequence, status);
	if (length < 0 || length >= (int)sizeof(response))
		return -EMSGSIZE;
	sent = send(control->client_fd, response, (size_t)length, MSG_NOSIGNAL);
	return sent == length ? 0 : -(errno ?: EIO);
}

static void phase_control_handle_message(struct phase_control *control, int phase_map_fd)
{
	struct llama_phase_value value = {};
	char request[PHASE_MESSAGE_MAX];
	unsigned int phase = 0;
	uint64_t sequence = 0;
	char *end;
	ssize_t length;
	int status = 0;

	length = recv(control->client_fd, request, sizeof(request) - 1,
		      MSG_DONTWAIT | MSG_TRUNC);
	if (!length) {
		phase_control_close_client(control, phase_map_fd);
		return;
	}
	if (length < 0) {
		if (errno != EAGAIN && errno != EWOULDBLOCK)
			phase_control_close_client(control, phase_map_fd);
		return;
	}
	if (length >= (ssize_t)sizeof(request)) {
		status = -EMSGSIZE;
	} else {
		request[length] = 0;
		/* Exact prefix and suffix also reject embedded NULs and extra fields. */
		if (length < 11 || memcmp(request, "PHASE 1 ", 8) ||
		    request[8] < '0' || request[8] > '9') {
			status = -EPROTO;
		} else {
			errno = 0;
			sequence = strtoull(request + 8, &end, 10);
			if (errno || end != request + length - 2 || end[0] != ' ')
				status = -EPROTO;
			else if (end[1] != '1' && end[1] != '2')
				status = -EINVAL;
			else
				phase = (unsigned int)(end[1] - '0');
		}
		if (!status && (!sequence || sequence != control->latest_sequence + 1))
			status = -EPROTO;
	}
	if (!status) {
		value.phase = phase;
		value.active = 1;
		value.source = LLAMA_PHASE_SOURCE_SOCKET;
		value.sequence = sequence;
		if (bpf_map_update_elem(phase_map_fd, &control->client_tgid, &value, BPF_ANY))
			status = -errno;
	}
	if (phase_control_send_ack(control, sequence, status)) {
		phase_control_close_client(control, phase_map_fd);
		return;
	}
	if (!status) {
		control->latest_phase = phase;
		control->latest_sequence = sequence;
		fprintf(stderr, "phase update acknowledged: tgid=%u phase=%s sequence=%" PRIu64 "\n",
			control->client_tgid, phase_name(phase), sequence);
	}
}

static void phase_uprobe_init(struct phase_uprobe_control *control)
{
	memset(control, 0, sizeof(*control));
	control->listener_fd = -1;
}

static int phase_uprobe_open(struct phase_uprobe_control *control, const char *name,
			     uid_t uid, const char *binary_path)
{
	struct sockaddr_un address = { .sun_family = AF_UNIX };
	const char *abstract_name = name[0] == '@' ? name + 1 : name;
	socklen_t address_length;
	size_t name_length = strlen(abstract_name);
	int fd = -1;
	int error;

	if (!name_length || name_length > sizeof(address.sun_path) - 1 ||
	    access(binary_path, R_OK)) {
		error = errno ?: EINVAL;
		fprintf(stderr, "phase uprobe: invalid registration socket or marker ELF: %s\n",
			strerror(error));
		return -error;
	}
	fd = socket(AF_UNIX, SOCK_SEQPACKET | SOCK_CLOEXEC | SOCK_NONBLOCK, 0);
	if (fd < 0)
		goto fail;
	address.sun_path[0] = '\0';
	memcpy(address.sun_path + 1, abstract_name, name_length);
	address_length = (socklen_t)(offsetof(struct sockaddr_un, sun_path) + 1 + name_length);
	if (bind(fd, (struct sockaddr *)&address, address_length))
		goto fail;
	if (listen(fd, 4))
		goto fail;
	control->enabled = true;
	control->listener_fd = fd;
	control->allowed_uid = uid;
	control->binary_path = binary_path;
	fprintf(stderr, "phase uprobe: listening on @%s uid=%u marker_elf=%s\n",
		abstract_name, (unsigned int)uid, binary_path);
	return 0;
fail:
	error = errno;
	fprintf(stderr, "phase uprobe: registration listener failed: %s\n", strerror(error));
	if (fd >= 0)
		close(fd);
	return -error;
}

static int parse_phase_registration(const char *message, size_t length, __u32 *tgid)
{
	const char prefix[] = "REGISTER 1 ";
	char text[PHASE_REGISTER_MAX];
	char *end = NULL;
	unsigned long long value;

	if (length >= sizeof(text) || length <= sizeof(prefix) - 1 ||
	    memchr(message, '\0', length) ||
	    memcmp(message, prefix, sizeof(prefix) - 1))
		return -EPROTO;
	memcpy(text, message, length);
	text[length] = '\0';
	errno = 0;
	value = strtoull(text + sizeof(prefix) - 1, &end, 10);
	if (errno || !value || value > UINT32_MAX || end != text + length)
		return -EPROTO;
	*tgid = (__u32)value;
	return 0;
}

static int read_process_identity(__u32 tgid, __u32 *parent, uid_t *uid)
{
	char path[64];
	char line[256];
	unsigned int parsed_parent = 0;
	unsigned int parsed_uid = UINT_MAX;
	FILE *status;

	if (snprintf(path, sizeof(path), "/proc/%u/status", tgid) >= (int)sizeof(path))
		return -EINVAL;
	status = fopen(path, "re");
	if (!status)
		return -errno;
	while (fgets(line, sizeof(line), status)) {
		if (sscanf(line, "PPid:%u", &parsed_parent) == 1)
			continue;
		if (sscanf(line, "Uid:%u", &parsed_uid) == 1)
			continue;
	}
	fclose(status);
	if (!parsed_parent || parsed_uid == UINT_MAX || (uid_t)parsed_uid != parsed_uid)
		return -EPROTO;
	*parent = parsed_parent;
	*uid = (uid_t)parsed_uid;
	return 0;
}

static int phase_uprobe_attach(struct phase_uprobe_control *control,
			       struct bpf_object *object, int config_map_fd, __u32 tgid)
{
	LIBBPF_OPTS(bpf_uprobe_opts, begin_options,
		.func_name = "llama_scx_decode_begin_v1");
	LIBBPF_OPTS(bpf_uprobe_opts, end_options,
		.func_name = "llama_scx_decode_end_v1");
	struct llama_uprobe_config config = {
		.enabled = 1,
		.target_tgid = tgid,
	};
	struct llama_uprobe_config disabled = {};
	struct bpf_program *begin_program;
	struct bpf_program *end_program;
	int error;

	begin_program = bpf_object__find_program_by_name(object,
		"llama_scx_decode_begin_v1_uprobe");
	end_program = bpf_object__find_program_by_name(object,
		"llama_scx_decode_end_v1_uprobe");
	if (!begin_program || !end_program)
		return -ENOENT;
	if (bpf_map_update_elem(config_map_fd, &(const __u32){ 0 }, &config, BPF_ANY))
		return -errno;
	control->begin_link = bpf_program__attach_uprobe_opts(begin_program, (pid_t)tgid,
		control->binary_path, 0, &begin_options);
	if (!control->begin_link) {
		error = -(errno ?: EIO);
		goto fail;
	}
	control->end_link = bpf_program__attach_uprobe_opts(end_program, (pid_t)tgid,
		control->binary_path, 0, &end_options);
	if (!control->end_link) {
		error = -(errno ?: EIO);
		goto fail;
	}
	control->target_tgid = tgid;
	control->last_target_tgid = tgid;
	return 0;
fail:
	bpf_link__destroy(control->end_link);
	bpf_link__destroy(control->begin_link);
	control->end_link = NULL;
	control->begin_link = NULL;
	bpf_map_update_elem(config_map_fd, &(const __u32){ 0 }, &disabled, BPF_ANY);
	return error;
}

static void phase_uprobe_send_ack(int fd, __u32 tgid, int status)
{
	char response[PHASE_REGISTER_MAX];
	int length;

	length = snprintf(response, sizeof(response), "ACK %u %u %d",
		PHASE_REGISTER_VERSION, tgid, status);
	if (length < 0 || length >= (int)sizeof(response) ||
	    send(fd, response, (size_t)length, MSG_NOSIGNAL) != length)
		fprintf(stderr, "phase uprobe: cannot send registration ACK\n");
}

static void phase_uprobe_accept(struct phase_uprobe_control *control,
				struct bpf_object *object, int config_map_fd)
{
	struct timeval timeout = { .tv_sec = 1 };
	struct ucred credentials;
	socklen_t credentials_length = sizeof(credentials);
	char request[PHASE_REGISTER_MAX];
	__u32 target_tgid = 0;
	__u32 parent_tgid = 0;
	uid_t target_uid = 0;
	ssize_t length;
	int client_fd;
	int status = 0;
	int policy;

	client_fd = accept4(control->listener_fd, NULL, NULL, SOCK_CLOEXEC);
	if (client_fd < 0) {
		if (errno != EAGAIN && errno != EWOULDBLOCK)
			fprintf(stderr, "phase uprobe: registration accept failed: %s\n",
				strerror(errno));
		return;
	}
	setsockopt(client_fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
	if (getsockopt(client_fd, SOL_SOCKET, SO_PEERCRED, &credentials,
		       &credentials_length) || credentials_length != sizeof(credentials)) {
		status = -EPERM;
		goto reply;
	}
	if (credentials.uid != control->allowed_uid) {
		status = -EACCES;
		goto reply;
	}
	length = recv(client_fd, request, sizeof(request), MSG_TRUNC);
	if (length <= 0 || length >= (ssize_t)sizeof(request)) {
		status = length < 0 ? -errno : -EMSGSIZE;
		goto reply;
	}
	status = parse_phase_registration(request, (size_t)length, &target_tgid);
	if (status)
		goto reply;
	if (control->target_tgid) {
		status = -EBUSY;
		goto reply;
	}
	status = read_process_identity(target_tgid, &parent_tgid, &target_uid);
	if (status)
		goto reply;
	if (parent_tgid != (__u32)credentials.pid || target_uid != credentials.uid) {
		status = -EPERM;
		goto reply;
	}
	policy = sched_getscheduler((pid_t)target_tgid);
	if (policy != SCHED_EXT) {
		status = policy < 0 ? -errno : -EPERM;
		goto reply;
	}
	status = phase_uprobe_attach(control, object, config_map_fd, target_tgid);
reply:
	phase_uprobe_send_ack(client_fd, target_tgid, status);
	if (!status)
		fprintf(stderr, "phase uprobe: attached pid-specific decode markers to tgid=%u\n",
			target_tgid);
	else
		fprintf(stderr, "phase uprobe: rejected registration tgid=%u status=%d (%s)\n",
			target_tgid, status, strerror(-status));
	close(client_fd);
}

static void phase_uprobe_close(struct phase_uprobe_control *control, int config_map_fd)
{
	struct llama_uprobe_config disabled = {};
	__u32 key = 0;

	if (config_map_fd >= 0)
		bpf_map_update_elem(config_map_fd, &key, &disabled, BPF_ANY);
	bpf_link__destroy(control->end_link);
	bpf_link__destroy(control->begin_link);
	control->end_link = NULL;
	control->begin_link = NULL;
	if (control->listener_fd >= 0)
		close(control->listener_fd);
	control->listener_fd = -1;
}

static void iso_timestamp(char output[32])
{
	struct timespec now;
	struct tm utc;

	clock_gettime(CLOCK_REALTIME, &now);
	gmtime_r(&now.tv_sec, &utc);
	strftime(output, 32, "%Y-%m-%dT%H:%M:%SZ", &utc);
}

static int mkdir_new(const char *path)
{
	if (!mkdir(path, 0755))
		return 0;
	if (errno == EEXIST)
		fprintf(stderr, "instrumentation output directory already exists: %s\n", path);
	else
		fprintf(stderr, "cannot create instrumentation output directory %s: %s\n",
			path, strerror(errno));
	return -1;
}

static int prepare_output_dir(const char *requested, char path[PATH_MAX])
{
	struct tm utc;
	time_t now;

	if (requested) {
		if (snprintf(path, PATH_MAX, "%s", requested) >= PATH_MAX) {
			fprintf(stderr, "instrumentation output path is too long\n");
			return -1;
		}
		return mkdir_new(path);
	}
	if (mkdir("results", 0755) && errno != EEXIST) {
		fprintf(stderr, "cannot create results: %s\n", strerror(errno));
		return -1;
	}
	if (mkdir("results/instrumentation", 0755) && errno != EEXIST) {
		fprintf(stderr, "cannot create results/instrumentation: %s\n", strerror(errno));
		return -1;
	}
	now = time(NULL);
	gmtime_r(&now, &utc);
	if (!strftime(path, PATH_MAX, "results/instrumentation/%Y%m%d-%H%M%S", &utc)) {
		fprintf(stderr, "cannot format instrumentation output path\n");
		return -1;
	}
	return mkdir_new(path);
}

static int read_stats(struct bpf_map *stats_map, __u64 stats[2])
{
	const int cpus = libbpf_num_possible_cpus();
	__u64 *per_cpu;
	__u32 index;

	if (cpus <= 0)
		return -EINVAL;
	per_cpu = calloc((size_t)cpus, sizeof(*per_cpu));
	if (!per_cpu)
		return -ENOMEM;
	memset(stats, 0, sizeof(__u64) * 2);
	for (index = 0; index < 2; index++) {
		if (!bpf_map_lookup_elem(bpf_map__fd(stats_map), &index, per_cpu)) {
			for (int cpu = 0; cpu < cpus; cpu++)
				stats[index] += per_cpu[cpu];
		}
	}
	free(per_cpu);
	return 0;
}

static void add_cpu_stats(struct llama_cpu_stats *total,
			  const struct llama_cpu_stats *value)
{
	const uint64_t *source = (const uint64_t *)value;
	uint64_t *destination = (uint64_t *)total;

	for (size_t index = 0; index < sizeof(*total) / sizeof(*source); index++)
		destination[index] += source[index];
}

static int collect_cpu_stats(struct bpf_map *map, struct llama_cpu_stats **values,
			     int *cpu_count, struct llama_cpu_stats *total)
{
	__u32 key = 0;
	int cpus = libbpf_num_possible_cpus();
	struct llama_cpu_stats *per_cpu;

	memset(total, 0, sizeof(*total));
	*values = NULL;
	*cpu_count = 0;
	if (!map || cpus <= 0)
		return -ENOENT;
	per_cpu = calloc((size_t)cpus, sizeof(*per_cpu));
	if (!per_cpu)
		return -ENOMEM;
	if (bpf_map_lookup_elem(bpf_map__fd(map), &key, per_cpu)) {
		int error = -errno;
		free(per_cpu);
		return error;
	}
	for (int cpu = 0; cpu < cpus; cpu++)
		add_cpu_stats(total, &per_cpu[cpu]);
	*values = per_cpu;
	*cpu_count = cpus;
	return 0;
}

static void add_phase_observation(struct llama_phase_observation *total,
				  const struct llama_phase_observation *value)
{
	total->select_cpu += value->select_cpu;
	total->enqueue += value->enqueue;
	total->running += value->running;
	total->stopping += value->stopping;
}

static int collect_phase_observations(
		struct bpf_map *map,
		struct llama_phase_observation totals[LLAMA_PHASE_COUNT])
{
	struct llama_phase_observation *per_cpu;
	int cpus = libbpf_num_possible_cpus();

	memset(totals, 0, sizeof(*totals) * LLAMA_PHASE_COUNT);
	if (!map || cpus <= 0)
		return -ENOENT;
	per_cpu = calloc((size_t)cpus, sizeof(*per_cpu));
	if (!per_cpu)
		return -ENOMEM;
	for (__u32 phase = 0; phase < LLAMA_PHASE_COUNT; phase++) {
		memset(per_cpu, 0, (size_t)cpus * sizeof(*per_cpu));
		if (bpf_map_lookup_elem(bpf_map__fd(map), &phase, per_cpu)) {
			int error = -errno;

			free(per_cpu);
			return error;
		}
		for (int cpu = 0; cpu < cpus; cpu++)
			add_phase_observation(&totals[phase], &per_cpu[cpu]);
	}
	free(per_cpu);
	return 0;
}

static int collect_uprobe_stats(struct bpf_map *map,
				struct llama_uprobe_stats *total)
{
	struct llama_uprobe_stats *per_cpu;
	const int cpus = libbpf_num_possible_cpus();
	__u32 key = 0;

	memset(total, 0, sizeof(*total));
	if (!map || cpus <= 0)
		return -ENOENT;
	per_cpu = calloc((size_t)cpus, sizeof(*per_cpu));
	if (!per_cpu)
		return -ENOMEM;
	if (bpf_map_lookup_elem(bpf_map__fd(map), &key, per_cpu)) {
		int error = -errno;

		free(per_cpu);
		return error;
	}
	for (int cpu = 0; cpu < cpus; cpu++) {
		const uint64_t *source = (const uint64_t *)&per_cpu[cpu];
		uint64_t *destination = (uint64_t *)total;

		for (size_t index = 0; index < sizeof(*total) / sizeof(*source); index++)
			destination[index] += source[index];
	}
	free(per_cpu);
	return 0;
}

static int collect_phase_state(struct bpf_map *map, __u32 tgid,
			       struct llama_phase_value *state)
{
	memset(state, 0, sizeof(*state));
	if (!map || !tgid)
		return -ENOENT;
	return bpf_map_lookup_elem(bpf_map__fd(map), &tgid, state) ? -errno : 0;
}

static int collect_tracking_state(struct bpf_map *map,
				  struct llama_tracking_state *state)
{
	__u32 key = 0;

	memset(state, 0, sizeof(*state));
	if (!map)
		return -ENOENT;
	return bpf_map_lookup_elem(bpf_map__fd(map), &key, state) ? -errno : 0;
}

static void json_string(FILE *output, const char *value)
{
	fputc('"', output);
	for (; value && *value; value++) {
		unsigned char c = (unsigned char)*value;

		if (c == '"' || c == '\\')
			fprintf(output, "\\%c", c);
		else if (c == '\n')
			fputs("\\n", output);
		else if (c == '\r')
			fputs("\\r", output);
		else if (c == '\t')
			fputs("\\t", output);
		else if (c < 0x20)
			fprintf(output, "\\u%04x", c);
		else
			fputc(c, output);
	}
	fputc('"', output);
}

static int write_task_json(FILE *output, struct bpf_map *map,
			   struct task_totals *totals)
{
	struct llama_task_key key;
	struct llama_task_key next_key;
	struct llama_task_record record;
	bool first = true;
	int error;

	memset(totals, 0, sizeof(*totals));
	if (!map)
		return 0;
	error = bpf_map_get_next_key(bpf_map__fd(map), NULL, &next_key);
	while (!error) {
		key = next_key;
		if (!bpf_map_lookup_elem(bpf_map__fd(map), &key, &record)) {
			fprintf(output, "%s{\"pid\":%u,\"start_time\":%llu,\"last_cpu\":%u,"
				"\"enqueue_count\":%llu,\"running_count\":%llu,"
				"\"stopping_count\":%llu,\"runtime_ns\":%llu,"
				"\"queue_wait_ns\":%llu,\"migration_count\":%llu}",
				first ? "" : ",", key.pid,
				(unsigned long long)key.start_time, record.last_cpu,
				(unsigned long long)record.enqueue_count,
				(unsigned long long)record.running_count,
				(unsigned long long)record.stopping_count,
				(unsigned long long)record.runtime_ns,
				(unsigned long long)record.queue_wait_ns,
				(unsigned long long)record.migration_count);
			first = false;
			totals->count++;
			totals->runtime_ns += record.runtime_ns;
			totals->queue_wait_ns += record.queue_wait_ns;
			totals->migration_count += record.migration_count;
		}
		error = bpf_map_get_next_key(bpf_map__fd(map), &key, &next_key);
	}
	return error == -ENOENT ? 0 : error;
}

static int write_report(const char *directory, const char *start_timestamp,
			const char *end_timestamp, struct bpf_map *cpu_map,
			struct bpf_map *task_map, struct bpf_map *tracking_map,
			struct bpf_map *phase_state_map,
			struct bpf_map *phase_observation_map,
			struct bpf_map *phase_uprobe_stats_map,
			const struct phase_control *phase_control,
			const struct phase_uprobe_control *phase_uprobe,
			const struct runtime_data *exit_data)
{
	char json_path[PATH_MAX];
	char text_path[PATH_MAX];
	struct utsname uts = {};
	struct llama_cpu_stats *per_cpu = NULL;
	struct llama_cpu_stats total;
	struct llama_tracking_state tracking;
	struct llama_phase_observation phase_observations[LLAMA_PHASE_COUNT];
	struct llama_uprobe_stats uprobe_stats;
	struct llama_phase_value uprobe_state;
	struct task_totals tasks;
	FILE *json = NULL;
	FILE *text = NULL;
	int cpu_count = 0;
	int error = 0;

	if (snprintf(json_path, sizeof(json_path), "%s/instrumentation.json", directory) >=
	    (int)sizeof(json_path) ||
	    snprintf(text_path, sizeof(text_path), "%s/summary.txt", directory) >=
	    (int)sizeof(text_path)) {
		fprintf(stderr, "instrumentation output file path is too long\n");
		return -1;
	}
	if (uname(&uts))
		snprintf(uts.release, sizeof(uts.release), "unknown");
	if (collect_cpu_stats(cpu_map, &per_cpu, &cpu_count, &total))
		memset(&total, 0, sizeof(total));
	if (collect_tracking_state(tracking_map, &tracking))
		memset(&tracking, 0, sizeof(tracking));
	if (collect_phase_observations(phase_observation_map, phase_observations))
		memset(phase_observations, 0, sizeof(phase_observations));
	if (collect_uprobe_stats(phase_uprobe_stats_map, &uprobe_stats))
		memset(&uprobe_stats, 0, sizeof(uprobe_stats));
	if (collect_phase_state(phase_state_map, phase_uprobe->last_target_tgid,
				&uprobe_state))
		memset(&uprobe_state, 0, sizeof(uprobe_state));
	json = fopen(json_path, "wx");
	if (!json) {
		fprintf(stderr, "cannot write instrumentation JSON %s: %s\n", json_path,
			strerror(errno));
		error = -1;
		goto out;
	}
	fprintf(json, "{\n  \"schema_version\": %d,\n  \"scheduler_name\": ",
		LLAMA_INSTRUMENTATION_SCHEMA_VERSION);
	json_string(json, "llama_simple");
	fputs(",\n  \"kernel_version\": ", json);
	json_string(json, uts.release);
	fputs(",\n  \"start_timestamp\": ", json);
	json_string(json, start_timestamp);
	fputs(",\n  \"end_timestamp\": ", json);
	json_string(json, end_timestamp);
	fprintf(json, ",\n  \"exit\": {\"kind\": %d, \"code\": %lld, \"reason\": ",
		exit_data->exit_record.kind, exit_data->exit_record.exit_code);
	json_string(json, exit_data->exit_record.reason);
	fputs(", \"message\": ", json);
	json_string(json, exit_data->exit_record.message);
	fprintf(json, "},\n  \"phase_control\": {\"enabled\":%s,"
		"\"client_tgid\":%u,\"last_client_tgid\":%u,"
		"\"latest_phase\":%u,\"latest_phase_name\":\"%s\","
		"\"latest_sequence\":%" PRIu64 "},\n  \"phase_uprobe\": {\"enabled\":%s,"
		"\"target_tgid\":%u,\"last_target_tgid\":%u,\"marker_elf\":",
		phase_control->enabled ? "true" : "false", phase_control->client_tgid,
		phase_control->last_client_tgid, phase_control->latest_phase,
		phase_name(phase_control->latest_phase),
		(uint64_t)phase_control->latest_sequence,
		phase_uprobe->enabled ? "true" : "false", phase_uprobe->target_tgid,
		phase_uprobe->last_target_tgid);
	json_string(json, phase_uprobe->binary_path ?: "");
	fprintf(json, ",\"state\":{\"active\":%u,\"phase\":%u,\"phase_name\":\"%s\","
		"\"run_id\":%llu,\"call_id\":%llu,\"retry\":%llu,"
		"\"n_prefill\":%llu,\"n_decode\":%llu,\"n_unknown\":%llu,\"result\":%lld},"
		"\"counters\":{\"begin_events\":%llu,\"end_events\":%llu,"
		"\"begin_unknown\":%llu,\"begin_prefill\":%llu,\"begin_decode\":%llu,"
		"\"begin_mixed\":%llu,\"abi_failures\":%llu,\"user_read_failures\":%llu,"
		"\"unsupported_phases\":%llu,\"stale_end_events\":%llu,"
		"\"map_update_failures\":%llu,\"filtered_events\":%llu}},\n"
		"  \"phase_observations\": [",
		uprobe_state.active, uprobe_state.phase, phase_name(uprobe_state.phase),
		(unsigned long long)uprobe_state.run_id,
		(unsigned long long)uprobe_state.call_id,
		(unsigned long long)uprobe_state.retry,
		(unsigned long long)uprobe_state.n_prefill,
		(unsigned long long)uprobe_state.n_decode,
		(unsigned long long)uprobe_state.n_unknown,
		(long long)uprobe_state.result,
		(unsigned long long)uprobe_stats.begin_events,
		(unsigned long long)uprobe_stats.end_events,
		(unsigned long long)uprobe_stats.begin_unknown,
		(unsigned long long)uprobe_stats.begin_prefill,
		(unsigned long long)uprobe_stats.begin_decode,
		(unsigned long long)uprobe_stats.begin_mixed,
		(unsigned long long)uprobe_stats.abi_failures,
		(unsigned long long)uprobe_stats.user_read_failures,
		(unsigned long long)uprobe_stats.unsupported_phases,
		(unsigned long long)uprobe_stats.stale_end_events,
		(unsigned long long)uprobe_stats.map_update_failures,
		(unsigned long long)uprobe_stats.filtered_events);
	for (__u32 phase = 0; phase < LLAMA_PHASE_COUNT; phase++) {
		const struct llama_phase_observation *observation = &phase_observations[phase];

		fprintf(json, "%s{\"phase\":%u,\"name\":\"%s\","
			"\"select_cpu\":%llu,\"enqueue\":%llu,"
			"\"running\":%llu,\"stopping\":%llu}",
			phase ? "," : "", phase, phase_name(phase),
			(unsigned long long)observation->select_cpu,
			(unsigned long long)observation->enqueue,
			(unsigned long long)observation->running,
			(unsigned long long)observation->stopping);
	}
	fputs("],\n  \"aggregate\": {", json);
	fprintf(json, "\"enqueue_count\": %llu, \"direct_local_insertions\": %llu, "
		"\"shared_dsq_insertions\": %llu, \"dispatch_callbacks\": %llu, "
		"\"running_callbacks\": %llu, \"stopping_callbacks\": %llu, "
		"\"runtime_ns\": %llu, \"queue_wait_ns\": %llu, \"migration_count\": %llu, "
		"\"current_tracked_tasks\": %llu, \"peak_tracked_tasks\": %llu, "
		"\"task_lookup_failures\": %llu, \"task_update_failures\": %llu, "
		"\"task_capacity_failures\": %llu, \"task_cleanup_failures\": %llu, \"tracking_state_lookup_failures\": %llu, "
		"\"completed_record_failures\": %llu},\n  \"per_cpu\": [",
		(unsigned long long)total.enqueue_count,
		(unsigned long long)total.direct_local_insertions,
		(unsigned long long)total.shared_dsq_insertions,
		(unsigned long long)total.dispatch_callbacks,
		(unsigned long long)total.running_callbacks,
		(unsigned long long)total.stopping_callbacks,
		(unsigned long long)total.runtime_ns,
		(unsigned long long)total.queue_wait_ns,
		(unsigned long long)total.migration_count,
		(unsigned long long)tracking.current_tracked_tasks,
		(unsigned long long)tracking.peak_tracked_tasks,
		(unsigned long long)total.task_lookup_failures,
		(unsigned long long)total.task_update_failures,
		(unsigned long long)total.task_capacity_failures,
		(unsigned long long)total.task_cleanup_failures,
		(unsigned long long)total.tracking_state_lookup_failures,
		(unsigned long long)total.completed_record_failures);
	for (int cpu = 0; cpu < cpu_count; cpu++) {
		const struct llama_cpu_stats *value = &per_cpu[cpu];
		fprintf(json, "%s{\"cpu\":%d,\"runtime_ns\":%llu,\"queue_wait_ns\":%llu,"
			"\"migration_count\":%llu,\"enqueue_count\":%llu,"
			"\"direct_local_insertions\":%llu,\"shared_dsq_insertions\":%llu,"
			"\"dispatch_callbacks\":%llu,\"running_callbacks\":%llu,"
			"\"stopping_callbacks\":%llu}", cpu ? "," : "", cpu,
			(unsigned long long)value->runtime_ns,
			(unsigned long long)value->queue_wait_ns,
			(unsigned long long)value->migration_count,
			(unsigned long long)value->enqueue_count,
			(unsigned long long)value->direct_local_insertions,
			(unsigned long long)value->shared_dsq_insertions,
			(unsigned long long)value->dispatch_callbacks,
			(unsigned long long)value->running_callbacks,
			(unsigned long long)value->stopping_callbacks);
	}
	fputs("],\n  \"tasks\": [", json);
	if (write_task_json(json, task_map, &tasks)) {
		fprintf(stderr, "cannot enumerate completed task statistics\n");
		error = -1;
	}
	fprintf(json, "],\n  \"task_aggregate\": {\"count\":%llu,\"runtime_ns\":%llu,"
		"\"queue_wait_ns\":%llu,\"migration_count\":%llu},\n"
		"  \"limitations\": [\"completed tasks only; live map is cleaned on disable\","
		"\"queue wait is latest enqueue to next running callback\","
		"\"capacity and update failures can leave a task untracked\"]\n}\n",
		(unsigned long long)tasks.count,
		(unsigned long long)tasks.runtime_ns,
		(unsigned long long)tasks.queue_wait_ns,
		(unsigned long long)tasks.migration_count);
	if (fclose(json)) {
		fprintf(stderr, "cannot finish instrumentation JSON %s: %s\n", json_path,
			strerror(errno));
		error = -1;
	}
	json = NULL;
	text = fopen(text_path, "wx");
	if (!text) {
		fprintf(stderr, "cannot write instrumentation summary %s: %s\n", text_path,
			strerror(errno));
		error = -1;
		goto out;
	}
	fprintf(text, "llama_simple instrumentation summary\n"
		"kernel=%s start=%s end=%s\n"
		"exit kind=%d code=%lld reason=%s message=%s\n"
		"enqueue=%llu local_insert=%llu shared_insert=%llu dispatch=%llu running=%llu stopping=%llu\n"
		"runtime_ns=%llu queue_wait_ns=%llu migrations=%llu tracked_current=%llu tracked_peak=%llu completed_tasks=%llu\n"
		"failures lookup=%llu update=%llu capacity=%llu cleanup=%llu tracking_state=%llu completed_record=%llu\n"
		"per_cpu_entries=%d report=%s\n",
		uts.release, start_timestamp, end_timestamp,
		exit_data->exit_record.kind, exit_data->exit_record.exit_code,
		exit_data->exit_record.reason, exit_data->exit_record.message,
		(unsigned long long)total.enqueue_count,
		(unsigned long long)total.direct_local_insertions,
		(unsigned long long)total.shared_dsq_insertions,
		(unsigned long long)total.dispatch_callbacks,
		(unsigned long long)total.running_callbacks,
		(unsigned long long)total.stopping_callbacks,
		(unsigned long long)total.runtime_ns,
		(unsigned long long)total.queue_wait_ns,
		(unsigned long long)total.migration_count,
		(unsigned long long)tracking.current_tracked_tasks,
		(unsigned long long)tracking.peak_tracked_tasks,
		(unsigned long long)tasks.count,
		(unsigned long long)total.task_lookup_failures,
		(unsigned long long)total.task_update_failures,
		(unsigned long long)total.task_capacity_failures,
		(unsigned long long)total.task_cleanup_failures,
		(unsigned long long)total.tracking_state_lookup_failures,
		(unsigned long long)total.completed_record_failures,
		cpu_count, json_path);
	fprintf(text, "phase_control enabled=%s client_tgid=%u last_client_tgid=%u "
		"latest_phase=%s latest_sequence=%" PRIu64 "\n",
		phase_control->enabled ? "true" : "false", phase_control->client_tgid,
		phase_control->last_client_tgid, phase_name(phase_control->latest_phase),
		(uint64_t)phase_control->latest_sequence);
	fprintf(text, "phase_uprobe enabled=%s target_tgid=%u marker_elf=%s "
		"active=%u phase=%s run_id=%llu call_id=%llu retry=%llu result=%lld\n",
		phase_uprobe->enabled ? "true" : "false", phase_uprobe->last_target_tgid,
		phase_uprobe->binary_path ?: "", uprobe_state.active,
		phase_name(uprobe_state.phase), (unsigned long long)uprobe_state.run_id,
		(unsigned long long)uprobe_state.call_id,
		(unsigned long long)uprobe_state.retry, (long long)uprobe_state.result);
	fprintf(text, "uprobe begin=%llu end=%llu unknown=%llu prefill=%llu decode=%llu mixed=%llu "
		"abi_fail=%llu read_fail=%llu unsupported=%llu stale_end=%llu update_fail=%llu filtered=%llu\n",
		(unsigned long long)uprobe_stats.begin_events,
		(unsigned long long)uprobe_stats.end_events,
		(unsigned long long)uprobe_stats.begin_unknown,
		(unsigned long long)uprobe_stats.begin_prefill,
		(unsigned long long)uprobe_stats.begin_decode,
		(unsigned long long)uprobe_stats.begin_mixed,
		(unsigned long long)uprobe_stats.abi_failures,
		(unsigned long long)uprobe_stats.user_read_failures,
		(unsigned long long)uprobe_stats.unsupported_phases,
		(unsigned long long)uprobe_stats.stale_end_events,
		(unsigned long long)uprobe_stats.map_update_failures,
		(unsigned long long)uprobe_stats.filtered_events);
	for (__u32 phase = 0; phase < LLAMA_PHASE_COUNT; phase++) {
		const struct llama_phase_observation *observation = &phase_observations[phase];

		fprintf(text, "phase=%s select_cpu=%llu enqueue=%llu running=%llu stopping=%llu\n",
			phase_name(phase),
			(unsigned long long)observation->select_cpu,
			(unsigned long long)observation->enqueue,
			(unsigned long long)observation->running,
			(unsigned long long)observation->stopping);
	}
	if (fclose(text)) {
		fprintf(stderr, "cannot finish instrumentation summary %s: %s\n", text_path,
			strerror(errno));
		error = -1;
	}
	text = NULL;
	printf("instrumentation: enqueue=%llu runtime_ns=%llu tracked_peak=%llu report=%s\n",
	       (unsigned long long)total.enqueue_count,
	       (unsigned long long)total.runtime_ns,
	       (unsigned long long)tracking.peak_tracked_tasks, directory);
out:
	if (json)
		fclose(json);
	if (text)
		fclose(text);
	free(per_cpu);
	return error;
}

static void print_status(struct bpf_map *stats_map,
			 struct bpf_map *phase_observation_map,
			 struct bpf_map *phase_uprobe_stats_map,
			 const struct phase_control *phase_control,
			 const struct phase_uprobe_control *phase_uprobe)
{
	struct llama_phase_observation observations[LLAMA_PHASE_COUNT];
	struct llama_uprobe_stats uprobe_stats;
	__u64 stats[2];

	if (!read_stats(stats_map, stats))
		printf("local=%llu shared=%llu\n",
		       (unsigned long long)stats[0],
		       (unsigned long long)stats[1]);
	if (collect_phase_observations(phase_observation_map, observations))
		memset(observations, 0, sizeof(observations));
	if (collect_uprobe_stats(phase_uprobe_stats_map, &uprobe_stats))
		memset(&uprobe_stats, 0, sizeof(uprobe_stats));
	printf("phase_client_tgid=%u phase=%s sequence=%" PRIu64
	       " observations UNKNOWN=%llu/%llu/%llu/%llu"
	       " PREFILL=%llu/%llu/%llu/%llu DECODE=%llu/%llu/%llu/%llu"
	       " MIXED=%llu/%llu/%llu/%llu\n",
	       phase_control->client_tgid, phase_name(phase_control->latest_phase),
	       (uint64_t)phase_control->latest_sequence,
	       (unsigned long long)observations[LLAMA_PHASE_UNKNOWN].select_cpu,
	       (unsigned long long)observations[LLAMA_PHASE_UNKNOWN].enqueue,
	       (unsigned long long)observations[LLAMA_PHASE_UNKNOWN].running,
	       (unsigned long long)observations[LLAMA_PHASE_UNKNOWN].stopping,
	       (unsigned long long)observations[LLAMA_PHASE_PREFILL].select_cpu,
	       (unsigned long long)observations[LLAMA_PHASE_PREFILL].enqueue,
	       (unsigned long long)observations[LLAMA_PHASE_PREFILL].running,
	       (unsigned long long)observations[LLAMA_PHASE_PREFILL].stopping,
	       (unsigned long long)observations[LLAMA_PHASE_DECODE].select_cpu,
	       (unsigned long long)observations[LLAMA_PHASE_DECODE].enqueue,
	       (unsigned long long)observations[LLAMA_PHASE_DECODE].running,
	       (unsigned long long)observations[LLAMA_PHASE_DECODE].stopping,
	       (unsigned long long)observations[LLAMA_PHASE_MIXED].select_cpu,
	       (unsigned long long)observations[LLAMA_PHASE_MIXED].enqueue,
	       (unsigned long long)observations[LLAMA_PHASE_MIXED].running,
	       (unsigned long long)observations[LLAMA_PHASE_MIXED].stopping);
	printf("phase_uprobe_tgid=%u begin=%llu end=%llu prefill=%llu decode=%llu mixed=%llu "
	       "abi_fail=%llu read_fail=%llu unsupported=%llu stale_end=%llu update_fail=%llu filtered=%llu\n",
	       phase_uprobe->target_tgid,
	       (unsigned long long)uprobe_stats.begin_events,
	       (unsigned long long)uprobe_stats.end_events,
	       (unsigned long long)uprobe_stats.begin_prefill,
	       (unsigned long long)uprobe_stats.begin_decode,
	       (unsigned long long)uprobe_stats.begin_mixed,
	       (unsigned long long)uprobe_stats.abi_failures,
	       (unsigned long long)uprobe_stats.user_read_failures,
	       (unsigned long long)uprobe_stats.unsupported_phases,
	       (unsigned long long)uprobe_stats.stale_end_events,
	       (unsigned long long)uprobe_stats.map_update_failures,
	       (unsigned long long)uprobe_stats.filtered_events);
	fflush(stdout);
}

int main(int argc, char **argv)
{
	enum {
		OPTION_PHASE_SOCKET = 1000,
		OPTION_PHASE_UID,
		OPTION_PHASE_UPROBE,
		OPTION_PHASE_REGISTER_SOCKET,
	};
	struct bpf_object *object = NULL;
	struct bpf_map *ops_map = NULL;
	struct bpf_map *stats_map = NULL;
	struct bpf_map *data_map = NULL;
	struct bpf_map *cpu_map = NULL;
	struct bpf_map *task_map = NULL;
	struct bpf_map *tracking_map = NULL;
	struct bpf_map *phase_state_map = NULL;
	struct bpf_map *phase_observation_map = NULL;
	struct bpf_map *phase_uprobe_config_map = NULL;
	struct bpf_map *phase_uprobe_stats_map = NULL;
	struct bpf_link *link = NULL;
	struct runtime_data exit_data = {};
	struct phase_control phase_control;
	struct phase_uprobe_control phase_uprobe;
	char output_dir[PATH_MAX];
	char start_timestamp[32];
	char end_timestamp[32];
	const char *requested_output = NULL;
	const char *phase_socket = NULL;
	const char *phase_uprobe_path = NULL;
	const char *phase_register_socket = NULL;
	uid_t phase_uid = 0;
	bool phase_uid_set = false;
	bool fifo = false;
	int option;
	int err = 0;
	__u32 key = 0;
	static const struct option long_options[] = {
		{ "output-dir", required_argument, NULL, 'o' },
		{ "phase-socket", required_argument, NULL, OPTION_PHASE_SOCKET },
		{ "phase-uid", required_argument, NULL, OPTION_PHASE_UID },
		{ "phase-uprobe", required_argument, NULL, OPTION_PHASE_UPROBE },
		{ "phase-register-socket", required_argument, NULL, OPTION_PHASE_REGISTER_SOCKET },
		{ "help", no_argument, NULL, 'h' },
		{ NULL, 0, NULL, 0 },
	};

	phase_control_init(&phase_control);
	phase_uprobe_init(&phase_uprobe);
	libbpf_set_print(libbpf_log);
	while ((option = getopt_long(argc, argv, "fvo:h", long_options, NULL)) != -1) {
		switch (option) {
		case 'f':
			fifo = true;
			break;
		case 'v':
			verbose = true;
			break;
		case 'o':
			requested_output = optarg;
			break;
		case OPTION_PHASE_SOCKET:
			phase_socket = optarg;
			break;
		case OPTION_PHASE_UPROBE:
			phase_uprobe_path = optarg;
			break;
		case OPTION_PHASE_REGISTER_SOCKET:
			phase_register_socket = optarg;
			break;
		case OPTION_PHASE_UID:
			if (parse_uid(optarg, &phase_uid)) {
				fprintf(stderr, "invalid --phase-uid value: %s\n", optarg);
				return EXIT_FAILURE;
			}
			phase_uid_set = true;
			break;
		default:
			usage(basename(argv[0]));
			return option != 'h';
		}
	}
	if (phase_socket && (phase_uprobe_path || phase_register_socket)) {
		fprintf(stderr, "legacy socket and semantic uprobe phase sources are mutually exclusive\n");
		return EXIT_FAILURE;
	}
	if (phase_socket && !phase_uid_set) {
		fprintf(stderr, "--phase-socket and --phase-uid must be specified together\n");
		return EXIT_FAILURE;
	}
	if (phase_uprobe_path || phase_register_socket) {
		if (!phase_uprobe_path || !phase_register_socket || !phase_uid_set) {
			fprintf(stderr, "--phase-uprobe, --phase-register-socket, and --phase-uid must be specified together\n");
			return EXIT_FAILURE;
		}
	} else if (phase_uid_set && !phase_socket) {
		fprintf(stderr, "--phase-uid requires a phase source\n");
		return EXIT_FAILURE;
	}
	iso_timestamp(start_timestamp);
	if (prepare_output_dir(requested_output, output_dir))
		return EXIT_FAILURE;
	signal(SIGINT, request_exit);
	signal(SIGTERM, request_exit);
	object = bpf_object__open_file(BPF_OBJECT_PATH, NULL);
	if (!object) {
		fprintf(stderr, "failed to open %s\n", BPF_OBJECT_PATH);
		err = -ENOENT;
		goto out;
	}
	{
		struct bpf_map *rodata_map = bpf_object__find_map_by_name(object, "llama_sc.rodata");
		if (!rodata_map || bpf_map__set_initial_value(rodata_map, &fifo, sizeof(fifo))) {
			fprintf(stderr, "failed to configure FIFO mode\n");
			err = -EINVAL;
			goto out;
		}
	}
	err = bpf_object__load(object);
	if (err) {
		fprintf(stderr, "failed to load BPF scheduler: %s\n", strerror(-err));
		goto out;
	}
	ops_map = bpf_object__find_map_by_name(object, "llama_simple_ops");
	stats_map = bpf_object__find_map_by_name(object, "stats");
	data_map = bpf_object__find_map_by_name(object, "llama_sc.data");
	cpu_map = bpf_object__find_map_by_name(object, "instrumentation_cpu_stats");
	task_map = bpf_object__find_map_by_name(object, "completed_task_stats");
	tracking_map = bpf_object__find_map_by_name(object, "tracking_state");
	phase_state_map = bpf_object__find_map_by_name(object, "phase_state");
	phase_observation_map = bpf_object__find_map_by_name(object, "phase_observations");
	phase_uprobe_config_map = bpf_object__find_map_by_name(object, "phase_uprobe_config");
	phase_uprobe_stats_map = bpf_object__find_map_by_name(object, "phase_uprobe_stats");
	if (!ops_map || !stats_map || !data_map || !cpu_map || !task_map ||
	    !tracking_map || !phase_state_map || !phase_observation_map ||
	    !phase_uprobe_config_map || !phase_uprobe_stats_map) {
		fprintf(stderr, "required BPF map is missing\n");
		err = -ENOENT;
		goto out;
	}
	link = bpf_map__attach_struct_ops(ops_map);
	if (!link) {
		err = -errno;
		fprintf(stderr, "failed to attach sched_ext ops: %s\n", strerror(errno));
		goto out;
	}
	if (phase_socket) {
		err = phase_control_open(&phase_control, phase_socket, phase_uid);
		if (err)
			goto out;
	}
	if (phase_uprobe_path) {
		err = phase_uprobe_open(&phase_uprobe, phase_register_socket, phase_uid,
			phase_uprobe_path);
		if (err)
			goto out;
	}
	{
		int64_t next_status = monotonic_ms();

		while (!exit_requested) {
			struct pollfd poll_fds[3];
			int socket_listener_index = -1;
			int uprobe_listener_index = -1;
			int client_index = -1;
			int poll_count = 0;
			int64_t now = monotonic_ms();
			int timeout;
			int poll_result;

			if (now >= next_status) {
				print_status(stats_map, phase_observation_map, phase_uprobe_stats_map,
					&phase_control, &phase_uprobe);
				next_status = now + STATUS_INTERVAL_MS;
			}
			if (phase_control.listener_fd >= 0) {
				socket_listener_index = poll_count;
				poll_fds[poll_count].fd = phase_control.listener_fd;
				poll_fds[poll_count].events = POLLIN;
				poll_fds[poll_count].revents = 0;
				poll_count++;
			}
			if (phase_uprobe.listener_fd >= 0) {
				uprobe_listener_index = poll_count;
				poll_fds[poll_count].fd = phase_uprobe.listener_fd;
				poll_fds[poll_count].events = POLLIN;
				poll_fds[poll_count].revents = 0;
				poll_count++;
			}
			if (phase_control.client_fd >= 0) {
				client_index = poll_count;
				poll_fds[poll_count].fd = phase_control.client_fd;
				poll_fds[poll_count].events = POLLIN;
				poll_fds[poll_count].revents = 0;
				poll_count++;
			}
			now = monotonic_ms();
			timeout = next_status > now ? (int)(next_status - now) : 0;
			poll_result = poll(poll_fds, (nfds_t)poll_count, timeout);
			if (poll_result < 0) {
				if (errno == EINTR)
					continue;
				fprintf(stderr, "phase control poll failed: %s\n", strerror(errno));
				err = -errno;
				break;
			}
			if (socket_listener_index >= 0 &&
			    (poll_fds[socket_listener_index].revents & POLLIN))
				phase_control_accept(&phase_control);
			if (uprobe_listener_index >= 0 &&
			    (poll_fds[uprobe_listener_index].revents & POLLIN))
				phase_uprobe_accept(&phase_uprobe, object,
					bpf_map__fd(phase_uprobe_config_map));
			if (client_index >= 0) {
				short events = poll_fds[client_index].revents;

				if (events & POLLIN)
					phase_control_handle_message(&phase_control,
						bpf_map__fd(phase_state_map));
				if (phase_control.client_fd >= 0 &&
				    (events & (POLLERR | POLLHUP | POLLNVAL)))
					phase_control_close_client(&phase_control,
						bpf_map__fd(phase_state_map));
			}
		}
	}
out:
	phase_control_close(&phase_control,
		phase_state_map ? bpf_map__fd(phase_state_map) : -1);
	phase_uprobe_close(&phase_uprobe,
		phase_uprobe_config_map ? bpf_map__fd(phase_uprobe_config_map) : -1);
	bpf_link__destroy(link);
	if (data_map && bpf_map_lookup_elem(bpf_map__fd(data_map), &key, &exit_data))
		memset(&exit_data, 0, sizeof(exit_data));
	iso_timestamp(end_timestamp);
	if (write_report(output_dir, start_timestamp, end_timestamp, cpu_map, task_map,
			 tracking_map, phase_state_map, phase_observation_map,
			 phase_uprobe_stats_map, &phase_control, &phase_uprobe, &exit_data))
		err = err ?: -EIO;
	if (exit_data.exit_record.reason[0]) {
		fprintf(stderr, "sched_ext exit: %s (%s)\n", exit_data.exit_record.reason,
			exit_data.exit_record.message);
		if (exit_data.exit_dump[0])
			fprintf(stderr, "sched_ext dump:\n%s\n", exit_data.exit_dump);
	}
	bpf_object__close(object);
	return err ? EXIT_FAILURE : EXIT_SUCCESS;
}
