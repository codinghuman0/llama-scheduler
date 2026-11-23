# NEW_A phase-aware execution and scheduling study

The complete controlling request is `research-request.txt`. This study does not end at the first successful result. Older checkpoint/provenance files and golden validations are read-only.

## Fixed comparisons

- B0: clean historical source `original-performance-baseline-v1`, commit `7a2db1a0cf38e5f4eb278a58c3903d295258d0ea`, rebuilt with the recorded GNU 13.3 Release/native/OpenMP options. The original executable bundle is unavailable. The rebuild is not claimed byte-identical to that lost bundle. Live support and loaded dependencies must pass smoke before measurements.
- B1: the q4-exact runtime selected from its audited eight-request confirmations. `identity/B1.json` freezes its code, mixed-component provenance, executable/DSO bytes, and execution configuration. Relocation preserves all runtime bytes. B1 will not be replaced by a later candidate.
- C0: starting checkpoint, B1 with the existing guarded Decode idle-handoff sched_ext policy. Initial measurements compare B0/B1/C0 directly under matched conditions. They are screening evidence, not the new confirmations.
- C: selected runtime/execution-policy/scheduler combination after exploration.
- C-off: exactly C with the newly researched phase decisions replaced by declared fixed decisions. Existing B1 Q4/Q6 kernels remain enabled. The exact off decisions must be frozen before confirmation.

Historical arm mapping is explicit in `identity/legacy-arm-mapping.json`. Previous NEW_A_* names denoted scheduler arms; previous LINUX_CONTROL was an optimized q4-tile32 runtime, not B0. No historical percentages will be added to produce C/B0.

## Measurement and exploration sequence

1. Finish B0 build identity, B1 relocated smoke, equal-input tokenization/support, current topology, model identity, permission and cleanup checks. Record B0/B1 output differences separately from within-runtime repeatability.
2. Characterize B0/B1/C0 with the existing eight distinct requests, in both ambient and measured cpu25 conditions, using fixed two-block paired pilots. Preserve any already successful system checkpoint without declaring this goal complete.
3. Run isolated policy pilots and separate diagnostics. Use complete balanced blocks and record all visits, including failures. Keep build/profiling out of performance runs.
4. Test combinations only when individual results or diagnostics supply an interaction hypothesis. Preserve the best supported checkpoint; reject unsupported complexity.
5. Freeze selected code, configurations, analysis, metric, two independent campaigns, held-out cohorts, repetition count and exclusion rules. Run both campaigns serially without tuning between them.
6. Finish on/off equality, single-request and changed-length regressions, actual policy-decision evidence, attribution, independent raw recomputation and submission package. Report system gain and phase contribution separately, including negative or inconclusive effects.

## Policy families and first evidence-driven candidates

### A: active workers/profile

Current B1's legacy profile uses six workers for batch8 even though its CLI generation count is five. Start with the existing semantic profile: Prefill6 / Decode5 / UNKNOWN-or-Mixed AUTO, compared to both fixed6 and fixed5. This changes policy through existing safe graph-boundary APIs and leaves arithmetic kernels untouched. Trace actual graph classifications/profile decisions and observed teams outside timed trials. Prior Q6-only semantic5 results are not a valid rejection of this q4-exact candidate.

The targeted cost is straggler/barrier waiting under contention versus lost parallelism when quiet. Decode4 is a follow-up only if the five-worker result/diagnostic supports that direction. If the best choice differs strongly by measured contention, consider a conservative phase+pressure selector after defining its observed signal and overhead. Do not identify contention by benchmark condition names.

### B: waiting/wakeup/idle handoff

First compare existing `observe` and `decode` idle-handoff loaders on the same B1 runtime. This isolates the handoff feature, but is not by itself a full phase-gating attribution. If worth retaining, compare Decode-only with an explicitly fixed eligible-phase handoff policy using a separate guarded object/loader; UNKNOWN/Mixed fallbacks remain conservative.

Existing native `GGML_NEWA_BARRIER` controls are inapplicable to the OpenMP early-return path in `ggml_barrier()`. Installed libgomp's `omp_pause_resource_all()` destroys/joins the host pool, so it is not a safe cheap spin-budget setter. These paths are rejected on code evidence unless new observations justify a backend change. Fixed GOMP_SPINCOUNT is a possible overhead control, not a phase policy.

Existing handoff activity was zero in the eight quiet candidate sessions and only four moves total in the eight loaded sessions; those are lifetime counts, not measured-window critical-path evidence. A Decode5 + handoff combination is worth considering because reducing workers may create idle destinations. New activity diagnostics must distinguish the actual request window and worker roles.

### C: phase, topology and contention in placement/dispatch

Start with existing previous-CPU-if-idle preference: Decode-only versus all-phase preference and the base selector, all within the same verified CPU mask. Revalidate every retained object/loader before reuse. Current q4-exact loaded data show migrations/cohort increasing from 88.875 (Linux) to 643.5 (research scheduler), cohort time 23.750 to 24.286 seconds, and selected-CPU busy 99.31% to 91.81%. This supports investigation, not a causal claim.

Inspect worker-specific migration/runnable-wait/imbalance and actual preference hits in separate diagnostics. Only add a phase+pressure/dispatch refinement if those observations identify recoverable waiting. Do not revive the historically unsafe dynamic-affinity/fairness paths, or expand the CPU envelope only for a candidate. Existing SMT results and the fixed six-CPU guard make adding sibling CPUs to one arm invalid here.

## Diagnosis and interpretation boundaries

The existing scheduler hint is last-emitted phase and is not reset at request idle. Never use it as an execution timer. Aggregate cohort throughput remains the primary metric. Trace actual graph begin/end and profile selection only in diagnostic runs; the existing compute-profile trace synchronizes/logs and is not free. Investigate whether minimal end-of-work UNKNOWN signaling is needed before relying on phase-specific wakeup decisions.

FULL BPF instrumentation includes accounting and a coarse guard monitor. All scheduler comparisons must use the same instrumentation mode. Any lighter diagnostic mode needs a separate overhead/safety check and cannot remove the fixed-affinity guard. CPU-seconds reduction alone is not speedup.

## Resource and integrity rules

Use the shared `new-a-runs/.measurement.lock`, one server/campaign at a time, fresh run directories, controlled ordinary-user environments, owned-process timeouts/cleanup, current CPU topology and kernel/BTF identities. Build and inference never use sudo. Sudo is limited to the guarded selected-child loader, scoped diagnostics and owned cleanup. Do not change sudoers, power/governor settings or unrelated processes. Preserve at least 512 MiB where practical; reclaim only this study's verified redundant build intermediates if needed.

At this stage no result meets the new goal's completion conditions. `protocol.json` fixes the primary measurement semantics; final candidate/held-out campaign identities remain pending exploration and must be frozen before confirmation.
