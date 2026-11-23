# llama.cpp

![llama](https://raw.githubusercontent.com/ggml-org/llama.brand/refs/heads/master/cover/llama-cpp/cover-llama-cpp-dark.svg)

<div align="center">

<b>LLM inference in C/C++</b>

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Release](https://img.shields.io/github/v/release/ggml-org/llama.cpp)](https://github.com/ggml-org/llama.cpp/releases)
[![Server](https://github.com/ggml-org/llama.cpp/actions/workflows/server.yml/badge.svg)](https://github.com/ggml-org/llama.cpp/actions/workflows/server.yml)
[![Docker](https://github.com/ggml-org/llama.cpp/actions/workflows/docker.yml/badge.svg)](https://github.com/ggml-org/llama.cpp/actions/workflows/docker.yml)
[![Winget](https://github.com/ggml-org/llama.cpp/actions/workflows/winget.yml/badge.svg)](https://github.com/ggml-org/llama.cpp/actions/workflows/winget.yml)

[manifesto](https://github.com/ggml-org/llama.cpp/discussions/205) / [ggml](https://github.com/ggml-org/ggml) / [ops](https://github.com/ggml-org/llama.cpp/blob/master/docs/ops.md) / [maintainer PRs](https://github.com/ggml-org/llama.cpp/issues?q=is%3Apr%20is%3Aopen%20draft%3AFalse%20(author%3Argerganov%20OR%20author%3AKitaitiMakoto%20OR%20author%3Adanbev%20OR%20author%3Aaldehir%20OR%20author%3Amax-krasnyansky%20OR%20author%3ACISC%20OR%20author%3Aggerganov%20OR%20author%3Aam17an%20OR%20author%3Abartowski1182%20OR%20author%3Ahipudding%20OR%20author%3AServeurpersoCom%20OR%20author%3Apwilkin%20OR%20author%3Areeselevine%20OR%20author%3Angxson%20OR%20author%3Ajeffbolznv%20OR%20author%3A0cc4m%20OR%20author%3Aangt%20OR%20author%3AIMbackK%20OR%20author%3Aarthw%20OR%20author%3AJohannesGaessler%20OR%20author%3AORippler%20OR%20author%3Aruixiang63%20OR%20author%3Axctan%20OR%20author%3Aallozaur%20OR%20author%3Ayomaytk%20OR%20author%3Aaendk%20OR%20author%3Agaugarg-nv%20OR%20author%3Ataronaeo%20OR%20author%3Aforforever73%20OR%20author%3Alhez%20OR%20author%3Anetrunnereve%20OR%20author%3Afairydreaming)%20sort%3Aupdated-desc) / [dev branches](https://github.com/ggml-org/llama.cpp-dev/blob/master/README-features.md) / [compile times](https://github.com/ggml-org/llama.cpp-dev/blob/master/README-compile-times.md) / [lib llama API](https://github.com/ggml-org/llama.cpp/issues/9289) / [llama-server REST API](https://github.com/ggml-org/llama.cpp/issues/9291)

</div>

## Portable Lightweight Base quick start

Supported hosts are Linux x86_64 with working sched_ext, kernel BTF, BPF syscall/configuration, matching kernel sched_ext UAPI headers, and a supported clang/libbpf toolchain. Ubuntu is the automated dependency installation path. Missing kernel facilities produce BLOCKED; there is no fallback scheduler.

```sh
git clone --branch lightweight-base https://github.com/codinghuman0/llama-scheduler-base.git
cd llama-scheduler-base
# Place the team's model.gguf next to this repository (../model.gguf).
./tools/sched_ext/bench/clean_room_setup.sh
# Explicit alternative: MODEL=/path/to/model.gguf ./tools/sched_ext/bench/clean_room_setup.sh
```

The model must be exactly 1117321312 bytes with SHA256 `f3bdf9cf31dee4b57ae4e455a1cb0d01b5c2c1b50d72d3112141c195506c2840`. Setup installs dependencies, checks the host, detects topology, builds the unchanged Base and neutral scheduler, runs correctness smoke, and generates ignored `benchmark-results/host-profile.json`. Expect `CLEAN_ROOM_SETUP_RESULT=PASS`. No performance campaign runs during setup. Optional frequency, temperature and power interfaces are recorded when exposed; setup never changes power settings.

For the frozen A/B/C/D benchmark, close Firefox, all Codex sessions and unnecessary applications, then run these sequentially as the repository's normal user from one terminal:

```sh
./tools/sched_ext/bench/step10_phase_a_prepare.sh
./tools/sched_ext/bench/step10_phase_b_arm.sh
./tools/sched_ext/bench/step10_phase_c_campaign.sh
./tools/sched_ext/bench/step10_phase_d_finalize.sh
```

Keep applications closed through Phase D. Results and raw evidence live in `benchmark-results/step10/<UTC-run-id>/`; `.active-run` identifies the current directory. Every run retains its frozen host profile and hash. See [benchmark instructions](tools/sched_ext/bench/README.md) for dry-runs, readiness and profile refresh. At least two usable physical cores are required for an isolated performance campaign; correctness setup/smoke is separate.

For Season 2, create one policy branch per hypothesis from the reviewed portable Base commit, retain its immutable tags, and follow the [Season 2 experiment protocol](tools/sched_ext/SEASON2_EXPERIMENT_PROTOCOL.md). Share the generated result directory for review.

## 이 저장소에 대하여

이 저장소는 CPU-only LLM inference 환경에서 Linux `sched_ext` 기반 스케줄링을 연구하기 위해 수정한 `llama.cpp` fork입니다.

현재 `Lightweight Base v1`은 향후 phase-aware, load-aware, topology-aware scheduling policy를 실험하기 위한 **중립적인 baseline**입니다.

현재 Base Version에서는 `llama.cpp`가 inference 실행 phase를 분류하여 scheduler 측으로 전달할 수 있지만, scheduler는 아직 이 phase 정보를 scheduling decision에 사용하지 않습니다.

즉 현재 구조는 다음 단계의 정책 실험을 위한 기준점입니다.

```text
Lightweight Base v1
        │
        ├── Phase-aware policy
        ├── Load-aware policy
        ├── Topology-aware policy
        └── Combined policies
```

### 프로젝트 구현 위치

#### 1. Lightweight sched_ext scheduler

실제로 사용되는 scheduler 구현은 [`tools/sched_ext/`](tools/sched_ext/) 아래에 있습니다.

- [`tools/sched_ext/llama_scx.bpf.c`](tools/sched_ext/llama_scx.bpf.c)
  - 실제 BPF `sched_ext` scheduling policy
  - Linux `scx_simple`의 weighted-vtime scheduling을 기반으로 하는 neutral scheduler

- [`tools/sched_ext/llama_scx.c`](tools/sched_ext/llama_scx.c)
  - userspace scheduler loader
  - 대상 `llama-server` 등록
  - phase uprobe 연결
  - scheduler lifecycle 및 cleanup 관리

- [`tools/sched_ext/llama_scx_child.c`](tools/sched_ext/llama_scx_child.c)
  - 선택된 `llama-server`와 해당 process가 생성한 thread를 `SCHED_EXT`에 진입시키기 위한 launcher

- [`tools/sched_ext/include/`](tools/sched_ext/include/)
  - userspace/BPF 사이의 scheduler state 및 control ABI 정의

다음 디렉터리는 실제 performance scheduler와 구분하여 보존합니다.

- [`tools/sched_ext/provenance/`](tools/sched_ext/provenance/)
  - active scheduler 구현의 기준으로 사용한 Linux sched_ext 원본 소스

- [`tools/sched_ext/validation/`](tools/sched_ext/validation/)
  - 개발 과정에서 correctness 검증에 사용한 instrumentation-heavy scheduler
  - 실제 성능 측정용 scheduler로는 사용하지 않음

#### 2. llama.cpp phase-hint 경로

`llama.cpp`에는 현재 inference가 어떤 phase에 있는지 판단하여 scheduler 측으로 전달하기 위한 lightweight phase-hint 경로가 추가되어 있습니다.

개념적인 흐름은 다음과 같습니다.

```text
semantic batch 확인
        ↓
UNKNOWN / PREFILL / DECODE / MIXED 분류
        ↓
직전 phase와 비교
        ↓
phase가 변경되었는가?
        ├── 아니오 → 기존 실행 계속
        └── 예     → llama_scx_phase_v1(uint32_t) 호출
```

동일한 phase가 계속되는 동안에는 marker를 반복 호출하지 않고, **phase transition이 발생했을 때만** marker를 호출합니다.

Lightweight configuration은 다음과 같습니다.

```text
LLAMA_SCX_PHASE_HINT=ON
LLAMA_SCX_PHASE_TRACE=OFF
```

과거 correctness 검증에 사용했던 begin/end tracing 및 GGML worker tracing은 이 configuration에서는 활성화되지 않습니다.

Phase-hint 동작을 이해하기 위해 우선 확인할 파일은 다음과 같습니다.

- [`tools/server/server-phase.h`](tools/server/server-phase.h)
  - server 측 phase 분류 관련 정의

- [`tools/server/server-scx.h`](tools/server/server-scx.h)
  - `llama_scx_phase_v1()` marker 및 SCX 연동

- [`tools/server/server-context.cpp`](tools/server/server-context.cpp)
  - 실제 server inference 경로와 phase classification을 연결하는 핵심 코드

- [`src/llama-context.cpp`](src/llama-context.cpp)
- [`src/llama-context.h`](src/llama-context.h)
- [`include/llama.h`](include/llama.h)
  - compute profile 및 llama decode 실행 경로를 지원하기 위한 llama-side 변경

추가적인 configuration 및 compute-profile 관련 변경은 다음 파일에 포함되어 있습니다.

- [`common/arg.cpp`](common/arg.cpp)
- [`common/common.h`](common/common.h)
- [`src/llama-kv-cache.cpp`](src/llama-kv-cache.cpp)
- [`ggml/src/ggml-cpu/ggml-cpu.c`](ggml/src/ggml-cpu/ggml-cpu.c)
- [`CMakeLists.txt`](CMakeLists.txt)
- [`tools/server/CMakeLists.txt`](tools/server/CMakeLists.txt)

테스트, benchmark 및 이전 검증 결과도 저장소에 포함되어 있지만, 위 파일들이 현재 runtime path를 이해하기 위한 주요 구현입니다.

### Phase 정보 전달 구조

scheduler 측 active control state는 다음 세 값만 유지합니다.

```c
uint32_t selected_tgid;
uint32_t current_phase;
uint32_t exit_kind;
```

선택된 `llama-server`에 PID-scoped uprobe 하나를 연결하여

```text
llama_scx_phase_v1(uint32_t phase)
```

호출을 관측하고 `current_phase`를 갱신합니다.

현재 neutral Base의 scheduling callback은 `current_phase`를 읽거나 scheduling decision에 사용하지 않습니다.

따라서 현재 버전의 목적은 **phase 전달 infrastructure 자체의 비용과 sched_ext baseline을 먼저 검증한 뒤, 이후 policy 효과를 독립적으로 비교할 수 있는 기준점을 만드는 것**입니다.

### 검증 결과

`Lightweight Base v1`은 다음 항목을 검증한 상태입니다.

- 선택된 `llama-server` 및 해당 thread만 `SCHED_EXT`에서 실행
- 다른 일반 process는 기존 Linux scheduler에 유지
- PREFILL → DECODE phase 전달 확인
- phase-hint transport의 성능 overhead 검증
- neutral sched_ext baseline의 성능 검증
- clean-clone 가능한 release checkpoint 생성

Base Version의 최종 release tag:

```text
lightweight-base-v1-release
```

### 상세 문서

보다 자세한 구조 및 검증 결과는 다음 문서를 참고하십시오.

- [`tools/sched_ext/LIGHTWEIGHT_BASE_V1_CHECKPOINT.md`](tools/sched_ext/LIGHTWEIGHT_BASE_V1_CHECKPOINT.md)
  - Base Version의 구조, revision, validation 및 성능 결과

- [`tools/sched_ext/BENCHMARK_PROTOCOL.md`](tools/sched_ext/BENCHMARK_PROTOCOL.md)
  - A/B/C/D benchmark 구성과 측정 방법

- [`tools/sched_ext/README.md`](tools/sched_ext/README.md)
  - sched_ext scheduler의 구조와 사용 방법

---

아래 내용은 upstream `llama.cpp`의 기본 사용법 및 프로젝트 문서입니다.

## Quick start

A few options to get `llama.cpp` installed on your machine:

- Visit https://llama.app and follow the instructions
- Run with Docker - see our [Docker documentation](docs/docker.md)
- Download pre-built binaries from the [releases page](https://github.com/ggml-org/llama.cpp/releases)
- Build from source by cloning this repository - check out [our build guide](docs/build.md)

Once installed:

```sh
# Download and run a model directly from Hugging Face
llama cli -hf ggml-org/Qwen3.5-0.8B-GGUF

# Launch OpenAI-compatible API server
llama serve -hf ggml-org/Qwen3.5-0.8B-GGUF
```

<table align="center">
    <tr>
        <td align="center" width=50%>
            <img width="1310" height="888" alt="VLM session with `llama cli`" src="https://github.com/user-attachments/assets/88726b48-1713-48aa-a525-95a02e78afc4" />
            <i>VLM session with <b>llama cli</b></i>
        </td>
        <td align="center">
            <img width="1392" height="958" alt="Built-in web UI against `llama serve` running Qwen 3.6" src="https://github.com/user-attachments/assets/b402f972-2e32-4def-8771-8d849f08cf2e" />
            <i>Built-in web UI against <b>llama serve</b></i>
        </td>
    </tr>
<table>

## Description

The main goal of `llama.cpp` is to enable LLM (and VLM) inference with minimal setup and state-of-the-art performance on
a wide range of hardware - locally and in the cloud.

- Plain C/C++ implementation without any dependencies
- Apple silicon is a first-class citizen - optimized via ARM NEON, Accelerate and Metal frameworks
- AVX, AVX2, AVX512 and AMX support for x86 architectures
- RVV, ZVFH, ZFH, ZICBOP and ZIHINTPAUSE support for RISC-V architectures
- 1.5-bit, 2-bit, 3-bit, 4-bit, 5-bit, 6-bit, and 8-bit integer quantization for faster inference and reduced memory use
- Custom CUDA kernels for running LLMs on NVIDIA GPUs (support for AMD GPUs via HIP and Moore Threads GPUs via MUSA)
- Vulkan and SYCL backend support
- CPU+GPU hybrid inference to partially accelerate models larger than the total VRAM capacity

The `llama.cpp` project is build on top of the [ggml](https://github.com/ggml-org/ggml) library.

## Supported backends

| Backend | Target devices |
| --- | --- |
| [BLAS](docs/build.md#blas-build) | All |
| [BLIS](docs/backend/BLIS.md) | All |
| [CANN](docs/build.md#cann) | Ascend NPU |
| [CUDA](docs/build.md#cuda) | Nvidia GPU |
| [HIP](docs/build.md#hip) | AMD GPU |
| [Hexagon [In Progress]](docs/backend/snapdragon/README.md) | Snapdragon |
| [IBM zDNN](docs/backend/zDNN.md) | IBM Z & LinuxONE |
| [MUSA](docs/build.md#musa) | Moore Threads GPU |
| [Metal](docs/build.md#metal-build) | Apple Silicon |
| [OpenCL](docs/backend/OPENCL.md) | Adreno GPU |
| [OpenVINO [In Progress]](docs/backend/OPENVINO.md) | Intel CPUs, GPUs, and NPUs |
| [RPC](https://github.com/ggml-org/llama.cpp/tree/master/tools/rpc) | All |
| [SYCL](docs/backend/SYCL.md) | Intel GPU |
| [VirtGPU](docs/backend/VirtGPU.md) | VirtGPU APIR |
| [Vulkan](docs/build.md#vulkan) | GPU |
| [WebGPU](docs/build.md#webgpu) | All |
| [ZenDNN](docs/build.md#zendnn) | AMD CPU |

## Documentation

#### Tools

- [cli](tools/cli/README.md)
- [completion](tools/completion/README.md)
- [server](tools/server/README.md)
- [GBNF grammars](grammars/README.md)

#### Development

- [How to build](docs/build.md)
- [Running on Docker](docs/docker.md)
- [Build on Android](docs/android.md)
- [Multi-GPU usage](docs/multi-gpu.md)
- [Performance troubleshooting](docs/development/token_generation_performance_tips.md)
- [GGML tips & tricks](https://github.com/ggml-org/llama.cpp/wiki/GGML-Tips-&-Tricks)
- [XCFramework](docs/xcframework.md)
- [Completions](docs/completions.md)
- [Models](docs/models.md)

## Contributing

- Contributors can open PRs
- Collaborators will be invited based on contributions
- Maintainers can push to branches in the `llama.cpp` repo and merge PRs into the `master` branch
- Any help with managing issues, PRs and projects is very appreciated!
- Read the [CONTRIBUTING.md](CONTRIBUTING.md) for more information

## Acknowledgements

- [yhirose/cpp-httplib](https://github.com/yhirose/cpp-httplib) - Single-header HTTP server, used by `llama-server` - MIT license
- [stb-image](https://github.com/nothings/stb) - Single-header image format decoder, used by multimodal subsystem - Public domain
- [nlohmann/json](https://github.com/nlohmann/json) - Single-header JSON library, used by various tools/examples - MIT License
- [miniaudio.h](https://github.com/mackron/miniaudio) - Single-header audio format decoder, used by multimodal subsystem - Public domain
- [subprocess.h](https://github.com/sheredom/subprocess.h) - Single-header process launching solution for C and C++ - Public domain
