# llama-scheduler

## What this is

`llama-scheduler` is the reproducible M11 semantic phase-observation baseline for
experiments with Linux `sched_ext`. It connects a pinned CPU-only semantic
`llama-server` to PID-specific uprobes, bounded BPF phase state, and observational
scheduler callback counters:

```text
semantic llama-server
  -> llama_scx_decode_begin/end_v1
  -> PID-specific uprobes
  -> BPF TGID phase state
  -> sched_ext callback observations
```

M11R packages the already validated path; it does not add a phase-aware
scheduling policy. The scheduler continues to use `SCX_OPS_SWITCH_PARTIAL`, and
only the explicitly selected server process/tasks enter `SCHED_EXT`.

## Quick Start

On a supported Ubuntu host with sched_ext, matching kernel headers, BTF, and a
CPU-runnable GGUF model:

```bash
git clone https://github.com/codinghuman0/llama-scheduler.git
cd llama-scheduler

./scripts/bootstrap_ubuntu.sh --install-deps

./scripts/validate_phase.sh \
    --model /path/to/model.gguf
```

The bootstrap clones the semantic fork into ignored
`.deps/llama.cpp-semantic`, checks out the exact revision in
[config/versions.env](config/versions.env), builds both projects, and runs
unprivileged tests. It does not download a model, install a GPU stack, change a
kernel, or load sched_ext.

The validator is run by the normal user. It invokes `sudo` for
`llama_scx_simple` only; `llama_scx_child` and `llama-server` remain the normal
user. A successful run ends with:

```text
semantic_acceptance=PASS
result_dir=/absolute/path/to/llama-scheduler/results/m11r/...
```

## Requirements

The release path supports Ubuntu on x86-64 and requires:

- a kernel exposing sched_ext, `/sys/kernel/sched_ext/state`, BTF at
  `/sys/kernel/btf/vmlinux`, and the SCX kfuncs used by this repository;
- headers matching the running kernel;
- C/C++ build tools, Clang, CMake with Unix Makefiles, bpftool, libbpf,
  libelf, zlib, Python 3, curl, Git, binutils, and ripgrep;
- passwordless sudo or an interactive sudo prompt for the loader;
- a compatible, locally supplied, CPU-runnable GGUF model.

The validated model belongs to the DeepSeek-R1-Distill-Qwen-1.5B Q4_K_M
family. That is evidence for this model family, not a claim that every GGUF
model behaves equivalently. Models and GGUF files are ignored and must not be
committed.

The validated host is Ubuntu 24.04, x86-64, Ryzen 5 5500U (6 cores/12 logical
CPUs), kernel `7.0.0-29-generic`. See
[docs/COMPATIBILITY.md](docs/COMPATIBILITY.md) before interpreting results from
another machine.

## Bootstrap

Run without package installation when dependencies are already present:

```bash
./scripts/bootstrap_ubuntu.sh
```

Use `--install-deps` only when you explicitly want the printed Ubuntu package
command to run:

```bash
./scripts/bootstrap_ubuntu.sh --install-deps
```

The bootstrap:

1. reports OS, architecture, kernel, CPU count, toolchain, bpftool/libbpf, and
   sched_ext state;
2. verifies kernel BTF and required SCX symbols;
3. reports `VALIDATED`, `COMPATIBLE-BUT-UNVALIDATED`, or `UNSUPPORTED`;
4. clones/fetches the semantic fork, checks out the manifest SHA detached, and
   refuses a dirty or mismatched dependency;
5. builds a shared, CPU-only semantic server with phase tracing;
6. verifies both marker symbols in `libllama-server-impl.so`;
7. builds the scheduler, BPF object, launcher, and test workloads;
8. runs `make check`; and
9. writes ignored build metadata to `build/reproducibility.env`.

A successful build on a different kernel is not a validated runtime result.
The final validator is the environment-specific acceptance test.

The GitHub Actions workflow runs syntax and portable Python checks only. It
does not invoke sudo, load sched_ext, attach BPF, run inference, or certify the
semantic runtime path.

## Validation

Normal usage needs one terminal:

```bash
./scripts/validate_phase.sh --model /path/to/model.gguf
```

Optional controls are:

```bash
./scripts/validate_phase.sh \
    --model /path/to/model.gguf \
    --port 18080 \
    --run-id 11 \
    --output-dir results/m11r/my-run
```

`--output-dir` names an exact new directory and is never overwritten. With no
port, the script selects an available localhost port. With no run ID, it uses a
nonzero UTC-derived marker ID.

