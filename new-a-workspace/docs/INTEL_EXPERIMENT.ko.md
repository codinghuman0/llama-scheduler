# Intel i5-1240P / Ubuntu 실행 안내

이 경로는 **동일한 모델로 B0, 최종 A의 fixed6, 최종 A의 pressure 정책을 Intel에서 새로 빌드하고 비교**한다. 모두 기본 Linux 스케줄러를 사용한다. AMD의 보관 바이너리나 CPU 번호를 재사용하지 않는다. Intel 실측 전에는 Intel 성능 개선을 주장하지 않는다.

## 1. 범위와 준비

Intel의 [i5-1240P 사양](https://www.intel.com/content/www/us/en/products/sku/132221/intel-core-i51240p-processor-12m-cache-up-to-4-40-ghz/specifications.html)은 P 코어 4개, E 코어 8개, 총 16 스레드, AVX2 지원이다. 현재 E 정책의 안전 경계는 **6개 서로 다른 물리 코어에서 논리 CPU 하나씩**, 5/6-worker 선택이다. 16개 전체를 쓰는 최적화가 아니다.

자동 선택은 현재 프로세스에 허용된 cpuset과 `/sys/devices/system/cpu`를 읽는다. SMT 형제 수가 많은 코어부터 고르고 각 코어에서 한 CPU만 선택한다. 일반적인 SMT 활성 i5-1240P에서는 4P+2E가 되지만 **P/E 식별은 SMT 정보에 근거한 추정**이다. BIOS에서 SMT를 껐거나 제한된 cpuset이면 결과를 확인하고 `--cpus`로 6개를 직접 지정한다. 실행 전 `check`가 실제 선택 번호와 controller CPU를 출력한다. AMD의 `0,2,4,6,8,10`을 복사하지 않는다.

Ubuntu의 일반 x86_64 Linux, Python 3.10 이상, GCC/G++, CMake, Make, Git, util-linux(taskset), tar가 필요하다. Python 외부 패키지는 없다. 최소 여유 RAM 2.5 GB, 최초 빌드 시작 시 디스크 1.3 GiB가 필요하며 실제 사용 가능 공간은 넉넉하게 확보한다. CPU 온도 센서가 없거나 90°C 이상이면 중단한다. AC 전원 연결과 일정한 전원 프로필을 권장한다. 실행 중 다른 빌드/추론은 피한다.

필요한 의존성이 없을 때만 팀원이 직접 실행한다. 실험 스크립트는 sudo를 호출하지 않는다.

```bash
sudo -v
sudo apt-get update
sudo apt-get install -y build-essential cmake git python3 pkg-config libssl-dev
```

## 2. Git clone과 모델

```bash
git clone https://github.com/codinghuman0/llama-scheduler.git
cd llama-scheduler/new-a-workspace
bash scripts/intel_experiment.sh check
```

모델 가중치와 실행 바이너리는 Git에서 제외했다. 팀 내에서 원본 `model.gguf`를 별도로 전달받고 절대경로로 지정한다. 모델 다운로드나 변경을 자동으로 수행하지 않는다. 모델이 이미 다른 위치에 있다면 복사할 필요가 없다.

```bash
MODEL_PATH=/absolute/path/to/model.gguf
sha256sum "$MODEL_PATH"
# 반드시 다음과 같아야 함:
# f3bdf9cf31dee4b57ae4e455a1cb0d01b5c2c1b50d72d3112141c195506c2840
```

고정 fixture에는 이 모델의 토큰 ID가 포함된다. 다른 모델을 넣어 같은 실험이라고 부를 수 없다. 각 요청의 원문을 다시 tokenize하여 ID도 확인한다.

## 3. 단계별 실행

```bash
# 별도 staged source에서 원본 B0와 A를 같은 AVX2 설정으로 빌드.
# 최초 B0 소스 획득 때만 GitHub 네트워크 필요.
bash scripts/intel_experiment.sh build --jobs 2

# 단일/8개 distinct 요청, 짧은 출력, ambient/cpu25 기동·출력·정리 확인.
bash scripts/intel_experiment.sh smoke --model "$MODEL_PATH"

# smoke가 통과한 뒤: 128 output tokens, 4 paired blocks/condition의 탐색 실험.
bash scripts/intel_experiment.sh pilot --model "$MODEL_PATH" --blocks 4
```

필요하면 모든 명령에 동일한 `--cpus CPU목록`을 추가한다. 예시는 CPU 번호를 고정하지 않는다. 외부 부하는 선택된 CPU 중 가장 높은 번호 하나에 걸린다. 다른 mask를 쓰면 별도 조건으로 기록한다.

네트워크가 없고 정확한 B0 commit을 포함하는 Git 저장소가 있다면 build에 `--baseline-repo /path/to/llama.cpp-git`을 추가한다. 다른 revision으로 대체하지 않는다. 빌드/로그는 `state/intel/builds/<input-hash>/`, 실행 결과는 `state/intel/<UTC>-smoke|pilot-<PID>/`에 생긴다. 같은 입력의 완료된 빌드는 해시 확인 후 재사용한다. `state/.measurement.lock`으로 중복 빌드/측정을 막는다.

## 4. 비교군과 실제 빌드 내용

| arm | 소스 / runtime | 결정 | kernel scheduler |
|---|---|---|---|
| B0_L | 원본 commit `7a2db1a0cf38e5f4eb278a58c3903d295258d0ea` 재빌드 | 기존 5/6 threads 설정 | 기본 Linux |
| F6_L | A 재빌드 | eligible multi-request Decode만 fixed6; singleton/fallback은 기존 규칙 | 기본 Linux |
| A_L | F6_L과 동일한 A 재빌드 | Prefill CPU pressure를 관측해 eligible Decode에서 5 또는 6 | 기본 Linux |

`src/llama`는 **pre-R Q4 정책**을 포함한다. 스크립트는 staging copy에서만 `experiments/r-pool-validation-v1/candidates/R/overlay/ggml/src/ggml-cpu/newa-q4-policy.h`를 적용한다. 이로써 semantic Prefill은 Q4 reference body를 사용하고 기존 exact Decode/Mixed Q4와 Q6 최적화는 유지한다. 보관 runtime 및 원본 소스를 수정하지 않는다. donor persistent pool은 `off`다.

B0와 A에 동일한 고정 UI 소스 네 파일(`tools/ui/CMakeLists.txt`, `frozen-ui.cpp`, `frozen-ui.h`, `ui.h`)을 적용한다. 이는 오프라인 빌드를 위한 자산 포장으로, `--no-ui`에서 추론 경로를 변경하지 않는다. B0의 연산/스케줄링 소스를 바꾸지는 않는다.

공통 빌드는 Release, OpenMP, `GGML_NATIVE=OFF`, `-march=x86-64 -mtune=generic`, AVX/AVX2/FMA/F16C/SSE4.2 ON, AVX512/AMX/AVX-VNNI/BMI2/GPU/BLAS OFF다. A만 semantic phase bridge를 위해 `LLAMA_SCX_PHASE_HINT=ON`; 무거운 TRACE는 두 arm 모두 OFF다. 서버의 실제 로드 DSO 및 컴파일 명령을 기록한다. **보관된 AMD 바이너리와 동일 바이트라는 뜻은 아니다.**

기존 `build.sh`, `run.sh`, 보관 experiment runner에는 AMD mask/온도/절대경로 및 pre-R 기본값이 남아 있다. Intel에서는 이 문서의 새 entrypoint를 사용한다.

## 5. 판정과 출력 읽기

`smoke`는 두 8-request cohort와 두 singleton을 각 arm에서 warmup+measured로 실행한다. 출력은 요청당 16 tokens다. 기본 설정은 cpu25에서 첫 cohort도 확인한다. `pilot`은 동일한 correctness 단계에서 128 tokens를 검증한 뒤 두 cohort를 번갈아 쓰며 각 조건당 4개의 3-arm paired block을 실행한다. 정/역순을 쌍으로 배치한다. 모델 로딩/1회 warmup은 집계에서 제외하고, 전 요청의 실제 생성 토큰 합을 cohort HTTP 전체 경과시간으로 나눈다. 요청 간 cache_prompt/n_cache_reuse를 끄고 실제 cache_n=0을 확인한다. 요청 내부 정상 KV cache는 유지한다.

- `summary.json`: 완료 상태, 절대 tokens/s, A_L/B0_L, F6_L/B0_L, A_L/F6_L의 paired gain과 block bootstrap 95% interval. pilot은 **PILOT_ONLY_NOT_CONFIRMATION**이다. 반복 수가 작고 전체 연구의 두 독립 confirmation 조건을 충족하지 않는다.
- `correctness.json`: A/F6의 신규 정책 equality와 A/B0 equality를 별도로 기록한다. 어느 쪽이든 mismatch이면 후속 측정을 중단하고 결과를 보존한다.
- `protocol.json`: 시작 전 고정된 fixture/build/model 해시, 순서, 조건, 토큰 수, 제외 규칙. 실패한 block을 버리거나 자동 재시도하지 않는다.
- visit별 `samples.json`, `*-responses.json`, `runtime.json`: HTTP raw 응답, 토큰, CPU 시간, 실제 DSO와 worker affinity/policy.
- `policy-recomputed.json`: raw `/proc` 카운터에서 E의 선택을 다시 계산. `result.json`의 `measured_multi_decode_5_6`은 measured 구간의 eligible multi-request 선택 횟수다. OpenMP team 5/6 관측도 검증한다.
- `load.jsonl`, `samples.json`: cpu25는 **코어 한 개의 25% CPU 시간**, 시스템 전체 25%가 아니다. 실제 부하가 0.22~0.28 core 밖이거나 paired arm 간 소비 차이가 0.025 core를 넘으면 무효다.
- `failure.json`, `cleanup.json`, `server.log`: 실패 이유와 본인 프로세스 정리 증거. Ctrl-C/SIGTERM/timeout은 소유 서버/부하만 정리한다. 무관한 프로세스는 종료하지 않는다.

Intel에서 Prefill이 1초 미만이면 기존 정책의 sample이 usable하지 않을 수 있다. phase/epoch 안전 조건이 맞지 않거나 pressure가 낮으면 fixed6로 fallback한다. 이때 실행 성공과 phase 정책 효과를 구분한다. A가 실제로 5를 선택하지 않았으면 phase 개선을 입증한 것이 아니다. P/E 혼합의 불균형이나 Intel의 더 짧은 Prefill 때문에 AMD의 이득이 재현되지 않을 수 있다.

**커널 스케줄러 A_S/C는 이 스크립트에서 NOT_RUN이다.** 일반 Ubuntu에 sched_ext가 없어도 runtime 비교는 가능하다. 보관 BTF/loader는 원래 AMD 호스트 커널용이다. Intel에서 실제 kernel/BTF를 조사하고 partial selected-child 경계와 verifier를 검증하기 전에는 로드하지 않는다. sudo 인증 여부만으로 이식성이 확인되는 것은 아니다. 커널 교체, 시스템 설정 변경, 전역 스케줄러 전환은 이 실험에 포함하지 않는다.

## 6. 오류가 나면

먼저 [Codex 전달용 프롬프트](INTEL_CODEX_HANDOFF.ko.md)를 사용한다. 가장 최근 결과 폴더와 `failure.json`/로그를 보존한다. incomplete build는 로그를 확인한 뒤 해당 `state/intel/builds/<hash>`만 이름을 바꾸어 보존하고 다시 build한다. 다른 baseline으로 바꾸거나 golden evidence를 고치지 않는다. 자동으로 긴 재시도/confirmation을 시작하지 않는다.

팀에 결과를 전달할 때 해당 실행 폴더와 사용한 build의 `inputs.json`, `complete.json`, configure/build 로그, `*-source-sha256.json`, `*-configure-command.json`, `build-*/compile_commands.json`을 포함한다. 모델이나 build 바이너리를 Git에 올릴 필요는 없다. 원시 결과에는 로컬 경로/CPU/OS 정보가 들어가므로 공개 업로드 전에 내용을 검토한다.
