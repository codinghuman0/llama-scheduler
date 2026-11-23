<!-- SPDX-License-Identifier: MIT -->
# Licensing and provenance

This repository is a llama.cpp fork with a separately licensed Linux sched_ext component. The top-level [MIT LICENSE](LICENSE), including Copyright (c) 2023-2026 The ggml authors, is retained unchanged. It is not a declaration that every bundled file has the same license. File-level notices and component licenses remain applicable; this notice does not relicense third-party code.

## Component inventory

| Component | Origin and license evidence |
| --- | --- |
| Ordinary llama.cpp source and documentation | [ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp); MIT under `LICENSE`, subject to the separately identified bundled components below. The original performance baseline is commit `7a2db1a0cf38e5f4eb278a58c3903d295258d0ea`. |
| Fork changes in `common/`, `include/`, `src/`, `ggml/src/ggml-cpu/ggml-cpu.c`, `tools/server/` and `examples/batched-bench/` | Project changes to the MIT llama.cpp implementation, including compute profiles and the phase marker. They keep the upstream MIT notice and header conventions. The server does not include the GPL scheduler headers or link the scheduler loader. Matching phase ABI declarations are kept on each side. |
| Active `tools/sched_ext/llama_scx.bpf.c` | Linux v6.17 `tools/sched_ext/scx_simple.bpf.c` weighted-vtime callbacks, plus project partial scheduling and phase input. Compatibility macros also match Linux `tools/sched_ext/include/scx/common.bpf.h`. GPL-2.0 SPDX, upstream author notices and the BPF GPL license section are retained. |
| Active `tools/sched_ext/llama_scx.c` | Linux v6.17 `scx_simple.c` lifecycle base, rewritten for direct libbpf loading, with narrow control-plane mechanisms from the golden project loader. GPL-2.0 SPDX and upstream author notices are retained. |
| `tools/sched_ext/llama_scx_child.c` and `include/llama_sched_uapi.h` | Byte-identical reuse of the project golden selected-child launcher and UAPI wrapper at the Base checkpoint. Both already have GPL-2.0 SPDX notices. The wrapper includes system UAPI headers; it is not a copied complete Linux scheduler header. |
| `tools/sched_ext/include/llama_scx_state.h`, Makefiles, validation headers/tests and `bench/` tooling | Project-authored control declarations, build/validation code and campaign automation, already marked GPL-2.0. Scheduler documentation, including the protocol and Base checkpoint, follows the existing separately licensed subtree scope documented in its README. |
| `tools/sched_ext/provenance/linux-v6.17/` | Unmodified Linux v6.17 source snapshots, GPL-2.0 with their original copyright notices. They are provenance, not the active build inputs. |
| `tools/sched_ext/validation/` | Golden project implementation imported from `codinghuman0/llama-scheduler`, source commit `ffc03c82738e31977cf402061422b0ef0148fe67`. Its BPF scheduling callbacks and userspace lifecycle/statistics retain Linux ancestry; all code carries GPL-2.0 SPDX. Attribution-only corrections are described below. |
| Niels Lohmann JSON and cpp-httplib | MIT notices in [licenses/LICENSE-jsonhpp](licenses/LICENSE-jsonhpp), `vendor/nlohmann/` headers, [vendor/cpp-httplib/LICENSE](vendor/cpp-httplib/LICENSE) and `httplib.h`. |
| Other bundled helpers | `vendor/stb/stb_image.h` offers MIT or public domain; `vendor/miniaudio/miniaudio.h` offers public domain or MIT-0 and retains its embedded notices; `vendor/sheredom/subprocess.h` and `common/base64.hpp` retain Unlicense text. `ggml/src/ggml-cpu/llamafile/sgemm.cpp` retains Mozilla's MIT notice; KleidiAI adapter files retain Arm MIT notices. |
| UI vendor code | Existing MIT notices for `decimal.js` and `nerdamer-prime`, and Unlicense text for `big-integer`, remain under `tools/ui/src/lib/vendors/`. `gguf-py/LICENSE` also retains its separate upstream MIT notice. |
| Apache and LLVM-derived upstream files | Apache-2.0 notices occur in OpenVINO headers, Android `gradlew`, two model templates and the legacy MiniCPM converter. SYCL files retain their MIT notices and `Apache-2.0 WITH LLVM-exception` notices for LLVM portions. Full texts are [licenses/LICENSE-Apache-2.0](licenses/LICENSE-Apache-2.0) and [licenses/LLVM-exception.txt](licenses/LLVM-exception.txt). These copies do not replace the file-level terms. |
| External dependencies | Dependencies downloaded or linked by a build, including libbpf and system libraries, have their own licenses. Package metadata describes additional dependencies but is not evidence that their code is vendored here. Preserve their notices when distributing those dependencies. |