The validator refuses root invocation, a missing/dirty/wrong semantic
dependency, a busy sched_ext state, an ambiguous existing `llama-server`, an
unavailable port, missing marker symbols, or missing build outputs. It then:

- starts only the loader through sudo;
- launches a normal-user one-slot, CPU-only server through
  `llama_scx_child`;
- verifies UID, PPID, scheduler policies, registration/target PID equality,
  and that every observed `SCHED_EXT` task belongs to the selected server TGID;
- sends one short completion with `n_predict=8`, `temperature=0`, and
  `cache_prompt=false`;
- shuts down its own server and loader by recorded PID/process group;
- confirms sched_ext returns to `disabled`; and
- evaluates the final instrumentation report.

Ctrl+C, SIGTERM, normal success, and validation failures all enter the same
targeted cleanup path. The script never uses `killall` or `pkill`.

Each run keeps authoritative evidence together under `results/m11r/`:

```text
loader.log
server.log
validation.log
health.json
health.headers
request.json
completion.headers
completion.json
isolation.json
environment.json
instrumentation.json
summary.txt
loader-report/
```

The nested `loader-report/` contains the loader-owned originals; the top-level
instrumentation files are copied into the run bundle after graceful unload.
No shared fixed `/tmp` log is used.

## Expected PASS

Acceptance requires all of the following:

- the invoking shell and launcher are normal-user `SCHED_NORMAL`, while only
  the selected server TGID is `SCHED_EXT`;
- server PID, registration PID, and uprobe target TGID are identical;
- the completion is HTTP 200, valid JSON, and predicts at least one token;
- semantic begin/end events are nonzero and balanced;
- PREFILL and DECODE begin counters are nonzero;
- ABI, user-read, unsupported-phase, stale-end, map-update, and filtered-event
  counters are all zero;
- final phase state is inactive/UNKNOWN;
- both `PREFILL.running` and `DECODE.running` are nonzero; and
- final sched_ext state is `disabled`.

MIXED counters are preserved and reported. MIXED is never relabeled and is not
an automatic failure for this baseline.

## Architecture

The privileged boundary is deliberately narrow:

```text
normal user: validate_phase.sh
    |
    +-- sudo build/bin/llama_scx_simple
    |       loader + BPF + PID-specific uprobes
    |
    +-- build/bin/llama_scx_child
            |
            +-- build/m11r/llama-semantic/bin/llama-server (SCHED_EXT)
```

The one-shot abstract registration socket authenticates the normal-user
launcher and exact server child. Semantic phase traffic itself travels through
the marker uprobes, not the registration socket. Phase information remains
observation-only in M11R: CPU selection, DSQ policy, slice, vtime, migration,
and SMT behavior are unchanged.

## Supported and validated environments

Only the recorded laptop/kernel/model path is currently `VALIDATED`. A
different Ubuntu x86-64 kernel with the required BTF/kfunc surface may be
reported as `COMPATIBLE-BUT-UNVALIDATED` and may continue, but a passing runtime
then constitutes a new environment result. Missing required capabilities are
`UNSUPPORTED`; the scripts never make automatic kernel changes.

The evidence table and procedure for adding a tested machine are in
[docs/COMPATIBILITY.md](docs/COMPATIBILITY.md).

## Experimenting from the baseline

Do not implement policy experiments on the immutable baseline tag. After the
release is reviewed and tagged `m11-semantic-phase-baseline-v1`, create a
separate `experiment/<name>` branch, preserve the semantic revision and
baseline validator, and change one scheduling dimension at a time.

See [docs/EXPERIMENT_GUIDE.md](docs/EXPERIMENT_GUIDE.md) and the reusable
[prompts/PHASE_POLICY_EXPERIMENT.md](prompts/PHASE_POLICY_EXPERIMENT.md).

## Documentation

- [docs/LLAMA_PHASE.md](docs/LLAMA_PHASE.md): semantic ABI/design and historical
  three-terminal debug procedure
- [docs/INSTRUMENTATION.md](docs/INSTRUMENTATION.md): bounded instrumentation
  schema and limitations
- [docs/COMPATIBILITY.md](docs/COMPATIBILITY.md): validated environment matrix
- [docs/EXPERIMENT_GUIDE.md](docs/EXPERIMENT_GUIDE.md): team policy experiment
  discipline
- [docs/STATUS.md](docs/STATUS.md): milestone history
- [docs/VALIDATION.md](docs/VALIDATION.md): earlier synthetic baseline suite
- [docs/M10B.md](docs/M10B.md): neutral `/proc/stat` load-signal feasibility

The repository is GPL-2.0. The Linux `scx_simple` provenance reference is under
`third_party/linux-v6.17/`.
