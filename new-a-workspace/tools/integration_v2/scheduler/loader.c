/* SPDX-License-Identifier: GPL-2.0 */
#define _GNU_SOURCE
#include <bpf/bpf.h>
#include <bpf/libbpf.h>
#include "new_a.h"
#include "state-receiver.h"
#include "guard_domain.h"
#include "identity.h"

static const char *topology_path;
static int new_a_object_load(struct bpf_object *object);

#ifdef NEW_A_DIAGNOSTICS
static const char *diagnostics_path;
static int diagnostics_fd = -1;
static int events_fd = -1;
static unsigned int mask_cpu_limit;
#endif

/* Keep the Frozen loader source and lifecycle byte-for-byte unchanged. */
static int analysis_monitor(void);
#define main neutral_loader_main
#define bpf_object__load new_a_object_load
#include "neutral_lifecycle.c"
#undef bpf_object__load
#undef main

#include "monitor.h"
#include "handoff-loader.h"

#ifdef NEW_A_DIAGNOSTICS
#include "mask_dump.h"
#endif

static int new_a_object_load(struct bpf_object *object)
{
	struct new_a_topology topology;
	struct bpf_map *map = bpf_object__find_map_by_name(object, "new_a_topology");
	bool seen[NEW_A_MAX_CPUS] = {};
	FILE *input = fopen(topology_path, "rb");
	__u32 key = 0;
	int error;
#ifdef NEW_A_DIAGNOSTICS
	char possible[NEW_A_MAX_CPUS * 6];
	FILE *cpu_input;
	struct new_a_diagnostic_config config;
#endif

	if (!input)
		return -errno;
	if (fread(&topology, 1, sizeof(topology), input) != sizeof(topology) || fgetc(input) != EOF || ferror(input)) {
		fclose(input);
		return -EINVAL;
	}
	fclose(input);
	if (!map || bpf_map__value_size(map) != sizeof(topology) || topology.magic != NEW_A_MAGIC || topology.enabled > 1)
		return -EINVAL;
	for (unsigned int tier = 0; tier < 3; tier++) {
		if (topology.count[tier] > NEW_A_MAX_CPUS)
			return -EINVAL;
		for (unsigned int i = 0; i < topology.count[tier]; i++) {
			__u32 cpu = topology.cpus[tier][i];

			if (cpu >= NEW_A_MAX_CPUS || seen[cpu] || !topology.enabled || !ug.selected[cpu])
				return -EINVAL;
			seen[cpu] = true;
		}
	}
    if (ug_current() || !topology.enabled || !topology.count[0])
        return -EINVAL;
    for (int cpu = 0; cpu < NEW_A_MAX_CPUS; cpu++) {
        if (ug.selected[cpu] != seen[cpu])
            return -EINVAL;
    }
#ifdef NEW_A_DIAGNOSTICS
	cpu_input = fopen("/sys/devices/system/cpu/possible", "r");
	if (!cpu_input)
		return -errno;
	error = fgets(possible, sizeof(possible), cpu_input) && fgetc(cpu_input) == EOF && !ferror(cpu_input) ? 0 : -EINVAL;
	if (!error)
		error = new_a_parse_mask_limit(possible, &mask_cpu_limit);
	fclose(cpu_input);
	if (error)
		return error;
	config.mask_bits = mask_cpu_limit;
#endif
	if (analysis_kernel_open()) return -EUCLEAN;
	error = bpf_object__load(object);
	if (error)
		return error;
	error = handoff_prepare(object);
	if (error)
		return error;
	if (bpf_map_update_elem(bpf_map__fd(map), &key, &topology, BPF_ANY))
		return -errno;
#ifdef NEW_A_DIAGNOSTICS
	map = bpf_object__find_map_by_name(object, "new_a_diagnostic_config");
	if (!map || bpf_map__value_size(map) != sizeof(config) ||
	    bpf_map_update_elem(bpf_map__fd(map), &key, &config, BPF_ANY))
		return -EINVAL;
	map = bpf_object__find_map_by_name(object, "new_a_stats");
	if (!map || (diagnostics_fd = fcntl(bpf_map__fd(map), F_DUPFD_CLOEXEC, 0)) < 0)
		return -EINVAL;
	map = bpf_object__find_map_by_name(object, "new_a_events");
	if (!map || (events_fd = fcntl(bpf_map__fd(map), F_DUPFD_CLOEXEC, 0)) < 0)
		return -EINVAL;
#endif
	fprintf(stderr, "NEW_A: enabled=%u tiers=%u/%u/%u; placement policy=" HANDOFF_MODE "\n",
		topology.enabled, topology.count[0], topology.count[1], topology.count[2]);
	return 0;
}

