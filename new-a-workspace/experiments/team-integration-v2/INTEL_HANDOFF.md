# Intel i5-1240P / Ubuntu 실행 안내

GitHub 저장소의 `integration-v2` 브랜치에서 실행합니다. 원본 모델은 `$HOME/projects/model.gguf`를 사용합니다. 이번 실기는 AMD에서 진행했고 Intel 실기 확인은 `INTEL_NATIVE_PENDING`입니다.

Ubuntu 일반 계정에서 GCC/G++, CMake, Make, Python 3.10+, Git, util-linux와 OpenSSL 개발 패키지가 필요합니다. Intel 하드웨어별 설정에는 CPU별 CPUID와 sysfs topology를 함께 사용합니다. 현재 허용 CPU의 P/E, SMT, cpuset과 보이는 cgroup 제한을 기록합니다. 전원이나 BIOS 설정이 달라지면 동일한 i5 모델이어도 결과가 달라질 수 있습니다.

## 기존 클론 업데이트

`~/projects/llama-scheduler`에 `main`을 클론해 둔 Intel PC에서는 기존 디렉터리에서 `integration-v2`를 가져옵니다. `main`만 가져온 클론에도 적용됩니다. 브랜치 전환에서 충돌하는 로컬 파일이 있거나 기존 `integration-v2`의 이력이 갈라졌다면 Git이 해당 단계에서 중단합니다.

```bash
(
  set -euo pipefail
  cd "$HOME/projects/llama-scheduler"
  git fetch --no-tags origin refs/heads/integration-v2
  if git show-ref --verify --quiet refs/heads/integration-v2; then
    git switch --no-overwrite-ignore integration-v2
    git merge --ff-only --no-overwrite-ignore FETCH_HEAD
  else
    git switch --no-overwrite-ignore -c integration-v2 FETCH_HEAD
  fi
)
```

처음 설치하는 PC에서는 `~/projects`에서 `git clone --branch integration-v2 --single-branch https://github.com/codinghuman0/llama-scheduler.git`을 사용합니다. 두 경우 모두 `$HOME/projects/model.gguf`를 그대로 읽습니다. 실행 시 해당 PC에서 새 바이너리를 빌드하고 `new-a-workspace/state/integration-v2/`에 저장합니다.

## 같은 소스에서 재빌드

```bash
cd "$HOME/projects/llama-scheduler/new-a-workspace"
bash scripts/intel-integration-v2-smoke.sh "$HOME/projects/model.gguf" intel-validation-01
```

스크립트는 build 입력과 doctor 결과 ZIP 하나, fixture별 실행 결과 ZIP 세 개와 SHA256 sidecar를 만듭니다. 직접 단계별로 실행할 경우 아래 명령을 사용합니다.

`smoke`와 `m4` 실행 스크립트는 기본 Linux 스케줄러용 `--relaxed-host-checks`를 전달합니다. 빌드·`doctor`·추론 실행에서 CPU 온도 센서를 읽지 않습니다. 새 빌드에만 저장소 파일시스템의 여유 공간 **128 MiB 초과**를 요구합니다. `doctor`와 추론에는 고정 여유 공간 기준이 없습니다. 로그와 결과 ZIP을 저장할 실제 공간은 필요합니다.

```bash
set -euo pipefail
cd "$HOME/projects/llama-scheduler/new-a-workspace"
model="$HOME/projects/model.gguf"
build_dir=state/integration-v2/builds/intel-openmp
out=state/integration-v2/intel-smoke-01
test -f "$model"

bash scripts/intel_experiment.sh test
bash scripts/intel_experiment.sh build --relaxed-host-checks --build-dir "$build_dir" --jobs 2
bash scripts/intel_experiment.sh doctor --relaxed-host-checks --build-dir "$build_dir" --resources intel-fixed6 --profile integrated-runtime-research
for fixture in heldout-1 heldout-2 single-short; do
  result="$out-$fixture"
  lifecycle=()
  if [[ "$fixture" == single-short ]]; then lifecycle=(--lifecycle); fi
  bash scripts/intel_experiment.sh run --relaxed-host-checks --build-dir "$build_dir" --model "$model" --output "$result" \
    --resources intel-fixed6 --profile integrated-runtime-research --state-log --worker-log \
    "${lifecycle[@]}" --sleep-idle 2 --fixtures "$fixture"
  bash scripts/intel_experiment.sh collect --result "$result" --output "$result.zip"
done
```

