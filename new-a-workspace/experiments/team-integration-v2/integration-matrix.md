# 통합 상태표

기능 원장의 증거 경로에는 실험 PC의 원시 결과 보관 경로도 포함된다. 이 브랜치에서 공유하는 수치는 [AMD 검증 문서](amd-local-validation.md)와 그 문서에 연결된 요약 JSON에서 확인할 수 있다.

| 기능 | 출처 유형 | 통합 | 검증 | 범위 |
|---|---|---|---|---|
| R-prefill | LOCAL | INTEGRATED_ACTIVE | MODEL_TESTED | Canonical R activation; native worker-index adapter. Q4 phase counters and exact token comparisons. |
| Q6-by-phase | LOCAL | INTEGRATED_ACTIVE | MODEL_TESTED | Native extension reuses kernel body and graph worker index. Phase chunk counters demonstrate path use. |
| explicit-profile | SHARED_ANCESTRY | EXISTING_REUSED | MODEL_TESTED | Two resource profile API, null ctx guard adapted from later donor. |
| semantic-batch | SHARED_ANCESTRY | EXISTING_REUSED | MODEL_TESTED | Selection reads actual view incl offset, retry and split. |
| CPU-bridge | LOCAL | INTEGRATED_ACTIVE | MODEL_TESTED | Off transport preserves CPU phase and R/Q6 dispatch. |
| E-legacy | LOCAL | EXISTING_REUSED | MODEL_TESTED | Legacy six CPU, 5/6, fixed5/fixed6/pressure and old behavior. Fresh model tests keep fixed envelope. |
| adaptive-config | LOCAL | INTEGRATED_SELECTABLE | MODEL_TESTED | Explicit workers, 2..8 members, age/threshold, max 32 CPU. Tested on 5/6 AMD only; Intel4/8 native pending. |
| pool | DONOR_ADAPTED | INTEGRATED_SELECTABLE | MODEL_TESTED | Common owner composes disposable/shared/role pools. New alloc failure and second-worker ENOMEM/EAGAIN injection verifies cleanup and fresh reuse. |
| role-masks | DONOR_ADAPTED | INTEGRATED_SELECTABLE | MODEL_TESTED | Actual native 5/6 teams with singleton worker masks; explicit generation/batch poll strategy. SCX/strict role-mask combination rejected. |
| role-priority | DONOR_ADAPTED | INTEGRATED_SELECTABLE | MODEL_TESTED | Native Linux only. Generation/Batch priority modes select actual SCHED_BATCH workers; caller restored on success/abort. OpenMP and SCX combination rejected; RT is outside the common launcher. |
| state-publisher | DONOR_ADAPTED | INTEGRATED_SELECTABLE | MODEL_TESTED | RUN and monotonically increasing sequence, active/idle, sleep and shutdown. Single CPU decoder scope. |
| marker-tu | DONOR_ADAPTED | INTEGRATED_SELECTABLE | MODEL_TESTED | All four transport modes tested as run selections; only state has publisher event log. Kernel attach NOT_RUN. |
| v2-receiver | LOCAL | INTEGRATED_SELECTABLE | MODEL_FREE_TESTED | C contract and both BTF objects built. Actual attach and raw event delivery KERNEL_NOT_RUN. |
| CPUID-topology | DONOR_ADAPTED | INTEGRATED_ACTIVE | MODEL_TESTED | AMD real; Intel hybrid/SMT/cpuset synthetic. Unknown is rejected. |
| FULL-Lite | DONOR_ADAPTED | INTEGRATED_SELECTABLE | COMPILED | Same dispatch and safety counters within each sealed policy. Compiled for current host BTF; native verifier and kernel data pending. |
| selected-child | DONOR_ADAPTED | INTEGRATED_SELECTABLE | MODEL_FREE_TESTED | Eight current-BTF builds/owner-bound plans across FULL/Lite and placement policies. Manual root loader remains a separate checkpoint. |
| idle-handoff | LOCAL | INTEGRATED_SELECTABLE | MODEL_FREE_TESTED | FULL/Lite sealed Decode candidate. Actual valid v2 state controls eligible first-tier idle enqueue/kick. Capabilities, real moves, isolation and detach require manual kernel admission. |
| serving | DONOR_ADAPTED | INTEGRATED_SELECTABLE | MODEL_TESTED | All six donor workloads times two profiles; overlap observed only in m1/m3. One pair per workload provides observations. |
| mixed-cap128 | DONOR_ADAPTED | INTEGRATED_SELECTABLE | MODEL_TESTED | Positive cap counts in m1/m3, zero in pure pp/d1/d2/d4. Paired config held cap constant. |
| flash-attn-head64 | DONOR_ADAPTED | INTEGRATED_SELECTABLE | MODEL_TESTED | Native 6/6, scoped m4 geometry, original Qwen2 and AVX2/FP16 KV. 3584 actual custom CPU layer calls per candidate visit; five stream arrays match in warmup/measurement. |
| manifest-launch | LOCAL | INTEGRATED_ACTIVE | MODEL_TESTED | Source+compiler+DSO seal, stale library/pre-R/invalid ELF rejection tests. |
| previous-idle-locality | LOCAL | INTEGRATED_SELECTABLE | MODEL_FREE_TESTED | Sealed locality-decode and locality-active choices; selected TGID, first tier, allowed/online/idle checks. No native kernel admission yet. |
| native-park | LOCAL | INTEGRATED_SELECTABLE | MODEL_TESTED | Native futex mode with common all/prefill/budget options. Budget test observed 3402 Prefill waits and exact tokens. OpenMP and kernel combination rejected. |
| native-barrier-hint | LOCAL | OUT_OF_SCOPE_WITH_REASON | NOT_RUN | Inherited diagnostic symbol has no matching barrier-hint consumer in pinned scheduler. The public state-v2 provider is a different ABI. |
| repack-huge-advice | LOCAL | EXISTING_REUSED | MODEL_TESTED | Eligible CPU repack buffers receive MADV_HUGEPAGE. AMD startup recorded return 0; actual THP use and effect not measured. |
