# Compatibility and validation matrix

M11R separates a known-good environment from hosts that merely expose the
interfaces needed to attempt a build or runtime test.

## Status terms

- `VALIDATED`: the complete semantic llama-server → uprobe → BPF → sched_ext
  path passed the M11 acceptance criteria on this environment.
- `COMPATIBLE-BUT-UNVALIDATED`: required Ubuntu/x86-64 sched_ext, BTF, header,
  and kfunc checks passed, but this exact environment has no recorded semantic
  end-to-end PASS yet.
- `UNSUPPORTED`: a required architecture, sched_ext state interface, BTF
  interface, header, kfunc, or build dependency is absent.

A successful compilation alone never promotes a machine to `VALIDATED`.

## Recorded environments

| Environment | CPU | Kernel | Build | Semantic E2E | Status |
| --- | --- | --- | --- | --- | --- |
| Ubuntu 24.04.4 LTS, x86-64 | AMD Ryzen 5 5500U, 6 cores / 12 logical CPUs | `7.0.0-29-generic` | PASS | PASS: 8 begin / 8 end, 1 PREFILL / 7 DECODE, failure counters zero, PREFILL.running and DECODE.running nonzero | VALIDATED |

The accepted semantic provider revision and baseline identity live in
[config/versions.env](../config/versions.env). The validated workload used a
DeepSeek-R1-Distill-Qwen-1.5B Q4_K_M-family model, one server slot, CPU-only
execution, no speculative decoding, no continuous batching, no warm-up, and
eight predicted tokens.

No other machine or kernel result is claimed here.

## Capability checks

`scripts/bootstrap_ubuntu.sh` requires and reports:

- Ubuntu and x86-64;
- `/sys/kernel/sched_ext/state`;
- `/sys/kernel/btf/vmlinux`;
- headers matching `uname -r`;
- `sched_ext_ops` and the SCX kfuncs used by the BPF scheduler in kernel BTF;
- the compiler, CMake, bpftool/libbpf, and userspace development dependencies.

A kernel other than the manifest's validated kernel may proceed only when these
checks pass. The bootstrap labels that host `COMPATIBLE-BUT-UNVALIDATED`, and
the runtime result must be reviewed as a new environment.

The scripts do not install, select, or boot a kernel.

## Adding a machine result

1. Start from the immutable `m11-semantic-phase-baseline-v1` tag once it has
   been published.
2. Record the Ubuntu release, architecture, CPU model, physical/logical CPU
   count, exact `uname -r`, model identity/quantization, and scheduler tag.
3. Run:

   ```bash
   ./scripts/bootstrap_ubuntu.sh
   ./scripts/validate_phase.sh --model /path/to/model.gguf
   ```

4. Preserve the complete ignored `results/m11r/<run>/` directory outside Git or
   in the team's approved evidence store.
5. Confirm `semantic_acceptance=PASS`, final sched_ext state `disabled`, and no
   cleanup warnings.
6. Add one table row in a review branch. Link or identify the evidence bundle
   and state the run count; do not infer compatibility for adjacent kernels or
   different model families.
7. Have another team member review the environment record, isolation evidence,
   completion response, and instrumentation JSON before marking the row
   `VALIDATED`.