`intel-fixed6`은 6개 물리 코어에 동일한 CPU 범위를 사용하고 generation 5/batch 6으로 실행합니다. 이 프로파일은 legacy E의 적격 multi-request Decode에서 6 workers를 고정합니다. `intel-4-8`은 실제 P 4개와 사용 가능한 E 4개 이상을 확인한 뒤 P 4개와 E 4개의 범위를 구성합니다. 기본은 phase-fixed이며, 고정 범위 안에서 4/8 worker를 선택하는 것과 P만 사용하도록 강제하는 것은 별도입니다. `doctor`에서 선택된 CPU와 worker 수를 확인하세요.

일반화한 pressure는 `--policy adaptive --pressure-threshold 0.125 --pressure-cohort 8 --min-prefill-ms 1000`처럼 조건을 명시해 별도 실험할 수 있습니다. 이는 성능 추천값이 아닙니다. 적격 Prefill과 이어지는 Decode를 찾지 못한 이유는 서버의 epoch 기록에서 확인합니다.

native backend가 필요하면 새 디렉터리에 `build --backend native --markers state-only`를 사용합니다. 여기서 native는 pthread backend이며 ISA는 동일한 AVX2 recipe입니다. 역할별 CPU mask, polling과 `SCHED_BATCH`를 시험하려면 native 역할별 pool과 `--policy phase-fixed`를 선택하고 `run --help`에서 `--generation-cpus`, `--batch-cpus`, `--generation-poll`, `--batch-poll`, `--generation-priority`, `--batch-priority`를 확인합니다. OS 스레드 정책과 affinity는 `runtime.json`에서 확인할 수 있습니다. Intel 6/6 head64 진단은 실제 타입과 범위를 확인한 뒤 정확히 6개의 물리 코어로 리소스를 제한해야 합니다. Intel의 효과와 정확성은 실측이 남아 있습니다.

여러 fixture를 연달아 같은 서버에 보내면 이전 요청의 슬롯 이력에 따라 배치 순서가 달라질 수 있습니다. AMD에서 원본 B0도 `heldout-1` 다음의 `heldout-2`에서 warmup과 sleep 이후의 생성 토큰 차이를 보였습니다. 위 스크립트는 fixture마다 새 서버를 시작합니다. 같은 서버의 순서 영향은 별도 실험으로 결과를 남깁니다.

## Serving과 결과 공유

멀티유저 혼합 부하에서 `cap128`과 `head64`를 비교하려면 다음을 실행합니다.

```bash
bash scripts/intel-integration-v2-smoke.sh "$HOME/projects/model.gguf" intel-m4-01 m4
```

`m4`는 native AVX2 소스를 따로 빌드합니다. `doctor`가 Intel에서 확인한 서로 다른 물리 코어 6개를 두 실행에 동일하게 사용하며 Generation/Batch를 모두 6 workers로 맞춥니다. Decode 요청 4개가 생성하는 동안 6,144토큰 Prefill 요청 하나를 추가합니다. `state/integration-v2/` 아래에 각 정책의 원시 SSE·요약, 빌드 정체 ZIP과 비교 결과 ZIP이 생성됩니다. 비교는 전용 커널 진입 횟수와 전체 생성 토큰 일치를 검사합니다. 실행이 중간에 멈추면 남아 있는 해당 실행 폴더의 `failure.json`과 `server.log`를 확인합니다.

OpenMP에서 일반 Prefill·Decode·Mixed 부하를 비교하려면 위 smoke 빌드로 다음을 실행합니다.

```bash
bash scripts/intel_experiment.sh serve-bench --relaxed-host-checks --build-dir "$build_dir" --model "$model" \
  --resources intel-fixed6 --compare-research --workloads pp d1 d2 d4 m1 m3 \
  --tokens 32 --repetitions 1 --output state/integration-v2/intel-serving-01
```

원래 8-prompt atomic fixture는 `run`입니다. `serve-bench`는 별도 HTTP SSE client로 측정하며 `m1`, `m3`은 진행 중인 Decode에 긴 Prefill을 넣습니다. 실제 overlay와 지연시간은 `trials.json`, 각 trial의 `measured/result.json`, 원시 SSE에 기록됩니다. 잘못된 overlap이나 실패 시도는 해당 run을 실패로 남깁니다. 팀원에게는 결과 ZIP, SHA256 sidecar, 사용한 빌드의 `inputs.json`과 `manifest.json`을 전달하세요. 해당 파일의 로컬 경로와 머신 정보를 검토해 공유하면 됩니다.

