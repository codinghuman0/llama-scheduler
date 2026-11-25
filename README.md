# llama-scheduler

## Intel·AMD CPU 실험

Ubuntu x86-64 일반 계정에서 원본 모델을 `~/projects/model.gguf`에 둡니다. 아래 명령은 `integration-v2`를 처음에는 얕게 클론하고 기존 `~/projects/llama-scheduler` 또는 `~/projects/llama-scheduler-integration-v2`가 있으면 그 폴더에서 업데이트합니다. 변경이 있거나 커밋 이력이 갈라진 체크아웃은 경로와 함께 알려줍니다.

```bash
runner=$(mktemp) &&
curl -fsSL https://raw.githubusercontent.com/codinghuman0/llama-scheduler/integration-v2/scripts/run-cpu-experiment.sh -o "$runner" &&
bash "$runner" smoke
```

| 모드 | 측정 또는 검증 |
|---|---|
| `smoke` (기본) | 서로 다른 8개 요청을 두 세트로 실행하고 단일 요청도 검사합니다. 입력마다 새 서버를 시작해 측정 tok/s와 결과 경로를 출력합니다. |
| `m4` | native 백엔드로 Decode 4개와 긴 Prefill 1개를 겹쳐 cap128/head64 처리와 출력 토큰을 비교합니다. 허용된 물리 코어 6개가 필요합니다. |
| `prefill-linux` | 기본 Linux 정책에서 짧은 단일·다중 요청과 phase 전송을 확인합니다. |
| `prepare` | 호스트 커널용 BPF를 일반 계정으로 빌드하고 두 정책의 체크포인트를 생성합니다. |
| `scx` | FULL 계측으로 선택된 서버의 neutral/prefill-pcore 배치와 생성 토큰을 비교합니다. 화면에 출력된 각 loader 명령을 다른 터미널에서 실행합니다. |
| `placement` | 평상시·cpu25 각각 6블록, 세 정책 총 36회 실행 후 블록별 생성 처리율과 95% 구간을 계산합니다. sudo 인증이 가능한 일반 터미널에서 실행합니다. |

다시 실행할 때는 클론 안에서 `bash scripts/run-cpu-experiment.sh 모드`를 사용합니다. 모델 경로는 두 번째 인자, 기존 다른 경로의 저장소는 `NEWA_CHECKOUT`으로 지정할 수 있습니다. 결과·빌드·로그는 `new-a-workspace/state/integration-v2/`에 보관합니다. `smoke`, `prefill-linux`, `prepare`, `scx`, `placement`는 같은 OpenMP 런타임을 검증해 재사용하고 `m4`에는 별도의 native 빌드를 사용합니다.

기본 실험에는 Git, Python 3.10 이상, CMake, GCC/G++, Make, util-linux 및 OpenSSL 개발 헤더가 필요합니다. CPU의 AVX2/FMA/F16C/SSE4.2, cpuset과 할당량에서 실제 사용 가능한 코어를 확인합니다. i5-1240P 형상의 P/E와 동종 Ryzen을 지원합니다. `prepare`, `scx`, `placement`에는 sched_ext/BTF 지원 커널과 clang BPF, bpftool, libbpf·libelf·zlib 개발 파일도 필요합니다. 커널 모드에서 제어용 CPU는 서버 범위 밖에 둡니다.

온도 센서와 고정 디스크·RAM 여유량을 검사하지 않습니다. 데스크톱에 AC 정보가 없어도 공용 실험은 진행합니다. 파일 쓰기·할당·권한 오류는 실제로 발생한 단계에서 한국어로 안내하며 외부 도구의 원문은 로그에 보관합니다. [팀원 실행 안내](new-a-workspace/experiments/team-integration-v2/INTEL_HANDOFF.md) · [AMD 런타임 측정](new-a-workspace/experiments/amd-published-direct-v1/result-summary.md) · [AMD 커널 배치 측정](new-a-workspace/experiments/amd-prefill-placement-ac-v1/result-summary.md)

## Historical Base Project

CPU-only llama.cpp semantic phase-aware `sched_ext` Base Project

## 1. 프로젝트 소개

`llama-scheduler`는 Linux `sched_ext`를 이용해 CPU-only LLM scheduling을 연구하기 위한 공통 Base Project다. 수정된 semantic `llama-server`가 inference 중의 `PREFILL`, `DECODE`, `MIXED`, `UNKNOWN` phase를 제공하고, PID-specific `uprobe`가 이 정보를 eBPF의 TGID별 phase state로 전달한다. `sched_ext` callback에서는 선택된 `llama-server` worker가 실제로 실행될 때의 phase를 관측할 수 있다.

```text
modified llama-server
        |
        | semantic phase marker
        v
      uprobe
        |
        v
 BPF phase state
        |
        v
 sched_ext callbacks
```

