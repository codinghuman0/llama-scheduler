#pragma once
#include "llama.h"
#include "server-phase.h"
#include <array>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <sched.h>
#include <stdexcept>
#include <time.h>
#include <unistd.h>

// CPU-only research overlay. The public interface matches the retained server hook.
// No token values, request answers, condition names, or previous-cohort learning are used.
class newa_decode_policy {
#ifdef NEWA_PREFILL_PRESSURE_TEST
    friend struct newa_prefill_pressure_test;
#endif
    enum class mode { off, pressure, fixed6, fixed5 } policy = mode::off;
    static constexpr long long min_call_ns = 1000000000LL;
    static constexpr long long max_read_ns = 20000000LL;
    static constexpr long long max_start_age_ns = 10000000000LL;
    static constexpr unsigned max_decode_calls = 256;
    static constexpr double threshold = .125, accounting_margin = .02;
    struct snapshot {
        long long wall_first = 0, wall_last = 0, cpu_first = 0, cpu_last = 0;
        unsigned long long task_ticks = 0;
        bool ok = false;
        unsigned long long fields[6][3] = {};
    };
    struct observation {
        snapshot before, after;
        long long model_start = 0, model_end = 0;
        int n_tokens = 0;
        bool captured = false, counters_valid = false, usable = false;
        double wall_s = 0, task_cpu_s = 0, own_cpu_upper_s = 0, rounding_cpu_s = 0, score = 0;
        int shadow_choice = 6;
    };
    struct member {
        int task = -1, slot = -1, first_position = -1, last_position = -1;
        bool prefill_seen = false;
    };
    struct epoch {
        std::array<member, 8> members{};
        unsigned member_count = 0, active_mask = 0, eligible_calls = 0;
        bool active = false, locked = false, invalidated = false;
        int reason = 0;
        long long first_decode_ns = 0, sample_age_ns = 0;
        unsigned long long calls = 0, decisions[4][2] = {}, eligible_by_size[9][2] = {};
        observation sample;
    } current, proposed;
    std::array<epoch, 16> reports{};
    std::array<int, 6> cpus{};
    unsigned report_count = 0, reports_dropped = 0, failures = 0, read_errors = 0;
    long ticks_per_second = 0;
    bool selected = false, begun = false, capture = false;

