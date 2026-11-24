/* SPDX-License-Identifier: GPL-2.0 */
#ifndef FG_MONITOR_H
#define FG_MONITOR_H
#include <time.h>

struct fg_kernel_record { unsigned int priority; unsigned long long sequence; const char *message; int bad; };
static int fg_parse_kernel_record(const char *text, struct fg_kernel_record *record)
{
    unsigned long long timestamp;
    const char *message = strchr(text, ';');
    if (!message || sscanf(text, "%u,%llu,%llu,", &record->priority, &record->sequence, &timestamp) != 3)
        return -EINVAL;
    record->message = message + 1;
    record->bad = (record->priority >> 3) == 0 &&
        ((record->priority & 7) <= 3 || strstr(record->message, "BUG:") ||
         strstr(record->message, "WARNING:") || strstr(record->message, "Oops:") ||
         strstr(record->message, "Call Trace:") || strstr(record->message, "soft lockup") ||
         strstr(record->message, "hard LOCKUP") || strstr(record->message, "rcu_preempt detected stalls"));
    return 0;
}
#ifndef FG_PARSER_ONLY
static int analysis_kernel_fd = -1;
static int analysis_kernel_opened;
static int analysis_count;
static struct new_a_stats *analysis_rows;
static unsigned long long analysis_samples, analysis_failures, analysis_kernel_records, analysis_last_sequence;
static int analysis_have_sequence;

static int analysis_fail(const char *reason)
{
    if (!analysis_failures)
        fprintf(stderr, "FULL_GUARD_MONITOR_FAILED: %s\n", reason);
    analysis_failures++;
    return -EUCLEAN;
}
static int analysis_kernel_open(void)
{
    analysis_kernel_fd = open("/dev/kmsg", O_RDONLY | O_NONBLOCK | O_CLOEXEC);
    if (analysis_kernel_fd < 0)
        return analysis_fail("cannot open read-only /dev/kmsg");
    if (lseek(analysis_kernel_fd, 0, SEEK_END) < 0)
        return analysis_fail("cannot seek kernel-log cursor");
    analysis_kernel_opened = 1;
    return 0;
}
static int analysis_kernel_check(void)
{
    static char buffer[65536];
    for (int records = 0; records < 4096; records++) {
        struct fg_kernel_record record;
        ssize_t size = read(analysis_kernel_fd, buffer, sizeof(buffer) - 1);
        if (size < 0 && errno == EINTR) continue;
        if (size < 0 && errno == EAGAIN) return 0;
        if (size <= 0) return analysis_fail("kernel-log read failed or records lost");
        buffer[size] = 0;
        if (fg_parse_kernel_record(buffer, &record)) return analysis_fail("invalid kernel-log record");
        if (analysis_have_sequence && record.sequence != analysis_last_sequence + 1)
            return analysis_fail("kernel-log sequence gap");
        analysis_have_sequence = 1;
        analysis_last_sequence = record.sequence;
        analysis_kernel_records++;
        fprintf(stderr, "FULL_GUARD_KERNEL_RECORD: %s", buffer);
        if (record.bad) return analysis_fail("new kernel error/warning; see raw record");
    }
    return analysis_fail("kernel-log flood; stop rather than lose coverage");
}
static int analysis_cpu_allowed(int cpu)
{
    return cpu >= 0 && cpu < NEW_A_MAX_CPUS && ug.selected[cpu];
}
static int analysis_monitor(void)
{
    __u32 key = 0;
    if (ug_current()) return analysis_fail("owner or topology changed");
    if (analysis_failures) return -EUCLEAN;
    if (!analysis_kernel_opened || analysis_kernel_check()) return analysis_fail("kernel monitoring unavailable");
    if (diagnostics_fd < 0) return analysis_fail("diagnostic map unavailable");
    if (!analysis_rows) {
        analysis_count = libbpf_num_possible_cpus();
        if (analysis_count <= 0 || (unsigned int)analysis_count != ug.count) return analysis_fail("possible CPU domain changed");
        analysis_rows = calloc((size_t)analysis_count, sizeof(*analysis_rows));
        if (!analysis_rows) return analysis_fail("monitor allocation failed");
    }
    if (bpf_map_lookup_elem(diagnostics_fd, &key, analysis_rows)) return analysis_fail("live diagnostics read failed");
    for (int cpu = 0; cpu < analysis_count; cpu++) {
        const struct new_a_stats *s = &analysis_rows[cpu];
        if (s->mask_violations || s->tracking_failures || s->events_dropped)
            return analysis_fail("Mask/Tracking/export failure; no transition exception");
        if (!analysis_cpu_allowed(analysis_possible_ids[cpu]) && (s->running || s->stopping || s->runtime_ns))
            return analysis_fail("execution outside prepared CPU set");
#ifdef FG_GUARD
        if (s->runtime_ns || s->migrations) return analysis_fail("guard optional counters unexpectedly active");
#endif
    }
    analysis_samples++;
    return 0;
}
static void analysis_monitor_export(FILE *output)
{
    fprintf(output, ",\"live_monitor\":{\"samples\":%llu,\"failures\":%llu,\"kernel_opened\":%s,\"kernel_records\":%llu,\"poll_seconds\":1,\"status\":\"%s\"}",
        analysis_samples, analysis_failures, analysis_kernel_opened ? "true" : "false", analysis_kernel_records,
        analysis_samples && !analysis_failures ? "PASS" : "FAIL");
}
static void analysis_monitor_close(void)
{
    free(analysis_rows);
    if (analysis_kernel_fd >= 0) close(analysis_kernel_fd);
}
#endif
#endif
