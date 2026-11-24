/* SPDX-License-Identifier: GPL-2.0 */
#include "handoff-policy.h"
static int handoff_fd = -1;
static int handoff_prepare(struct bpf_object *object)
{
    int fd = bpf_object__find_map_fd_by_name(object, "handoff_stats");
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
        }
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