    static long long wall_ns() {
        return std::chrono::duration_cast<std::chrono::nanoseconds>(
            std::chrono::steady_clock::now().time_since_epoch()).count();
    }
    static bool cpu_ns(long long & result) {
        timespec value{};
        if (clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &value)) return false;
        result = (long long)value.tv_sec * 1000000000LL + value.tv_nsec;
        return true;
    }
    snapshot sample_cpu() const {
        snapshot result;
        result.wall_first = wall_ns();
        bool ok = cpu_ns(result.cpu_first);
        unsigned seen = 0;
        FILE * file = std::fopen("/proc/stat", "r");
        if (!file) ok = false;
        else {
            char line[1024];
            while (std::fgets(line, sizeof(line), file)) {
                if (std::strncmp(line, "cpu", 3) || line[3] < '0' || line[3] > '9') continue;
                int cpu;
                unsigned long long user, nice, system;
                if (std::sscanf(line, "cpu%d %llu %llu %llu", &cpu, &user, &nice, &system) != 4) {
                    ok = false; break;
                }
                for (unsigned i = 0; i < cpus.size(); ++i) {
                    if (cpu != cpus[i]) continue;
                    if (seen & (1U << i)) ok = false;
                    seen |= 1U << i;
                    result.fields[i][0] = user;
                    result.fields[i][1] = nice;
                    result.fields[i][2] = system;
                    result.task_ticks += user + nice + system;
                }
            }
            if (std::ferror(file)) ok = false;
            if (std::fclose(file)) ok = false;
        }
        ok = cpu_ns(result.cpu_last) && ok;
        result.wall_last = wall_ns();
        result.ok = ok && seen == 63 && result.wall_last >= result.wall_first &&
                    result.wall_last - result.wall_first <= max_read_ns && result.cpu_last >= result.cpu_first;
        return result;
    }
    void evaluate(observation & value) const {
        const auto & a = value.before;
        const auto & b = value.after;
        value.counters_valid = a.ok && b.ok && b.wall_first >= a.wall_last &&
            b.cpu_first >= a.cpu_last && b.task_ticks >= a.task_ticks && value.model_start >= a.wall_last &&
            value.model_end >= value.model_start && b.wall_first >= value.model_end;
        for (unsigned i = 0; i < cpus.size(); ++i)
            for (unsigned j = 0; j < 3; ++j)
                value.counters_valid &= b.fields[i][j] >= a.fields[i][j];
        if (!value.counters_valid) return;
        value.wall_s = (b.wall_last - a.wall_first) / 1e9;
        value.task_cpu_s = (b.task_ticks - a.task_ticks) / (double)ticks_per_second;
        value.own_cpu_upper_s = (b.cpu_last - a.cpu_first) / 1e9;
        // One truncation-difference tick per CPU per user/nice/system field.
        // This operational margin is not a confidence interval or a universal accounting bound.
        value.rounding_cpu_s = 3.0 * cpus.size() / ticks_per_second;
        value.counters_valid = value.wall_s > 0 && value.own_cpu_upper_s >= 0 &&
            value.own_cpu_upper_s <= cpus.size() * value.wall_s + value.rounding_cpu_s &&
            value.task_cpu_s <= cpus.size() * value.wall_s + value.rounding_cpu_s;
        const double read_skew_cpu_s = cpus.size() *
            ((a.wall_last - a.wall_first) + (b.wall_last - b.wall_first)) / 1e9;
        value.counters_valid &= value.task_cpu_s + value.rounding_cpu_s + read_skew_cpu_s +
            accounting_margin * value.wall_s >= value.own_cpu_upper_s;
        if (!value.counters_valid) return;
        value.score = (value.task_cpu_s - value.own_cpu_upper_s - value.rounding_cpu_s) / value.wall_s - accounting_margin;
        value.usable = value.model_end - value.model_start >= min_call_ns;
        value.shadow_choice = value.usable && value.score > threshold ? 5 : 6;
    }
    static void invalidate(epoch & value, int reason) {
        if (!value.invalidated) value.reason = reason;
        value.invalidated = true;
    }
    static int find_member(epoch & value, int slot, int task, bool add) {
        for (unsigned i = 0; i < value.member_count; ++i) {
            const auto & existing = value.members[i];
            if (existing.slot == slot) return existing.task == task ? (int)i : -1;
            if (existing.task == task) return -1;
        }
        if (!add || value.member_count == 8 || task < 0 || slot < 0) return -1;
        const unsigned index = value.member_count++;
        value.members[index].task = task;
        value.members[index].slot = slot;
        return (int)index;
    }
    static void print_snapshot(const snapshot & value) {
        std::fprintf(stderr, "{\"wall_first\":%lld,\"wall_last\":%lld,\"cpu_first\":%lld,\"cpu_last\":%lld,\"task_ticks\":%llu,\"ok\":%s,\"fields\":[",
                     value.wall_first, value.wall_last, value.cpu_first, value.cpu_last, value.task_ticks, value.ok ? "true" : "false");
        for (unsigned i = 0; i < 6; ++i)
            std::fprintf(stderr, "%s[%llu,%llu,%llu]", i ? "," : "", value.fields[i][0], value.fields[i][1], value.fields[i][2]);
        std::fprintf(stderr, "]}");
    }

