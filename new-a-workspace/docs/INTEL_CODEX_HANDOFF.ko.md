# Intel 실험 오류 조사용 Codex 프롬프트

이 문서는 과거 B0/A 비교의 보존 기록입니다. 현재 배포본의 실행 명령, 폴더 구조와 결과 위치는 공용 실행 안내에서 확인하세요. [현재 Intel·AMD 실험](../../README.md#intelamd-cpu-실험) · [과거 전체 원본](https://github.com/codinghuman0/llama-scheduler/tree/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace)


아래 내용을 팀원 장비의 Codex에 붙여 넣으세요. 마지막에 실제 경로와 오류를 덧붙이세요.

---

우리는 `https://github.com/codinghuman0/llama-scheduler`의 `new-a-workspace/`를 Intel i5-1240P / Ubuntu에서 검증하고 있다. 현재 작업은 Intel 이식성·실험 오류의 원인 조사와 최소 수정이다. 과거 장기 연구 goal을 새로 무한 실행하지 말고, 먼저 저장소와 실제 환경/실패 로그를 읽고 재현 가능한 진단을 수행하라. 사용자에게 이미 받은 권한 범위에서 일반 계정 build·test를 진행하라.

## 먼저 읽을 문서

1. 저장소 루트 `AGENTS.md`, 해당 경로에 적용되는 추가 `AGENTS.md`.
2. `new-a-workspace/docs/INTEL_EXPERIMENT.ko.md`: 현재 Intel 실행의 기준. 과거 AMD 명령보다 우선한다.
3. `new-a-workspace/docs/INTEL_COMPATIBILITY_CHECK.ko.md`: 실제로 한 검증과 하지 않은 검증.
4. `new-a-workspace/experiments/final-team-integration-audit-v1/integration-summary.ko.md`, `runtime-integration-map.md`, `source-lineage.json`, `missing-evidence.md`.
5. `new-a-workspace/experiments/r-pool-validation-v1/`와 `a-component-scheduler-replication-v1/`의 `GOAL_STATE.md`, protocol/cases 및 결과 요약. Markdown 이름은 `rg --files`로 확인하라.
6. `new-a-workspace/GITHUB_BACKUP.md`: Git에서 제외한 파일. 최상위 `GOAL_STATE.md`, `README.md`, `run.sh`에는 과거 pre-R/AMD 설명이 남아 있으므로 현재 최종 A로 오해하지 마라.

## 저장소 구조

```text
llama-scheduler/                  # 기존 Git 저장소와 main 이력 유지
  AGENTS.md
  src/, include/, scripts/, tests/, docs/  # 기존 neutral scheduler 프로젝트
  new-a-workspace/
    scripts/intel_experiment.sh   # Intel entrypoint; sudo 없음
    tools/intel_experiment.py     # topology, pinned build, smoke/pilot, raw evidence
    tools/intel_policy_evidence.py # raw pressure/decision 재계산
    tools/test_intel_experiment.py
    docs/INTEL_*.ko.md
    src/llama/                   # vendored merged source; pre-R Q4 header 포함
    scheduler/                   # 보관 scheduler source; Intel loader로 가정 금지
    experiments/                # 기존 증빙, fixture, overlay, 코드와 보고서
      r-pool-validation-v1/candidates/R/overlay/
      a-component-scheduler-replication-v1/
      final-team-integration-audit-v1/
    models/, runtime/, archive/  # 로컬 보존물; Git에는 없음
    state/intel/                # 새 빌드/결과; Git에는 없음
      builds/<hash>/
      <UTC>-smoke|pilot-<PID>/
```

## 현재 코드/비교군

- B0는 `ggml-org/llama.cpp` commit `7a2db1a0cf38e5f4eb278a58c3903d295258d0ea`이다. 최신 upstream이나 편의상 다른 runtime으로 바꾸지 마라.
- 최종 채택 A의 소스 recipe는 `src/llama` 복사본 + 보존 R의 `newa-q4-policy.h`다. R header SHA256는 `014ec3787142838295cb9e8193453ea504cf7a27f18c14a0fa6b8799fcd93029`다. 단순 `src/llama` build는 pre-R이므로 A가 아니다.
- R은 semantic Prefill에서 custom Q4를 쓰지 않고 reference body를 사용한다. 기존 exact Q4 Decode/Mixed와 Q6 최적화는 유지한다. donor persistent pool은 미채택이며 `GGML_NEWA_POOL=off`다.
- `A_L`: 새 A + `NEWA_DECODE_RESOURCE=pressure` + 기본 Linux. `F6_L`: 같은 바이너리 + `fixed6`. fixed6는 eligible multi-request Decode만의 ablation이며 모든 phase/연산 최적화를 끄는 것이 아니다. B0_L도 동일 모델·6CPU envelope·출력량·공통 AVX2 빌드를 사용한다.
- 새 빌드는 보관 AMD 바이너리와 바이트가 다를 수 있다. source/overlay/flags/compiler/DSO 해시로 식별하며 예전 AMD 성능 수치를 Intel 성능으로 가져오지 마라. B1은 이 짧은 세 arm Intel pilot에 포함하지 않는다.
- B0/A 공통으로 고정 UI 자산 네 파일을 사용한다. 최초 build에서 `ui.h`가 빠지면 `frozen-ui.cpp`가 컴파일되지 않는 문제가 있었으며 현재 recipe는 alias header까지 포함한다. UI는 실행 시 꺼져 있다.
- E 정책은 허용 CPU 6개, threads=5/threads-batch=6, 안전한 epoch/8 distinct 요청 provenance와 1초 이상의 Prefill sample을 전제로 한다. Intel에서 sample이 짧거나 조건이 안 맞으면 6으로 fallback하는 것이 정상이다. fallback을 효과 입증으로 표현하지 마라.
- Intel i5-1240P는 4P+8E/16 threads다. 스크립트는 실제 cpuset/SMT topology에서 6 physical cores를 선택하고 controller는 가능한 별도 코어로 둔다. P/E는 SMT 기반 추정이다. CPU 번호/온도 경로를 AMD 값으로 고정하지 마라. 전체 16 threads 최적화라고 주장하지 마라.
- model SHA256는 `f3bdf9cf31dee4b57ae4e455a1cb0d01b5c2c1b50d72d3112141c195506c2840`다. 가중치·양자화·모델 변경, GPU, speculative decoding, 답변 암기, 요청 간 cache 재사용은 금지한다.

## 먼저 실행할 비권한 진단

```bash
git status --short --branch
git rev-parse HEAD
cd new-a-workspace
bash scripts/intel_experiment.sh check
python3 -B tools/test_intel_experiment.py
# 실제 모델 위치를 지정한 다음 필요할 때만 build/smoke
bash scripts/intel_experiment.sh build --jobs 2
bash scripts/intel_experiment.sh smoke --model /actual/path/model.gguf
```

오류를 재현하기 전에 최근 `state/intel/*/protocol.json`, `host.json`, `failure.json`, `progress.json`, visit별 `server.log`, `cleanup.json`, `samples.json`, `runtime.json`, `policy-recomputed.json`과 build의 configure/build 로그를 읽어라. 아직 안 한 단계를 했다고 보고하지 마라. B0/A output mismatch와 A/F6 신규 정책 mismatch를 분리해 기록하라. 실패를 삭제하거나 불리한 block만 재시도하지 마라.

build 실패 시 commit/source/header/hash, `compile_commands.json`, GCC/CMake/OpenMP, AVX2/FMA/F16C CPU flags, 디스크/RAM을 확인하라. `GGML_NATIVE=ON`으로 손쉽게 바꾸어 두 arm의 컴파일 조건을 다르게 만들지 마라. 원본 source·golden evidence·보관 runtime을 수정하지 말고 Intel staging recipe/새 diff에서 최소 수정하라. 변경 후 입력 해시가 바뀌는지 확인하라. 소스/API를 바꾸었다면 코드뿐 아니라 고정 protocol 및 correctness 재검증 필요성을 설명하라.

timeout/기동 실패 시 서버 로그, 실제 DSO, /health, 포트 충돌, 메모리, worker affinity를 확인하라. 스크립트는 자신의 process group만 정리한다. 관련 없는 프로세스를 죽이지 마라. 출력 cache_n은 반드시 0이어야 하며 모든 요청은 지정된 실제 토큰 수를 완료해야 한다. 무거운 profiling은 throughput 측정과 분리하라.

`cpu25`는 1코어의 25% CPU 시간이며 실제 소비량과 affinity로 검증한다. 후보에서 외부 부하가 덜 실행되었다면 공정한 성능 개선으로 인정하지 마라. measured pressure epoch와 실제 OpenMP team을 확인하라. 동일 선택만 했다면 phase 독립 효과는 입증되지 않았다. 4-block pilot은 두 독립 confirmation이 아니다.

## 커널 스케줄러 경계

Intel 스크립트는 커널 scheduler를 로드하지 않는다. A_S/C는 Intel NOT_RUN이다. Ubuntu에 sched_ext가 없더라도 기본 Linux의 A_L/F6_L/B0_L 실험은 가능하다. `scheduler/include/vmlinux.h`와 기존 loader는 원래 AMD 호스트 커널의 증빙이다. 현재 Intel kernel/BTF와 호환된다고 가정하지 마라.

루트 AGENTS의 partial switching/selected-child/수동 kernel-load checkpoint를 유지하라. sudoers·비밀번호 저장·권한 우회·커널 설치·boot/systemd 변경·전역 스케줄러 전환을 하지 마라. 실제 BPF 검증은 별도 승인된 명령/새 프로토콜이 필요하다. sudo 문제가 아니라 kernel API/BTF 및 대상 worker 적용 증거도 확인해야 한다.

## 종료 시 보고

최소 수정, 재현 명령, 실제 PASS/FAIL/NOT_RUN, 남은 blocker, 원시 결과 경로를 한국어로 정리하라. Intel 실행 성공을 Intel 성능 향상이나 kernel scheduler의 성공으로 부풀리지 마라. 새 측정은 실패까지 보존하고 기존 증빙은 바꾸지 마라. push는 별도 사용자 지시가 있을 때 수행하라.

현재 repo 경로: [여기에 입력]
실제 모델 경로: [여기에 입력]
실행 명령: [여기에 입력]
최근 결과/build 디렉터리: [여기에 입력]
오류 전문 또는 현상: [여기에 입력]