실패하면 처음에는 `doctor`와 build/configure 로그, 결과의 `failure.json`, `server.log`를 확인합니다. 옛 바이너리나 잘못된 DSO를 지정하면 새 launcher가 거부합니다. 수정 전 실패 폴더를 보존하고 새 output 이름으로 다시 실행하세요. 같은 build의 source seal이 바뀌면 새 build 경로를 지정합니다.

동결 재현이 필요하면 이 브랜치에서 `scripts/historical-frozen.sh /absolute/path/to/preserved/new-a-workspace run ...`으로 원래 workspace에 위임합니다. GitHub main과 로컬 보존 바이너리를 연결하는 이전 지침은 1차 문서의 범위입니다.

## 선택된 child의 커널 스케줄러

### Prefill P-core 옵션을 확인하는 짧은 실험

`new-a-workspace`에서 아래 명령을 실행합니다. 프로젝트 상위의 `model.gguf`를 자동으로 찾으며 다른 위치는 두 번째 인자로 지정할 수 있습니다. Linux x86-64, AVX2/FMA/F16C/SSE4.2, Python 3.10 이상이 필요합니다. 커널 실험에는 호스트의 sched_ext와 BTF, clang BPF 백엔드, bpftool, libbpf·libelf·zlib 개발 파일도 필요합니다.

```bash
bash scripts/prefill-pcore-smoke.sh linux
bash scripts/prefill-pcore-smoke.sh prepare
bash scripts/prefill-pcore-smoke.sh scx
```

`linux`는 기본 Linux 스케줄러에서 실제 모델로 단일 요청과 8개 동시 요청을 각각 워밍업한 뒤 한 번 다시 실행합니다. 각 요청은 4개 토큰을 생성합니다. `prepare`는 이 호스트의 BTF로 스케줄러를 빌드하고 두 옵션의 CPU 목록과 체크포인트를 확인합니다. 이 단계에서 만든 체크포인트는 소유 프로세스가 종료되면 만료됩니다.

`scx`는 새 체크포인트를 만들고 일반 계정 터미널에서 기다립니다. 다른 Bash 터미널에서 `sudo -v` 후 화면에 출력된 `bash …/load.sh`를 실행합니다. `neutral`의 요청과 detach가 끝나면 출력되는 `prefill-pcore`의 명령도 같은 방식으로 실행합니다. 승인 대기는 옵션당 10분이며 loader에는 540초 제한이 있습니다. 원래 셸과 컨트롤러는 Linux 정책을 사용합니다. 두 실행의 정책 7 worker, 고정 mask, PID 등록, v2 수신과 idle, loader 종료, detach를 검사합니다. 온도 센서는 이 스크립트의 세 모드에서 읽지 않습니다. 새 빌드에는 128 MiB의 여유 공간 하한이 적용됩니다. 런타임이나 커널이 바뀌어 기존 빌드 검증이 실패하면 `NEWA_BUILD_DIR`, `NEWA_SCX_BUILD`에 새 빌드 경로를 지정할 수 있습니다.