현재 scheduler는 phase를 관측하고 계측할 뿐, CPU 선택, DSQ, queue order, vtime, slice 같은 scheduling 결정에는 phase를 사용하지 않는 neutral baseline이다. 따라서 성능을 개선하는 scheduling policy가 구현되었다거나 성능 향상이 입증되었다고 보지 않는다. 이 저장소는 팀원이 동일한 semantic phase 입력과 selected-child isolation 위에서 독립적인 policy 실험을 시작하기 위한 기반이다.

## 2. 현재 상태

| 항목 | 상태 |
|---|---|
| Semantic PREFILL/DECODE detection | 완료 |
| PID-specific uprobe integration | 완료 |
| sched_ext phase observation | 완료 |
| selected-child isolation | 완료 |
| reproducible setup/validation | 완료 |
| phase-aware scheduling policy | 미구현 |
| load-aware scheduling policy | 미구현 |
| performance improvement evaluation | 미수행 |

즉, `phase-aware observability`는 구현되어 있지만 `phase-aware scheduling policy`는 아직 구현되어 있지 않다.

## 3. Codex에 전달할 프로젝트 설명

새 Codex 세션에는 아래 내용을 그대로 전달할 수 있다.

```text
이 저장소는 CPU-only llama.cpp inference를 위한 Linux sched_ext scheduler 연구의 Base Project다.

modified llama-server가 semantic PREFILL/DECODE/MIXED/UNKNOWN phase를 제공하고,
PID-specific uprobe를 통해 eBPF의 TGID별 phase state로 전달된다.

sched_ext callback에서는 실제 selected llama-server worker의 phase를 관측할 수 있다.
현재 scheduling policy 자체는 phase 정보를 scheduling 결정에 사용하지 않는 neutral baseline이다.

이 저장소를 수정할 때:
- semantic phase input을 유지할 것
- selected-child isolation을 유지할 것
- llama-server workload는 normal user로 실행할 것
- privileged loader만 root로 실행할 것
- 한 번에 하나의 scheduling dimension만 변경할 것
- baseline validation을 깨뜨리지 말 것
- 성능 향상은 반복 실험 전에는 주장하지 말 것
- 실험 변경은 가급적 experiment/<name> 브랜치에서 진행할 것
```

## 4. 빠른 설치

지원 경로는 `sched_ext`, kernel BTF, 실행 중인 kernel과 일치하는 headers를 갖춘 Ubuntu x86-64 환경이다.

```bash
git clone https://github.com/codinghuman0/llama-scheduler.git
cd llama-scheduler

./scripts/bootstrap_ubuntu.sh --install-deps
```

bootstrap은 환경과 kernel capability를 검사하고, [config/versions.env](config/versions.env)에 고정된 semantic llama.cpp fork를 `.deps/llama.cpp-semantic`에 받아 CPU-only semantic server를 빌드한다. 이어서 scheduler와 BPF 구성 요소를 빌드하고 unprivileged tests를 실행한다.

현재 고정된 semantic revision은 `5219055a578fd741e029e81fefef6f3a5695086d`다. bootstrap은 kernel을 변경하거나 scheduler를 load하지 않으며 GPU dependency와 model도 설치하지 않는다. 시스템 dependency가 이미 준비되어 있다면 `--install-deps` 없이 실행할 수 있다.

## 5. Phase 연결 검증

호환되는 CPU-runnable GGUF model을 준비한 뒤 normal user shell에서 실행한다.

```bash
./scripts/validate_phase.sh \
    --model /path/to/model.gguf
```

이 검증은 semantic `llama-server -> uprobe -> BPF phase state -> sched_ext callback` 경로와 selected-child isolation을 한 번의 controlled inference로 확인한다. 내부적으로 `llama_scx_simple` loader만 `sudo`를 사용하며, `llama_scx_child`와 `llama-server`는 계속 normal-user process로 실행된다.

성공한 실행의 마지막에는 다음 결과와 run별 evidence directory가 출력된다.

```text
semantic_acceptance=PASS
result_dir=/absolute/path/to/result
```

GGUF model은 이 저장소에 포함되지 않으며 validation script가 자동으로 다운로드하지도 않는다.

## 6. 실험 시작

먼저 위 validation이 통과하는지 확인한 뒤 별도 브랜치를 만든다.

```bash
git checkout -b experiment/<name>
```

초기에는 `CPU selection`, `SMT avoidance`, `migration policy`, `DSQ policy`, `phase-dependent slice`, `load-aware scheduling` 중 하나처럼 한 번에 하나의 scheduling dimension만 변경한다. baseline validation과 semantic phase 입력을 유지하고, 반복 실험 전에는 성능 향상을 주장하지 않는다. 실험 원칙과 기록 항목은 [docs/EXPERIMENT_GUIDE.md](docs/EXPERIMENT_GUIDE.md)를 참고한다.
