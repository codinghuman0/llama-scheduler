/* SPDX-License-Identifier: GPL-2.0 */
/* Direct-libBPF loader compatible with the installed libbpf 1.3.0. */
#include <errno.h>
#include <getopt.h>
#include <libgen.h>
#include <limits.h>
#include <signal.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/utsname.h>
#include <time.h>
#include <unistd.h>

#include <linux/types.h>
#include <bpf/bpf.h>
#include <bpf/libbpf.h>

#include "llama_instrumentation.h"

#define BPF_OBJECT_PATH "build/llama_scx_simple.bpf.o"
#define EXIT_DUMP_LEN 32768

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
		"Usage: %s [-f] [-v] [-o DIRECTORY]\n"
		"  -f  preserve scx_simple FIFO mode (default is weighted vtime)\n"
		"  -v  print libbpf debug output\n"
		"  -o  create this empty instrumentation output directory\n"
		"  -h  show this help\n",
		program);
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
			const struct runtime_data *exit_data)
{
	char json_path[PATH_MAX];
	char text_path[PATH_MAX];
	struct utsname uts = {};
	struct llama_cpu_stats *per_cpu = NULL;
	struct llama_cpu_stats total;
	struct llama_tracking_state tracking;
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
	fputs("},\n  \"aggregate\": {", json);
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

int main(int argc, char **argv)
{
	struct bpf_object *object = NULL;
	struct bpf_map *ops_map = NULL;
	struct bpf_map *stats_map = NULL;
	struct bpf_map *data_map = NULL;
	struct bpf_map *cpu_map = NULL;
	struct bpf_map *task_map = NULL;
	struct bpf_map *tracking_map = NULL;
	struct bpf_link *link = NULL;
	struct runtime_data exit_data = {};
	char output_dir[PATH_MAX];
	char start_timestamp[32];
	char end_timestamp[32];
	const char *requested_output = NULL;
	bool fifo = false;
	int option;
	int err = 0;
	__u32 key = 0;
	static const struct option long_options[] = {
		{ "output-dir", required_argument, NULL, 'o' },
		{ "help", no_argument, NULL, 'h' },
		{ NULL, 0, NULL, 0 },
	};

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
		default:
			usage(basename(argv[0]));
			return option != 'h';
		}
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
	if (!ops_map || !stats_map || !data_map || !cpu_map || !task_map || !tracking_map) {
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
	while (!exit_requested) {
		__u64 stats[2];

		if (!read_stats(stats_map, stats))
			printf("local=%llu shared=%llu\n",
			       (unsigned long long)stats[0],
			       (unsigned long long)stats[1]);
		fflush(stdout);
		sleep(1);
	}
out:
	bpf_link__destroy(link);
	if (data_map && bpf_map_lookup_elem(bpf_map__fd(data_map), &key, &exit_data))
		memset(&exit_data, 0, sizeof(exit_data));
	iso_timestamp(end_timestamp);
	if (write_report(output_dir, start_timestamp, end_timestamp, cpu_map, task_map,
			 tracking_map, &exit_data))
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