The existing full [scheduler GPLv2 text](tools/sched_ext/LICENSE) is retained; another GPL copy is unnecessary. Linux's `GPL-2.0` identifier denotes version 2 only, distinct from `GPL-2.0+`; the upstream identifier is preserved rather than broadened. See the [Linux licensing rules](https://docs.kernel.org/process/license-rules.html). An ELF `license` section containing `GPL` is not a replacement for source attribution.

## Linux and project provenance

The Linux reference is tag `v6.17`, commit `e5f0a698b34ed76002dc5cff3804a61c80233a7a`. On 2026-10-08 the local snapshots were compared byte for byte with the upstream tag:

| Reference | Upstream source | SHA-256 |
| --- | --- | --- |
| `scx_simple.c` | [Linux userspace example](https://github.com/torvalds/linux/blob/v6.17/tools/sched_ext/scx_simple.c) | `f9a1c7a648575d4415377f7bba668c9064e89519b5b0ec05fd45c8edcc89e59f` |
| `scx_simple.bpf.c` | [Linux BPF example](https://github.com/torvalds/linux/blob/v6.17/tools/sched_ext/scx_simple.bpf.c) | `f8b2d3ab08a326b09e3e7c8a6eeea43991a5b5265ff9bfb4444bf459e36e3f59` |

Their original author notices are Copyright (c) 2022 Meta Platforms, Inc. and affiliates; Copyright (c) 2022 Tejun Heo <tj@kernel.org>; and Copyright (c) 2022 David Vernet <dvernet@meta.com>. The same notices are retained in the active Linux-derived files.

Git records the provenance import at `98c0a2606c6ff846ae091fd9c9d76be7983a2e32`, the golden validation import at `542850645a54fc2e35a9a8189ff8dfcf35b9c51d`, and the active neutral implementation at `ea4a36bbad1100d7d3f7c6aa57caadcb782a26fa`. The active scheduler keeps weighted-vtime ordering, default idle CPU selection and partial switching. It removes the example FIFO/statistics paths and adds selected-child lifetime control and a PID-scoped phase uprobe. Scheduling callbacks remain phase-independent. The launcher and UAPI wrapper were reused in full; the instrumented golden BPF scheduler was not used as the active implementation base.

On 2026-10-08, this publication audit restored omitted Linux author notices in `validation/src/llama_scx_simple.bpf.c` and `validation/src/llama_scx_simple.c`. Only their leading comments changed. Their behavior and existing SPDX identifiers are unchanged; the original golden bytes remain available from the import commit/tag. The provenance snapshots, active implementation and frozen llama-side files are unchanged.

The Apache text is copied from [the Apache Software Foundation](https://www.apache.org/licenses/LICENSE-2.0.txt), and the exception is copied verbatim from the exception section of [LLVM's license](https://llvm.org/LICENSE.txt). The existing upstream file notices referenced these terms but the complete texts were absent locally. One shared Apache text plus its separate LLVM exception avoids duplicating the complete Apache license.

## Source, binaries and model boundary

This audit concerns publication of the source repository with its notices and history. It is not a license grant for externally supplied model weights or a compliance manifest for a future binary release. Distribution of GPL scheduler binaries must satisfy GPLv2 source and notice requirements, including corresponding source/build material, and account for any distributed dependencies. The normal llama.cpp server and privileged scheduler loader remain separate executables.

The benchmark model `/home/codinghuman/projects/model.gguf`, runtime bundles, build outputs and `benchmark-results/` are not tracked and must not be uploaded. No license claim is made about that external model. Nineteen inherited `models/ggml-vocab-*.gguf` fixtures remain tracked, unchanged from upstream: each has zero tensors and supplies tokenizer/vocabulary metadata, not inference model weights. Their presence must not be confused with distribution of the benchmark model or a general license grant for other model/tokenizer assets. Existing small `results/compute-profile-20260905T044005Z/` experiment records are historical tracked evidence, not Step 10 runtime bundles.

## Publication and checkpoint preservation

The licensing clarification is a later, documentation/comment-only commit on `lightweight-base`. It does not rewrite history or change the validated checkpoint meanings:

| Tag | Commit target |
| --- | --- |
| `original-performance-baseline-v1` | `7a2db1a0cf38e5f4eb278a58c3903d295258d0ea` |
| `llama-side-lightweight-v1` | `c8b9d61d12b4997d902a03e5dc55a185d18c3bc9` |
| `one-repo-golden-validation-v1` | `542850645a54fc2e35a9a8189ff8dfcf35b9c51d` |
| `neutral-sched-ext-base-v1` | `ea4a36bbad1100d7d3f7c6aa57caadcb782a26fa` |
| `lightweight-base-v1` | `4471b80d6ef1001d126611c0cb9cec6feb58880e` |

For the completed architecture, validation and measured-host result, read [Lightweight Base v1](tools/sched_ext/LIGHTWEIGHT_BASE_V1_CHECKPOINT.md). C -> D is the neutral sched_ext-base delta including weighted-vtime semantics, not pure framework overhead. No optimization policy is introduced by this audit.

Create an empty repository under GitHub owner `codinghuman0`, with no generated README, license or gitignore. The name is the owner's choice; `llama.cpp-lightweight` is a suggested name, not a configured destination. Keep `origin` unchanged and use `personal` for the new repository. After explicit publication authorization, the future commands are:

```sh
git remote add personal <NEW_GITHUB_REPOSITORY_URL>
git ls-remote personal
git -c push.followTags=false push --atomic personal \
  refs/heads/lightweight-base:refs/heads/lightweight-base \
  refs/tags/original-performance-baseline-v1:refs/tags/original-performance-baseline-v1 \
  refs/tags/llama-side-lightweight-v1:refs/tags/llama-side-lightweight-v1 \
  refs/tags/one-repo-golden-validation-v1:refs/tags/one-repo-golden-validation-v1 \
  refs/tags/neutral-sched-ext-base-v1:refs/tags/neutral-sched-ext-base-v1 \
  refs/tags/lightweight-base-v1:refs/tags/lightweight-base-v1
git ls-remote personal refs/heads/lightweight-base 'refs/tags/original-performance-baseline-v1*' 'refs/tags/llama-side-lightweight-v1*' 'refs/tags/one-repo-golden-validation-v1*' 'refs/tags/neutral-sched-ext-base-v1*' 'refs/tags/lightweight-base-v1*'
```

Replace the URL placeholder only with the new owner-controlled repository URL. If `personal` already exists, inspect it instead of replacing it. Stop for any conflicting remote branch/tag; do not force-update refs. Push the licensing follow-up branch and the unchanged checkpoint tags together, then independently verify remote ref objects and peeled commit targets. Do not initialize a replacement Git history or publish unrelated local branches/tags. This audit adds no remote and performs no push.
