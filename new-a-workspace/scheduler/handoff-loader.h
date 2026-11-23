/* SPDX-License-Identifier: GPL-2.0 */
struct handoff_counters { __u64 attempts[4]; __u64 moved[4]; };
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
        }
    free(rows);
    fprintf(output, ",\"idle_handoff\":{\"mode\":\"" HANDOFF_MODE "\",\"attempts\":[%llu,%llu,%llu,%llu],\"moved\":[%llu,%llu,%llu,%llu]}",
        (unsigned long long)total.attempts[0], (unsigned long long)total.attempts[1],
        (unsigned long long)total.attempts[2], (unsigned long long)total.attempts[3],
        (unsigned long long)total.moved[0], (unsigned long long)total.moved[1],
        (unsigned long long)total.moved[2], (unsigned long long)total.moved[3]);
    return 0;
}