Intel i5-1240P에서 `auto`는 사용 가능한 물리 코어가 충분하면 대표 CPU 여섯 개를 선택합니다. CPUID로 확인한 P-core 대표만 선호 목록에 들어갑니다. AMD Ryzen 5 5500U에서는 같은 옵션의 선호 목록이 비고 두 옵션 모두 기본 SCX CPU 선택 함수를 사용합니다. 각 옵션은 shared weighted-vtime 큐와 동일한 자원 상한을 사용합니다. 정책 판정은 등록된 서버의 유효한 active Prefill wakeup에서만 일어납니다. 각 wakeup에서 최대 32개 후보의 task mask, online, idle 여부를 확인합니다. 원 설계의 선택 규칙을 기존 state-v2 수신기와 selected-child loader에 이식했습니다. [Policy F 소스](https://github.com/sueon00/PA-IPP-LLM-Scheduler/blob/e4c74dc52f3154349b9c01d74d7658e957677caf/tools/sched_ext/llama_scx.bpf.c#L59)

출력 경로 아래 `pair-metrics.json`에는 양쪽의 실제 생성 토큰 수, cohort wall time·tokens/s, CPU seconds, 요청별 Prefill·Decode 시간이 들어갑니다. 두 방문의 모델, 런타임, 설정, 요청 순서와 출력 토큰이 일치해야 생성됩니다. 요청별 시간에는 겹치는 구간이 있습니다. 전체 처리율의 분모는 cohort wall time입니다.

각 `*-checkpoint/scheduler-stats.json`의 `prefill_pcore.attempts`와 `hits` 순서는 Unknown/idle, Prefill, Decode, Mixed입니다. hit는 허용된 idle P-core를 선택한 횟수입니다. FULL의 `running_starts_by_cpu`는 실제 CPU에서 등록된 작업이 실행을 시작한 순간의 phase를 셉니다. phase의 범위는 등록된 서버 프로세스 전체여서 같은 시점에 깨어나는 HTTP 스레드도 포함될 수 있습니다. Lite는 실행 시작의 CPU별 상세 항목을 `null`로 저장합니다. `NO_ELIGIBLE_WAKEUP_OBSERVED`와 `ATTEMPTED_NO_IDLE_HIT`는 모두 가능한 결과입니다. 비교 실행을 한 쌍만 수행하는 이 스크립트는 기능 확인용입니다.

### 개별 정책과 FULL/Lite 수동 실행

이 단계는 실제 Intel/AMD kernel BTF와 검토된 권한으로만 진행합니다. 일반 계정은 먼저 모델 조합을 검증하고 아래에서 빌드와 준비만 수행합니다. 권한을 확보한 운영자가 출력된 단일 loader 명령을 검토한 뒤 수동 실행합니다.

```bash
bash scripts/intel_experiment.sh build-scheduler --output state/integration-v2/intel-scx-build
bash scripts/intel_experiment.sh prepare-scx --build-dir "$build_dir" \
  --scheduler-build state/integration-v2/intel-scx-build --variant full --scheduler-policy observe --owner-pid "$$" \
  --resources intel-fixed6 --profile integrated-runtime-research \
  --output state/integration-v2/intel-scx-full-01
```

준비 명령을 실행한 셸은 유지합니다. 출력된 root loader가 선택 child를 기다리는 상태가 된 뒤 일반 계정에서 다음을 실행합니다.

```bash
bash scripts/intel_experiment.sh run --build-dir "$build_dir" --model "$model" \
  --resources intel-fixed6 --profile integrated-runtime-research --state-log \
  --scx-checkpoint state/integration-v2/intel-scx-full-01 \
  --output state/integration-v2/intel-scx-full-model-01
```

확인할 증거는 PID별 등록 ACK, server/worker의 정책 7과 고정 mask, 외부 셸의 Linux 정책, 실제 v2 sequence와 idle, loader 로그, 실패 카운터, 최종 detach입니다. `lite`는 새 output dir를 쓰는 별도 실행입니다. 같은 enqueue 정책의 FULL과 Lite는 선택적인 `runtime_ns` 집계에서만 달라집니다.

`observe`로 현재 커널의 수신·격리·종료를 검증한 뒤 `--scheduler-policy decode-handoff`와 새 결과 경로로 수동 checkpoint를 만들 수 있습니다. 이 정책은 유효한 active Decode에서만 선택 대상의 허용 mask 및 online 조건에 맞는 첫 tier의 idle CPU로 enqueue할 수 있습니다. `scheduler-stats.json`의 실제 Decode 이동 횟수가 0이면 이동 효과는 관측되지 않은 것입니다. 두 정책 모두 현재 통합본의 실기 검증은 `KERNEL_NOT_RUN`입니다.

이전 CPU 선호는 `--scheduler-policy locality-decode`로 선택합니다. 이전 CPU가 첫 tier에 속하고 허용된 online idle CPU일 때만 기존 tier 순서보다 먼저 선택합니다. `locality-active`는 같은 조건을 Prefill·Decode·Mixed에 적용하는 대조 구성입니다. `scheduler-stats.json`의 `locality.attempts`와 `locality.hits`에 phase별 결과를 남깁니다. 각각 별도 수동 checkpoint로 실행하며 현재 `KERNEL_NOT_RUN`입니다.