#ifdef NEW_A_DIAGNOSTICS
static int export_events(FILE *output, int count)
{
	struct new_a_event *events = calloc((size_t)count, sizeof(*events));
	bool comma = false;
	int result = 0;

	_Static_assert(sizeof(struct new_a_event) % 8 == 0, "per-CPU event stride");
	if (!events || events_fd < 0) {
		free(events);
		return -ENOMEM;
	}
	fprintf(output, ",\"event_schema\":2,\"mask_cpu_limit\":%u,\"kernel_clock\":\"bpf_ktime_get_ns\",\"events\":[", mask_cpu_limit);
	for (__u32 key = 0; key < NEW_A_EVENT_CAPACITY; key++) {
		if (bpf_map_lookup_elem(events_fd, &key, events)) {
			result = -errno;
			break;
		}
		for (int slot = 0; slot < count; slot++) {
			const struct new_a_event *e = &events[slot];

			if (!e->timestamp_ns)
				continue;
			fprintf(output, "%s{\"timestamp_ns\":%llu,\"sequence\":%u,\"kind\":%u,\"callback\":%u,\"tgid\":%u,\"tid\":%u,\"task_start_time\":%llu,\"actor_tgid\":%u,\"actor_tid\":%u,\"callback_cpu\":%u,\"task_cpu\":%d,\"nr_cpus_allowed\":%u,\"migration_disabled\":%u,\"migration_pending\":%u,\"on_cpu\":%u,\"on_rq\":%u,\"mask_bits\":%u,\"allowed_weight\":%u,\"regular_weight\":%u,\"requested_weight\":%u,\"allowed_read_error\":%d,\"regular_read_error\":%d,\"requested_read_error\":%d,\"callback_allowed\":%d,\"task_allowed\":%d,\"allowed_cpus\":",
				comma ? "," : "", (unsigned long long)e->timestamp_ns, e->sequence, e->kind, e->callback, e->tgid, e->tid,
				(unsigned long long)e->task_start_time, (__u32)(e->actor_pid_tgid >> 32), (__u32)e->actor_pid_tgid,
				e->callback_cpu, e->task_cpu, e->nr_cpus_allowed, e->migration_disabled, e->migration_pending,
				e->on_cpu, e->on_rq, e->mask_bits, e->allowed_weight, e->regular_weight, e->requested_weight,
				e->allowed_read_error, e->regular_read_error, e->requested_read_error, e->callback_allowed, e->task_allowed);
			unsigned int bits = e->mask_bits < mask_cpu_limit ? e->mask_bits : mask_cpu_limit;

			new_a_print_mask(output, e->allowed, bits);
			fprintf(output, ",\"regular_cpus\":");
			new_a_print_mask(output, e->regular, bits);
			fprintf(output, ",\"requested_cpus\":");
			new_a_print_mask(output, e->requested, bits);
			fprintf(output, ",\"allowed_complete\":%s,\"regular_complete\":%s,\"requested_complete\":%s}",
				e->mask_bits == mask_cpu_limit && new_a_mask_complete(e->allowed, bits, e->allowed_weight, e->allowed_read_error) ? "true" : "false",
				e->mask_bits == mask_cpu_limit && new_a_mask_complete(e->regular, bits, e->regular_weight, e->regular_read_error) ? "true" : "false",
				e->kind == NEW_A_EVENT_SET_CPUMASK && e->mask_bits == mask_cpu_limit &&
				new_a_mask_complete(e->requested, bits, e->requested_weight, e->requested_read_error) ? "true" : "false");
			comma = true;
		}
	}
	fprintf(output, "],\"events_export_error\":%d", result);
	free(events);
	return result;
}
#endif

