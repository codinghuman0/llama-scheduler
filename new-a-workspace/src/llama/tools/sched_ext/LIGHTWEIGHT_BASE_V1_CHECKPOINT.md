# Lightweight Base v1

## 1. Purpose

This is the validated, frozen minimal infrastructure baseline before phase-aware, load-aware, or topology-aware scheduler optimization. The final checkpoint is the commit named by the annotated `lightweight-base-v1` tag. This document preserves its architecture, source identities, validation and accepted measurement result without requiring chat history or local result files.

## 2. Final Architecture

The MIT llama-side implementation is frozen at `llama-side-lightweight-v1`. With `LLAMA_SCX_PHASE_HINT=ON` it emits semantic transitions through `llama_scx_phase_v1(uint32_t)`. `LLAMA_SCX_PHASE_TRACE=OFF` for the lightweight runtime. The ABI is UNKNOWN=0, PREFILL=1, DECODE=2, MIXED=3. There is no idle UNKNOWN transition: the last DECODE value may remain while the server is idle.

The optional GPL scheduler remains separate from the normal llama.cpp build. Active sources are `llama_scx.bpf.c`, `llama_scx.c`, `llama_scx_child.c`, the two `include/` control headers and the scheduler-only `Makefile` under this directory. Linux v6.17 `scx_simple` copies in `provenance/` are immutable implementation provenance; `validation/` is the frozen golden correctness oracle, not the active implementation base.

The active scheduler preserves upstream weighted-vtime behavior: default CPU selection, direct local insertion on an idle CPU, shared DSQ 0 otherwise, vtime-ordered enqueue, shared-to-local dispatch, upstream running/stopping charging and enable initialization. Its ops use `SCX_OPS_SWITCH_PARTIAL`. The six scheduling callbacks (`select_cpu`, `enqueue`, `dispatch`, `running`, `stopping`, `enable`) neither read phase nor call phase-dependent helpers. No callback performs selected-TGID admission filtering; partial switching is not a security allowlist. Example FIFO/statistics and heavy validation accounting are absent.

The loader opens the BPF object directly through libbpf, with no generated skeleton. The root loader and normal-user launcher remain SCHED_NORMAL (raw policy 0); the selected normal-user server and its created threads use SCHED_EXT (raw policy 7). An authenticated, one-shot abstract SOCK_SEQPACKET registration/ACK exchange establishes the selected child. Userspace checks credentials, parent/leader identity, executable identity, marker mapping and target lifetime. Success ordering is identity validation -> selected-state initialization -> one PID-scoped ENTRY uprobe attachment -> liveness recheck -> success ACK. A pidfd tracks the target; signalfd handles loader termination. These controls stay outside scheduling decisions.

Executable and marker identities are independent. In the validated shared build, `build-lightweight-dev/bin/llama-server` is the executable and `build-lightweight-dev/bin/libllama-server-impl.so` contains the marker. Benchmark D uses the corresponding executable/DSO from C's exact runtime bundle. The uprobe reads the uint32 argument, defensively checks the current TGID against the selected TGID, rejects values above 3, and updates only the current phase.

The existing global `.data` ABI uses three fixed 32-bit fields (`__u32` in the shared GPL header):

| Field | Offset | Width |
| --- | ---: | ---: |
| `selected_tgid` | 0 | 4 bytes |
| `current_phase` | 4 | 4 bytes |
| `exit_kind` | 8 | 4 bytes |

Total logical size is 12 bytes, verified by static assertions and the built object's BTF/layout inspection. Upstream `vtime_now` remains separate in `.bss`. There is no per-task phase map, event stream, counter/history framework, worker classification, hot-path timestamp or permanent phase observer.

## 3. Git Checkpoints

