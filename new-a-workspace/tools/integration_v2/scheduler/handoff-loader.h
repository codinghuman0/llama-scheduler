/* SPDX-License-Identifier: GPL-2.0 */
#include "handoff-policy.h"
static int handoff_fd = -1;
#ifdef NEW_A_PREFILL_PAIR
static struct newa_dispatch_topology installed_placement;

static void print_phase_counts(FILE *output, const __u64 counts[4])
{
    fprintf(output, "[%llu,%llu,%llu,%llu]", counts[0], counts[1], counts[2], counts[3]);
}
#endif
static int handoff_prepare(struct bpf_object *object)
{
    struct bpf_map *map = bpf_object__find_map_by_name(object, "handoff_stats");
    if (!map || bpf_map__value_size(map) != sizeof(struct handoff_counters))
        return -EINVAL;
    int fd = bpf_map__fd(map);
    if (fd < 0)
        return fd;
    handoff_fd = fcntl(fd, F_DUPFD_CLOEXEC, 0);
    return handoff_fd < 0 ? -errno : 0;
}
static int handoff_export(FILE *output)
{
    __u32 key = 0;
    int count = libbpf_num_possible_cpus();
    if (count <= 0 || count > NEW_A_MAX_CPUS || handoff_fd < 0)
        return -EINVAL;
    struct handoff_counters *rows = calloc((size_t)count, sizeof(*rows));
    if (!rows)
        return -ENOMEM;
    if (bpf_map_lookup_elem(handoff_fd, &key, rows)) {
        free(rows);
        return -EIO;
    }
    struct handoff_counters total = {};
    for (int cpu = 0; cpu < count; cpu++)
        for (int phase = 0; phase < 4; phase++) {
            total.attempts[phase] += rows[cpu].attempts[phase];
            total.moved[phase] += rows[cpu].moved[phase];
            total.locality_attempts[phase] += rows[cpu].locality_attempts[phase];
            total.locality_hits[phase] += rows[cpu].locality_hits[phase];
#ifdef NEW_A_PREFILL_PAIR
            total.prefill_attempts[phase] += rows[cpu].prefill_attempts[phase];
            total.prefill_hits[phase] += rows[cpu].prefill_hits[phase];
#endif
        }
#ifdef NEW_A_PREFILL_PAIR
    fputs(",\"prefill_pcore\":{\"p_representatives\":[", output);
    for (__u32 i = 0; i < installed_placement.prefill_pcore_count; i++)
        fprintf(output, "%s%u", i ? "," : "", installed_placement.tiers.cpus[0][i]);
    fputs("],\"attempts\":", output);
    print_phase_counts(output, total.prefill_attempts);
    fputs(",\"hits\":", output);
    print_phase_counts(output, total.prefill_hits);
#ifdef NEW_A_RUNTIME_LITE
    fputs(",\"running_starts_by_cpu\":null}", output);
#else
    fputs(",\"running_starts_by_cpu\":[", output);
    for (int cpu = 0; cpu < count; cpu++) {
        fprintf(output, "%s{\"cpu\":%d,\"by_phase\":", cpu ? "," : "", analysis_possible_ids[cpu]);
        print_phase_counts(output, rows[cpu].running_starts);
        fputc('}', output);
    }
    fputs("]}", output);
#endif
#endif
    free(rows);
    fprintf(output, ",\"idle_handoff\":{\"mode\":\"" HANDOFF_MODE "\",\"attempts\":[%llu,%llu,%llu,%llu],\"moved\":[%llu,%llu,%llu,%llu]}",
        (unsigned long long)total.attempts[0], (unsigned long long)total.attempts[1],
        (unsigned long long)total.attempts[2], (unsigned long long)total.attempts[3],
        (unsigned long long)total.moved[0], (unsigned long long)total.moved[1],
        (unsigned long long)total.moved[2], (unsigned long long)total.moved[3]);
    fprintf(output, ",\"locality\":{\"attempts\":[%llu,%llu,%llu,%llu],\"hits\":[%llu,%llu,%llu,%llu]}",
        (unsigned long long)total.locality_attempts[0], (unsigned long long)total.locality_attempts[1],
        (unsigned long long)total.locality_attempts[2], (unsigned long long)total.locality_attempts[3],
        (unsigned long long)total.locality_hits[0], (unsigned long long)total.locality_hits[1],
        (unsigned long long)total.locality_hits[2], (unsigned long long)total.locality_hits[3]);
    return 0;
}
