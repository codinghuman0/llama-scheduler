/* SPDX-License-Identifier: GPL-2.0 */
/* Direct-libBPF loader compatible with the installed libbpf 1.3.0. */
#include <errno.h>
#include <getopt.h>
#include <libgen.h>
#include <signal.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include <bpf/bpf.h>
#include <bpf/libbpf.h>

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
		"Usage: %s [-f] [-v]\n"
		"  -f  preserve scx_simple FIFO mode (default is weighted vtime)\n"
		"  -v  print libbpf debug output\n"
		"  -h  show this help\n",
		program);
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

int main(int argc, char **argv)
{
	struct bpf_object *object = NULL;
	struct bpf_map *ops_map = NULL;
	struct bpf_map *stats_map = NULL;
	struct bpf_map *rodata_map = NULL;
	struct bpf_map *data_map = NULL;
	struct bpf_link *link = NULL;
	struct runtime_data exit_data = {};
	bool fifo = false;
	int option;
	int err = 0;
	__u32 key = 0;

	libbpf_set_print(libbpf_log);
	while ((option = getopt(argc, argv, "fvh")) != -1) {
		switch (option) {
		case 'f':
			fifo = true;
			break;
		case 'v':
			verbose = true;
			break;
		default:
			usage(basename(argv[0]));
			return option != 'h';
		}
	}

	signal(SIGINT, request_exit);
	signal(SIGTERM, request_exit);
	object = bpf_object__open_file(BPF_OBJECT_PATH, NULL);
	if (!object) {
		fprintf(stderr, "failed to open %s\n", BPF_OBJECT_PATH);
		return EXIT_FAILURE;
	}
	rodata_map = bpf_object__find_map_by_name(object, "llama_sc.rodata");
	if (!rodata_map || bpf_map__set_initial_value(rodata_map, &fifo, sizeof(fifo))) {
		fprintf(stderr, "failed to configure FIFO mode\n");
		err = -EINVAL;
		goto out;
	}
	err = bpf_object__load(object);
	if (err) {
		fprintf(stderr, "failed to load BPF scheduler: %s\n", strerror(-err));
		goto out;
	}
	ops_map = bpf_object__find_map_by_name(object, "llama_simple_ops");
	stats_map = bpf_object__find_map_by_name(object, "stats");
	data_map = bpf_object__find_map_by_name(object, "llama_sc.data");
	if (!ops_map || !stats_map || !data_map) {
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
	if (exit_data.exit_record.reason[0]) {
		fprintf(stderr, "sched_ext exit: %s (%s)\n", exit_data.exit_record.reason,
			exit_data.exit_record.message);
		if (exit_data.exit_dump[0])
			fprintf(stderr, "sched_ext dump:\n%s\n", exit_data.exit_dump);
	}
	bpf_object__close(object);
	return err ? EXIT_FAILURE : EXIT_SUCCESS;
}