| Checkpoint | Exact commit |
| --- | --- |
| `original-performance-baseline-v1` | `7a2db1a0cf38e5f4eb278a58c3903d295258d0ea` |
| `llama-side-lightweight-v1` | `c8b9d61d12b4997d902a03e5dc55a185d18c3bc9` |
| `one-repo-golden-validation-v1` | `542850645a54fc2e35a9a8189ff8dfcf35b9c51d` |
| `neutral-sched-ext-base-v1` | `ea4a36bbad1100d7d3f7c6aa57caadcb782a26fa` |
| Step 10.1 protocol: `bench: freeze lightweight base measurement protocol` | `64d9ea61278fbb0b1795d3cfcaaa688dbba9a91d` |
| Step 10.2 preparation: `bench: prepare isolated step10 campaign` | `90f5f042a46a57a17781c9315ef2600e59142383` |
| Runner guard/cleanup fixes | `19db9754f58f09c2071c6d9a0ed9cc97595119f1` |
| Quiet four-phase workflow; measured automation revision | `ecb1c6762e4e67b509c0e919ede5fc779a030225` |
| Final documentation checkpoint: `lightweight-base-v1` | Resolve `git rev-parse 'lightweight-base-v1^{commit}'`; the tag names the commit containing this document |

The audit of `90f5f042a46a57a17781c9315ef2600e59142383..ecb1c6762e4e67b509c0e919ede5fc779a030225` found only benchmark automation/tests/documentation changes. They fixed port TIME_WAIT handling, registration-log synchronization, bounded cleanup, strict quiet-application guards and artifact reuse. No scheduler/llama implementation or provenance/validation change occurred. The final checkpoint adds only this document; the previous tags retain their original targets.

## 4. Validation History

| Step | Result | Important acceptance facts |
| --- | --- | --- |
| 9.2 | PASS | Minimal direct-object scheduler/userspace builds; weighted-vtime neutrality, partial flag, phase independence and 12-byte object layout checked |
| 9.3 | PASS | Positive registration/isolation and one bounded inference; negative UID/executable/late-uprobe rejection; rollback, target-death and loader-signal lifecycle cleanup |
| 9.4 | PASS | Existing selected-process state transported PREFILL then DECODE during controlled inference; PID-scoped attachment; temporary observer only |
| 9.5 | PASS | Neutral scheduler tag fixed at its implementation commit; no policy change |
| 10.1 / 10.2 preparation | PASS | Fixed protocol and four-phase automation prepared before measurement |
| Step 10 campaign / 10.4 | PASS | All 40 measured samples retained; raw-result/statistics/paired-bootstrap audit; both infrastructure decision gates accepted |

Across runtime validation the root loader, user launcher and unrelated sentinel stayed at policy 0, and all observed selected-server TIDs used policy 7. Shutdown/reap and BPF cleanup passed. Short natural visibility of programs/global-data maps after loader exit was accepted: Case 3 revalidation first restored the complete baseline at the approximately 289 ms checkpoint. Cleanup observation allows up to 2000 ms, saves evidence before assertions, and performs no BPF deletion.

## 5. Benchmark Protocol

The full frozen definitions are in [BENCHMARK_PROTOCOL.md](BENCHMARK_PROTOCOL.md); operational instructions are in [bench/README.md](bench/README.md).

| Setting | Frozen measurement value |
| --- | --- |
| Host | AMD Ryzen 5 5500U; six physical cores, twelve logical CPUs; SMT enabled |
| SMT sibling pairs | 0/1, 2/3, 4/5, 6/7, 8/9, 10/11 |
| Measured kernel | `7.0.0-34-generic`; the Git checkpoint is not kernel-specific |
| Server affinity / threads | CPUs `0,2,4,6,8`; compute=5, batch=5, HTTP=2 |
| Housekeeping | CPUs `10,11`; runner/client=11, root helper/loader=10 |
| Unused server siblings | 1,3,5,7,9; SMT was not disabled globally |
| Server configuration | GPU layers=0, parallel=1, context=2048, batch=512, ubatch=256; loopback port 8096 |
| Compute path | B/C/D use `--server-compute-profile-mode legacy`; A uses its original decode path |
| Build | GNU 13.3.0, CMake 3.28.3, Make 4.3; Release `-O3 -DNDEBUG`, native CPU, shared libraries, OpenMP; GPU/BLAS/LTO/sanitizers/profiling OFF |
| System conditions | AC power, acpi-cpufreq/schedutil, boost ON; frozen bounded load/temperature readiness; no intentional contention |
| Applications | Firefox/Codex/unnecessary applications closed before Phase A through Phase D; one terminal/text console |
| Repetitions | 10 measured samples/config; each fresh-server visit has two excluded warm-ups and one measured request |