int main(int argc, char **argv)
{
	int result;

	if (argc == 2 && (!strcmp(argv[1], "--help") || !strcmp(argv[1], "-h"))) {
		fprintf(stderr, "NEW_A: --guard-config FILE --topology FILE --diagnostics-output FILE before phase arguments.\n");
		usage(argv[0]);
		return 0;
	}
    if (argc < 8 || strcmp(argv[1], "--guard-config") || ug_load(argv[2]) ||
        strcmp(argv[3], "--topology")) {
        fprintf(stderr, "NEW_A: invalid or stale guard/topology input\n");
        return EXIT_FAILURE;
    }
    char *program_name = argv[0];
    argc -= 2;
    argv += 2;
    argv[0] = program_name;
	topology_path = argv[2];

#ifdef NEW_A_DIAGNOSTICS
	if (argc < 6 || strcmp(argv[3], "--diagnostics-output")) {
		fprintf(stderr, "diagnostic loader requires --diagnostics-output FILE after --topology FILE\n");
		return EXIT_FAILURE;
	}
	diagnostics_path = argv[4];
	argv[4] = argv[0];
	result = neutral_loader_main(argc - 4, argv + 4);
	if (diagnostics_fd >= 0 && analysis_monitor()) result = EXIT_FAILURE;
	if (diagnostics_fd >= 0) {
		int count = libbpf_num_possible_cpus();
		struct new_a_stats *stats = count > 0 ? calloc((size_t)count, sizeof(*stats)) : NULL;
		__u32 key = 0;
		FILE *output = NULL;

		if (!stats || bpf_map_lookup_elem(diagnostics_fd, &key, stats) ||
		    !(output = fopen(diagnostics_path, "wx"))) {
			fprintf(stderr, "NEW_A diagnostic export failed\n");
			result = EXIT_FAILURE;
		} else {
#ifdef FG_GUARD
            fprintf(output, "{\"instrumentation_mode\":\"GUARD_NO_DETAIL\",\"optional_metrics\":{\"runtime_ns\":\"NOT_AVAILABLE\",\"migrations\":\"NOT_AVAILABLE\"},\"cpus\":[");
#elif defined(NEW_A_RUNTIME_LITE)
            fprintf(output, "{\"instrumentation_mode\":\"LITE\",\"optional_metrics\":{\"runtime_ns\":\"NOT_AVAILABLE\",\"migrations\":\"COLLECTED\"},\"cpus\":[");
#else
            fprintf(output, "{\"instrumentation_mode\":\"FULL\",\"optional_metrics\":{\"runtime_ns\":\"COLLECTED\",\"migrations\":\"COLLECTED\"},\"cpus\":[");
#endif
            for (int cpu = 0; cpu < count; cpu++) {
                struct new_a_stats *s = &stats[cpu];
                fprintf(output, "%s{\"cpu\":%d,\"selected\":[%llu,%llu,%llu,%llu],\"running\":%llu,\"stopping\":%llu",
                    cpu ? "," : "", analysis_possible_ids[cpu], (unsigned long long)s->selected[0], (unsigned long long)s->selected[1],
                    (unsigned long long)s->selected[2], (unsigned long long)s->selected[3],
                    (unsigned long long)s->running, (unsigned long long)s->stopping);
#ifdef FG_GUARD
                fprintf(output, ",\"runtime_ns\":\"NOT_AVAILABLE\",\"migrations\":\"NOT_AVAILABLE\"");
#elif defined(NEW_A_RUNTIME_LITE)
                fprintf(output, ",\"runtime_ns\":\"NOT_AVAILABLE\",\"migrations\":%llu", (unsigned long long)s->migrations);
#else
                fprintf(output, ",\"runtime_ns\":%llu,\"migrations\":%llu", (unsigned long long)s->runtime_ns, (unsigned long long)s->migrations);
#endif
                fprintf(output, ",\"mask_violations\":%llu,\"tracking_failures\":%llu,\"phase_seen\":%llu,\"events_attempted\":%llu,\"events_dropped\":%llu}",
                    (unsigned long long)s->mask_violations, (unsigned long long)s->tracking_failures,
                    (unsigned long long)s->phase_seen, (unsigned long long)s->events_attempted, (unsigned long long)s->events_dropped);
            }
			fputc(']', output);
			analysis_monitor_export(output);
			if (export_events(output, count))
				result = EXIT_FAILURE;
			if (handoff_export(output))
				result = EXIT_FAILURE;
			fprintf(output, "}\n");
			if (fclose(output))
				result = EXIT_FAILURE;
		}
		free(stats);
		close(diagnostics_fd);
	}
	if (events_fd >= 0)
		close(events_fd);
#else
	argv[2] = argv[0];
	result = neutral_loader_main(argc - 2, argv + 2);
#endif
	if (handoff_fd >= 0) close(handoff_fd);
	analysis_monitor_close();
    free(universal_object_bytes);
	return result;
}
