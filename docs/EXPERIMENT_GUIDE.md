# Phase-policy experiment guide

M11R is the shared observation baseline. It is not a policy result and should
remain reproducible while experiments diverge on separate branches.

## Start from the immutable baseline

After the release owner publishes the tag:

```bash
git fetch --tags origin
git checkout m11-semantic-phase-baseline-v1
git switch -c experiment/<name>
```

Never move or overwrite that tag. Do not change the pinned semantic llama.cpp
revision during a scheduling-policy experiment. If a semantic-provider change
is needed, treat it as a separate integration milestone rather than a policy
comparison.

Before editing policy code, run or review the baseline bootstrap and privileged
validation on the experiment machine. Keep `scripts/validate_phase.sh` passing
throughout the work.

## Choose one dimension

Begin with exactly one scheduling dimension. Suitable independent themes
include:

- idle-core CPU selection;
- SMT avoidance;
- migration suppression;
- phase-separated DSQs;
- phase-dependent slice length; or
- load-aware CPU selection.

Do not combine several successful-looking changes before each has isolated
evidence. Keep selected-child isolation and `SCX_OPS_SWITCH_PARTIAL`. Preserve
UNKNOWN, PREFILL, DECODE, and MIXED as distinct semantic inputs; never relabel
MIXED to make a policy simpler.

Add neutral or diagnostic evidence before drawing performance conclusions.
Single runs can establish plumbing or reveal failures, but they cannot support
performance claims.

## Minimum experiment record

For every baseline and treatment, record:

- CPU model, physical core count, logical CPU count, and SMT state;
- Ubuntu release and exact kernel;
- model identity, size, quantization, and model file checksum where policy
  permits;
- immutable baseline tag and experiment commit;
- exact server/workload parameters;
- co-load type, placement, intensity, and timing;
- warm-up and cache conditions;
- run count and run ordering/randomization;
- latency, throughput, runtime, migrations, CPU utilization, and any
  phase-specific metrics used;
- failures, exclusions, interrupted runs, and cleanup state.

Keep raw runs separate. Do not merge output from different PIDs, kernels,
models, or run IDs into one authoritative directory.

## Evaluation discipline

1. Re-run M11R semantic acceptance after every change that can affect phase
   capture, selected-child launch, or loader lifecycle.
2. Compare the unchanged baseline and one treatment under the same workload and
   co-load.
3. Use repeated runs and report variability, not only the best result.
4. Check callback counts, failure counters, scheduler exit data, and cleanup
   before interpreting performance.
5. Preserve negative and neutral results.
6. Review one dimension before starting or combining another.
7. Keep the work on `experiment/<name>` until it has independent review.

The baseline does not select a winning policy. Policy selection belongs to a
later milestone after isolated evaluation.