public:
    newa_decode_policy() {
        const char * setting = std::getenv("NEWA_DECODE_RESOURCE");
        if (!setting || !std::strcmp(setting, "off")) return;
        if (!std::strcmp(setting, "pressure")) policy = mode::pressure;
        else if (!std::strcmp(setting, "fixed6")) policy = mode::fixed6;
        else if (!std::strcmp(setting, "fixed5")) policy = mode::fixed5;
        else throw std::invalid_argument("unknown Prefill pressure mode");
        cpu_set_t mask;
        CPU_ZERO(&mask);
        if (sched_getaffinity(0, sizeof(mask), &mask) || CPU_COUNT(&mask) != 6)
            throw std::invalid_argument("Prefill pressure experiment requires fixed six-CPU affinity");
        unsigned index = 0;
        for (int cpu = 0; cpu < CPU_SETSIZE; ++cpu) if (CPU_ISSET(cpu, &mask)) cpus[index++] = cpu;
        ticks_per_second = sysconf(_SC_CLK_TCK);
        if (ticks_per_second <= 0) throw std::invalid_argument("invalid USER_HZ");
    }
    bool enabled() const { return policy != mode::off; }
    void reset() {
        if (!enabled()) return;
        if (selected) ++failures;
        if (current.active && current.calls) {
            if (report_count < reports.size()) reports[report_count++] = current;
            else ++reports_dropped;
        }
        current = proposed = epoch{};
        selected = begun = capture = false;
    }
    template<class Tokens>
    llama_compute_profile select(server_batch_phase phase, const llama_batch & view,
            const Tokens & tokens, int off, llama_context * ctx, llama_compute_profile original) {
        if (!enabled()) return original;
        if (selected) reset();
        if (llama_n_threads(ctx) != 5 || llama_n_threads_batch(ctx) != 6)
            throw std::invalid_argument("Prefill pressure experiment requires threads5/batch6");
        proposed = current;
        proposed.active = true;
        capture = false;
        int actual = phase == SERVER_BATCH_PHASE_DECODE && view.n_tokens == 1 ? 5 : 6;
        const bool shape = view.n_tokens > 0 && off >= 0 && (size_t)off + view.n_tokens <= tokens.size() &&
            view.token && !view.embd && view.pos && view.seq_id && view.n_seq_id && view.logits;
        if (!shape || (unsigned)phase >= 4 || phase == SERVER_BATCH_PHASE_UNKNOWN) invalidate(proposed, 1);
        if (!proposed.invalidated && (phase == SERVER_BATCH_PHASE_PREFILL || phase == SERVER_BATCH_PHASE_MIXED)) {
            if (proposed.locked) invalidate(proposed, 2);
            for (int i = 0; i < view.n_tokens && !proposed.invalidated; ++i) {
                const auto & token = tokens[off + i];
                const bool prefill = token.phase == SERVER_BATCH_PHASE_PREFILL;
                const bool decode = token.phase == SERVER_BATCH_PHASE_DECODE;
                int member_index = find_member(proposed, token.id_slot, token.id_task, prefill);
                if (member_index < 0 || (!prefill && !decode) || view.n_seq_id[i] != 1 || !view.seq_id[i] ||
                        view.seq_id[i][0] != token.id_slot || view.pos[i] != token.pos) {
                    invalidate(proposed, 3); break;
                }
                auto & member = proposed.members[member_index];
                if ((member.prefill_seen && (long long)member.last_position + 1 != token.pos) ||
                        (!member.prefill_seen && (!prefill || token.pos != 0)) ||
                        (decode && (!token.output || !view.logits[i]))) {
                    invalidate(proposed, 4); break;
                }
                if (!member.prefill_seen) member.first_position = token.pos;
                member.prefill_seen = true;
                member.last_position = token.pos;
            }
            if (!proposed.invalidated && phase == SERVER_BATCH_PHASE_PREFILL && view.n_tokens >= 32 && !proposed.sample.captured) {
                capture = true;
                proposed.sample.captured = true;
                proposed.sample.n_tokens = view.n_tokens;
            }
        } else if (!proposed.invalidated && phase == SERVER_BATCH_PHASE_DECODE) {
            bool eligible = view.n_tokens <= 8 && proposed.member_count == 8 && proposed.sample.captured &&
                proposed.sample.counters_valid && proposed.sample.usable;
            unsigned active_mask = 0;
            for (int i = 0; i < view.n_tokens && eligible; ++i) {
                const auto & token = tokens[off + i];
                int index = find_member(proposed, token.id_slot, token.id_task, false);
                if (index < 0 || view.n_seq_id[i] != 1 || !view.seq_id[i] ||
                        view.seq_id[i][0] != token.id_slot || view.pos[i] != token.pos ||
                        token.phase != SERVER_BATCH_PHASE_DECODE || !token.output || !view.logits[i]) {
                    eligible = false; break;
                }
                unsigned bit = 1U << index;
                auto & member = proposed.members[index];
                if ((active_mask & bit) || !member.prefill_seen || (long long)member.last_position + 1 != token.pos) {
                    eligible = false; break;
                }
                active_mask |= bit;
                member.last_position = token.pos;
            }
            if (!proposed.locked) {
                eligible &= active_mask == 255;
                if (eligible) {
                    proposed.first_decode_ns = wall_ns();
                    proposed.sample_age_ns = proposed.first_decode_ns - proposed.sample.after.wall_last;
                    eligible &= proposed.sample.after.ok && proposed.sample_age_ns >= 0 && proposed.sample_age_ns <= max_start_age_ns;
                }
            } else eligible &= active_mask && !(active_mask & ~proposed.active_mask);
            eligible &= proposed.eligible_calls < max_decode_calls;
            if (!eligible) invalidate(proposed, 5);
            else {
                proposed.locked = true;
                proposed.active_mask = active_mask;
                ++proposed.eligible_calls;
                actual = view.n_tokens == 1 ? 5 : policy == mode::fixed6 ? 6 : policy == mode::fixed5 ? 5 : proposed.sample.shadow_choice;
                ++proposed.eligible_by_size[view.n_tokens][actual == 5 ? 0 : 1];
            }
        }
        ++proposed.calls;
        if ((unsigned)phase < 4) ++proposed.decisions[(unsigned)phase][actual == 5 ? 0 : 1];
        selected = true;
        return actual == 5 ? LLAMA_COMPUTE_PROFILE_GENERATION : LLAMA_COMPUTE_PROFILE_BATCH;
    }
    void begin() {
        if (!enabled()) return;
        if (!selected || begun) throw std::logic_error("Prefill sensor begin order");
        begun = true;
        if (capture) {
            proposed.sample.before = sample_cpu();
            proposed.sample.model_start = wall_ns();
        }
    }
    void finish(int result) {
        if (!enabled()) return;
        if (!selected || !begun) throw std::logic_error("Prefill sensor finish order");
        selected = begun = false;
        if (result) {
            ++failures;
            invalidate(current, 6);
            capture = false;
            return; // Never commit provisional metadata from a failed model call.
        }
        if (capture) {
            proposed.sample.model_end = wall_ns();
            proposed.sample.after = sample_cpu();
            evaluate(proposed.sample);
            if (!proposed.sample.counters_valid) {
                ++read_errors;
                invalidate(proposed, 7);
            }
        }
        current = proposed;
        capture = false;
    }
    ~newa_decode_policy() {
        if (!enabled()) return;
        reset();
        const char * name = policy == mode::pressure ? "pressure" : policy == mode::fixed6 ? "fixed6" : "fixed5";
        std::fprintf(stderr, "NEWA_PREFILL_POLICY {\"mode\":\"%s\",\"failures\":%u,\"read_errors\":%u,\"reports_dropped\":%u,\"ticks_per_second\":%ld,\"cpus\":[",
                     name, failures, read_errors, reports_dropped, ticks_per_second);
        for (unsigned i = 0; i < cpus.size(); ++i) std::fprintf(stderr, "%s%d", i ? "," : "", cpus[i]);
        std::fprintf(stderr, "],\"threshold\":%.17g,\"accounting_margin_cores\":%.17g,\"epochs\":[", threshold, accounting_margin);
        for (unsigned i = 0; i < report_count; ++i) {
            const auto & e = reports[i];
            const auto & s = e.sample;
            std::fprintf(stderr, "%s{\"calls\":%llu,\"locked\":%s,\"invalidated\":%s,\"reason\":%d,\"active_mask\":%u,\"eligible_calls\":%u,\"first_decode_ns\":%lld,\"sample_age_ns\":%lld,\"members\":[",
                i ? "," : "", e.calls, e.locked ? "true" : "false", e.invalidated ? "true" : "false", e.reason,
                e.active_mask, e.eligible_calls, e.first_decode_ns, e.sample_age_ns);
            for (unsigned j = 0; j < e.member_count; ++j) {
                const auto & v = e.members[j];
                std::fprintf(stderr, "%s{\"task\":%d,\"slot\":%d,\"first_position\":%d,\"last_position\":%d,\"prefill_seen\":%s}",
                    j ? "," : "", v.task, v.slot, v.first_position, v.last_position, v.prefill_seen ? "true" : "false");
            }
            std::fprintf(stderr, "],\"decisions_5_6\":[");
            for (unsigned j = 0; j < 4; ++j) std::fprintf(stderr, "%s[%llu,%llu]", j ? "," : "", e.decisions[j][0], e.decisions[j][1]);
            std::fprintf(stderr, "],\"eligible_by_size_5_6\":[");
            for (unsigned j = 0; j < 9; ++j) std::fprintf(stderr, "%s[%llu,%llu]", j ? "," : "", e.eligible_by_size[j][0], e.eligible_by_size[j][1]);
            std::fprintf(stderr, "],\"sample\":{\"captured\":%s,\"counters_valid\":%s,\"usable\":%s,\"n_tokens\":%d,\"model_start\":%lld,\"model_end\":%lld,\"wall_s\":%.17g,\"task_cpu_s\":%.17g,\"own_cpu_upper_s\":%.17g,\"rounding_cpu_s\":%.17g,\"score\":%.17g,\"shadow_choice\":%d,\"before\":",
                s.captured ? "true" : "false", s.counters_valid ? "true" : "false", s.usable ? "true" : "false", s.n_tokens,
                s.model_start, s.model_end, s.wall_s, s.task_cpu_s, s.own_cpu_upper_s, s.rounding_cpu_s, s.score, s.shadow_choice);
            print_snapshot(s.before);
            std::fprintf(stderr, ",\"after\":");
            print_snapshot(s.after);
            std::fprintf(stderr, "}}");
        }
        std::fprintf(stderr, "]}\n");
    }
};
