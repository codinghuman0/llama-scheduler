# Instructions for llama.cpp-fork

## Project scope

This is a personal fork of llama.cpp used solely for a graduation project. Its changes will not be contributed to `ggml-org/llama.cpp`. The project studies CPU resource management for LLM inference by distinguishing Prefill, Decode, and Mixed work and connecting that information to the separate `llama-scheduler` sched_ext project.

These instructions govern work in this fork. The inherited [CONTRIBUTING.md](CONTRIBUTING.md) describes upstream contribution procedures; it is reference material, not an approval gate for this graduation project. Preserve the upstream license, copyright notices, and attribution.

## Working with the project owner

- AI-assisted implementation, debugging, tests, experiments, and documentation are allowed. Carry out requested work within the agreed scope.
- Explain design choices, behavior, tradeoffs, and validation so the owner can review the work and defend it in the graduation project.
- Do not require upstream issue searches, maintainer approval, contribution eligibility checks, or comprehension quizzes before local work.
- Read the relevant implementation and documentation before editing. Reuse existing infrastructure and keep changes small enough to review.
- Ask when a material design decision or expansion of scope is unresolved. Do not repeatedly ask for approval for work the owner has already authorized.
- When external web research is needed, prefer the Exa plugin. Use built-in web search only when Exa is unavailable or unsuitable.

## Repository and Git boundaries

- Inspect the branch, remotes, and working-tree status before editing. Preserve unrelated changes, experiment artifacts, and local configuration.
- Do not stage, commit, push, reset, clean, discard, or rewrite history unless the user explicitly requests that action. A request to edit files is not permission to publish them.
- When a commit is explicitly requested, use a concise message and an `Assisted-by: <assistant name>` trailer for meaningful AI assistance.
- Before an authorized push, verify the destination is the owner's fork and the intended branch. Upstream submission rules do not block an explicitly requested personal-fork push.
- Do not open issues, submit pull requests, or post comments to the original llama.cpp repository. This project has no upstream contribution workflow.
- The sibling `llama-scheduler` checkout is a separate repository. Inspect it when needed to understand the integration, but modify it only when the requested scope includes it, and follow its own instructions.
- If Git reports dubious ownership, use a command-scoped `git -c safe.directory=...` for the verified checkout instead of changing global Git settings.

## Architecture to preserve

Keep these responsibilities distinct:

| Layer | Responsibility |
| --- | --- |
| Application / `llama-server` | Track token origin, classify submitted batches, manage requests, and select a compute profile. |
| libllama / ggml | Execute a decode call with the configured thread count and threadpool; split logical batches into physical ubatches. |
| `llama-scheduler` | Observe phase information and schedule opted-in Linux tasks through sched_ext. Kernel scheduling policy lives in that repository. |

- `AUTO`, `GENERATION`, and `BATCH` are resource profiles, not semantic phases. Do not infer Prefill or Decode from token count: one-token Prefill, multi-request Decode, and Mixed batches are valid.
- `llama_decode_with_options()` applies an explicit profile to every physical ubatch in one call. It does not choose separate resources per token or sequence. `AUTO` retains the existing per-ubatch selection behavior.
- Preserve the default `llama_decode()` path and server `legacy` mode unless the task explicitly changes them. Experimental routing and tracing should remain opt-in.
- The server's `phase` mode maps Prefill to `BATCH`, Decode to `GENERATION`, and Mixed or Unknown work to `AUTO` for its supported decoder path.
- Thread-count and threadpool selection do not reserve CPU cores, establish fixed worker identities, or provide independent concurrent Prefill/Decode execution.
- `LLAMA_SCX_PHASE_TRACE` is a default-OFF Linux observation bridge. Its supported scope is a single CPU-only, decoder-only text-generation context with explicit `-ngl 0`, without GPU/BLAS, speculative decoding, multimodal, embedding, or router modes.
- The phase markers are optional uprobe symbols, not a public libllama phase API. Preserve the versioned wire layout and marker symbols unless an integration change is explicitly in scope; coordinate provider and consumer changes.
- Observation and phase delivery are not evidence that a phase-aware CPU allocation policy or a performance improvement exists.

## Implementation conventions

- Follow the surrounding C/C++ style: simple control flow, 4-space indentation, existing naming, and minimal dependencies.
- Keep code comments concise, usually 1-2 lines, and explain only non-obvious behavior or invariants. Do not narrate the user's request in comments.
- Use ASCII punctuation in code and comments. Do not hard-wrap prose or comments merely to reach a fixed column width.
- Avoid unrelated formatting, generated-file churn, new subsystems, and broad API changes when existing mechanisms suffice.
- Keep CLI help, argument parsing, tests, and documentation consistent when changing options.
- Preserve non-experimental behavior and platform guards. Linux-only instrumentation must not break ordinary Windows builds.
- Chat templates use the Jinja engine in `common/jinja`, not Minja.

## Validation and experiment evidence

- Run checks appropriate to the change. For documentation-only edits, verify paths, commands against source, and the diff; a full inference build is not required.
- For compute-profile changes, build the affected targets and run `test-compute-profile`. Include `test-arg-parser` when changing flags and the focused server tests when changing server behavior.
- For phase-routing changes, cover one-token Prefill, multi-request Decode, Mixed/Unknown fallback, split/retry ranges, cancellation, and slot reuse as relevant. Require trace evidence for the batch composition actually exercised.
- For marker changes, check OFF and ON builds and the affected OpenMP/native-threadpool paths. Keep default-OFF behavior usable.
- Use fresh output directories for experiments. Preserve archived `results/` data and record revisions, dirty state, build flags, host/kernel, model identity, workload, thread counts, affinity, seeds, commands, and repetitions.
- Separate diagnostic tracing from performance runs: synchronization and marker collection affect timing. Compare equivalent workloads against a stated baseline and report latency distributions, throughput, and interference where relevant.
- Distinguish source inspection, unit tests, userspace marker observations, BPF compilation, native verifier/attachment results, and actual SCHED_EXT execution. None substitutes for the next.
- Windows and WSL can support ordinary development and userspace checks. Native sched_ext claims require a compatible Linux kernel, its BTF/UAPI, and actual selected-task execution evidence. Do not assume the current WSL kernel supports sched_ext.
- Kernel installation, reboot, privileged scheduler loading, and uprobe attachment require explicit user authorization. Keep inference workloads unprivileged and limit elevated work to the required loader operations.
- Report what ran, what passed, what failed, and what remains unverified. Historical reports describe their recorded revisions and environments; do not present them as fresh validation of the current checkout.

## Starting points

- [Project overview and quick start](README.md)
- [Compute-profile API, server modes, and phase-marker contract](docs/development/compute-profile.md)
- [Public API](include/llama.h) and [decode execution](src/llama-context.cpp)
- [Server batch classification and routing](tools/server/server-context.cpp)
- [Server marker ABI](tools/server/server-scx.h) and [CPU worker implementation](ggml/src/ggml-cpu/ggml-cpu.c)
- [Batched benchmark](tools/batched-bench/README.md), [build guide](docs/build.md), and [server tests](tools/server/tests/README.md)
- [Archived server experiment](results/compute-profile-20260905T044005Z/README.md)
- [Repository skills](skills/) when a workflow matches the task; inherited upstream submission steps do not apply to local fork work.