Model: `/home/codinghuman/projects/model.gguf`, 1117321312 bytes, SHA-256 `f3bdf9cf31dee4b57ae4e455a1cb0d01b5c2c1b50d72d3112141c195506c2840`. The model is not stored in Git.

The exact prompt text/construction and canonical request JSON remain tracked in the protocol and `bench/common.py`. The fixed library-description prompt repeats the same paragraph eight times; it is 5023 bytes and evaluated to 920 tokens in this campaign. POST `/completion`, output=128 tokens, temperature=0, seed=424242, streaming=false, cache_prompt=false, ignore_eos=true, n_cache_reuse=0, id_slot=0, stop=[], return_tokens=false, timings_per_token=false. Prompt SHA-256: `b7be51379d30270d4d645aefb6014525e89e2bcba6e4be60f5f5613efbe5b4a9`; canonical request SHA-256: `7b68e4809a1f9bca18c2bc29b87c62c637e19e2ccd3785745cc717c046999e1d`.

Ten blocks use `ABCD, BCDA, CDAB, DABC, ABCD, BCDA, CDAB, DABC, ABCD, BCDA`: 40 measured samples and 80 excluded warm-ups. Normal server prefill/decode timing fields and external monotonic duration of the complete HTTP POST are the primary metrics. Startup, readiness, warm-ups, cleanup and result serialization are outside that duration. No phase polling or continuous observer runs during timing.

## 6. A/B/C/D Definition

| Config | Llama source/runtime | Hint | Scheduler |
| --- | --- | --- | --- |
| A | Original performance baseline tag | Option absent | Default Linux |
| B | Frozen llama-side tag | OFF, TRACE OFF | Default Linux |
| C | Frozen llama-side tag | ON, TRACE OFF | Default Linux |
| D | Exact C executable and project-library bytes; no separate D llama build | ON, TRACE OFF | Frozen neutral sched_ext base; validated selected-child mechanism |

A/B/C server TIDs use raw policy 0; D selected-server TIDs use raw policy 7. The D control processes remain raw policy 0 and use the housekeeping core. C/D share all llama runtime settings; D adds the neutral scheduler, validated control plane and PID-scoped marker attachment.

## 7. Performance Result

Authoritative local campaign: `benchmark-results/step10/20261007T120757Z/`, automation revision `ecb1c6762e4e67b509c0e919ede5fc779a030225`. Protocol SHA-256: `6cc89e5f389cac6c1c9eabdb2c688103ccad9325dd5cf2802115c3c0dcf236d9`. Validation was PASS; no samples/outliers were discarded and no measured sample was replaced. The ignored raw campaign is not included in a clone; these tables are its durable result summary, not a substitute for its raw evidence.

| Config | Prefill median, tokens/s | Decode median, tokens/s | Total median, ms |
| --- | ---: | ---: | ---: |
| A | 124.933214 | 15.006419 | 15904.641654 |
| B | 124.868871 | 14.999786 | 15913.659853 |
| C | 125.032522 | 14.997299 | 15902.877936 |
| D | 125.947163 | 15.102937 | 15783.368799 |

The tables display six decimal places with decimal half-up rounding. The unrounded B/D duration medians are 15913.6598525 ms and 15783.3687985 ms; use the unrounded campaign values for calculations.

| Comparison | Prefill slowdown | Decode slowdown | Total slowdown | Worst median slowdown |
| --- | ---: | ---: | ---: | ---: |
| A -> B | +0.051529% | +0.044217% | +0.056702% | +0.056702% |
| B -> C | -0.130887% | +0.016588% | -0.067753% | +0.016588% |
| C -> D | -0.726210% | -0.699455% | -0.751494% | -0.699455% |

Positive slowdown means slower. Throughput slowdown is `100 * (reference_median / candidate_median - 1)`; duration slowdown is `100 * (candidate_median / reference_median - 1)`. Use all ten measured samples/config and report medians, min/max, IQR and MAD. Gates use the worst of the three signed median slowdowns separately for B -> C and C -> D: <=0.5% acceptable; >0.5% through 1.0% requires repeat/variance investigation; >1.0% requires mandatory overhead investigation. Improvements never cancel another metric's regression. A -> B remains a reference-only fork/base comparison.

Whole-block paired bootstrap: 10000 draws, Python `random.Random(20261006)`, 95% percentile intervals with frozen linear interpolation. The verified supporting intervals are:

| Comparison | Prefill slowdown interval | Decode slowdown interval | Total slowdown interval |
| --- | --- | --- | --- |
| B -> C | [-0.194023%, -0.074243%] | [-0.051216%, +0.108575%] | [-0.129247%, +0.003741%] |
| C -> D | [-0.802584%, -0.445601%] | [-0.805620%, -0.493975%] | [-0.800681%, -0.467204%] |

All A -> B intervals cross zero. B -> C decode/duration intervals cross zero; its small decode point regression is not resolved from zero. All C -> D intervals are below zero in this campaign. No interval triggers the frozen precision rule spanning both <=0.5% and >1.0%. Bootstrap supports the median gate and does not replace it.

Step 10.4 decision: no repeat required; no overhead investigation required; infrastructure accepted for Lightweight Base v1 freeze and later optimization. Every visit and final cleanup passed; pre/post BPF inventories matched, sched_ext was disabled and no project process remained. Ten D activations advanced enable_seq from 0 to 10.

## 8. Interpretation Boundaries

A -> B is the fork/base implementation delta. B -> C is the phase-hint transport delta. C -> D is the neutral sched_ext-base delta including weighted-vtime scheduling semantics, not pure sched_ext framework overhead.

Base v1 contains no phase-aware, load-aware, or topology-aware scheduling decision. The stored phase is transport input only. The measured result applies to this frozen single-request CPU-only workload and measured host; it does not establish performance for other workloads, contention or later policies.

## 9. Reproduction / Return Checklist

1. Clone the repository including tags, then check out `lightweight-base-v1`. Resolve its commit with `git rev-parse 'lightweight-base-v1^{commit}'`; this is the final documentation checkpoint and avoids a self-referential commit-hash placeholder.
2. Verify the four authoritative tag targets in section 3. Keep provenance, validation and frozen llama-side sources intact. Read this document and the linked protocol before changing anything.
3. Prepare a compatible Linux sched_ext kernel with local `/sys/kernel/btf/vmlinux`, clang with BPF support, libbpf/libelf/zlib and bpftool. The scheduler-only `make -C tools/sched_ext all` regenerates local `vmlinux.h`; never reuse another host's BPF artifact blindly. Runtime loader privilege is separate from normal-user llama execution.
4. Supply the model with the recorded size/SHA-256. It and ignored build/runtime bundles are not included in Git. Verify available disk and exact compiler/build settings before rebuilding for measurement.
5. If measurement is needed, follow `BENCHMARK_PROTOCOL.md` and `bench/README.md`. The four-phase runner is host/UID/toolchain/artifact-hash specific; changed host, topology, kernel or artifact identity requires a reviewed reproduction plan, not relaxed gates.
6. The unchanged runner's repository guard accepts only protocol/bench-path changes after Step 10.1 and requires branch `lightweight-base`. This final checkpoint document lies outside that allowlist. For unchanged four-phase automation, use a separate clone at the exact tested automation revision `ecb1c6762e4e67b509c0e919ede5fc779a030225` on branch `lightweight-base`, retain the Base tag, and rebuild the recorded A/B/C revisions according to the protocol. Do not move the Base tag, rewrite its history, or bypass guards. A fresh preparation uses Phase A without `--reuse-artifacts` because bundles are absent.
7. Do not assume `benchmark-results/` exists in a fresh clone. Preserve any new campaign separately; compare it with this recorded result using the frozen definitions. Phases A/B prepare and arm, C measures unattended, D validates/summarizes; keep applications closed through D. The 2026 campaign's local raw files are optional archival evidence, not a runtime dependency of Base v1.

## 10. Future Work Boundary

Future phase/load/topology-aware work belongs after Lightweight Base v1. It must remain distinguishable from this accepted neutral baseline and must not move or change the meaning of `lightweight-base-v1` or `neutral-sched-ext-base-v1`. No such optimization was implemented in this checkpoint. Remote publication and remote-ref verification are separate actions; this local checkpoint step does not push.
