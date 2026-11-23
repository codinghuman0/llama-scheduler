# B0 / NEW_A B1 deterministic 출력 분기 진단

이 디렉터리는 기존 `phase-scheduling-study-v1`과 `phase-scheduler-review-v1`을 보존한 별도 진단이다. 기존 모델, runtime, E, 원시 성능 결과를 변경하지 않았다. 결론과 한계는 `diagnosis-summary.md`, 품질 형식 진단은 `quality-report.md`에 있다.

## 읽는 순서

1. `diagnosis-summary.md`: 최초 token 분기와 Q4 Prefill 경로 격리.
2. `protocol-and-identity.json`, `identity/`: 동결 B0/B1 및 실제 실행 설정.
3. `evidence/compare-*.json`, `runs/*/events.jsonl`: 같은 전체 요청 history/ubatch/profile/RNG 대조 및 logits.
4. `quality-v2/protocol.json`, `quality-report.md`: 별도 20응답의 사전 기준과 결과. 중단한 BOS 처리 오류 시도는 `quality/`에 남긴다.
5. `ledger.jsonl`, `evidence/preservation-{before,after}.json`, `next-step.md`.

## 일반 계정 재현

sudo를 사용하지 않는다. 이 단계는 Linux correctness 진단이며 BPF를 로드하지 않는다. 명령의 출력 디렉터리는 존재하지 않는 새 경로여야 한다.

```bash
cd /home/codinghuman/projects/new-a-performance/output-divergence-diagnosis-v1
bash reproduce.sh verify
bash reproduce.sh analyze /tmp/newa-diagnosis-analysis-fresh
bash reproduce.sh replay-single /tmp/newa-diagnosis-single-fresh
# 원래 8개 요청 형상: B0 free / B1 all-request B0-prefix replay / B1 Q4off replay
bash reproduce.sh replay-cohort /tmp/newa-diagnosis-cohort-fresh
# 선택: template/EOS/length/temperature 품질 진단 20응답
bash reproduce.sh replay-quality /tmp/newa-diagnosis-quality-fresh
```

`replay-single`은 실제 한 요청으로 줄인 h1-d 사례를 B0, B1, B1 Q4off에서 실행한다. frozen 8-request 출력과 singleton 출력이 다를 수 있으며, 이를 오류로 판정하지 않는다. B0/B1의 singleton끼리 비교한다. B1의 read-only operator overlay는 실제 Prefill 입력의 32×8 출력만 추가 계산하고 원래 결과는 바꾸지 않는다. 속도 측정에 사용하지 않는다.

`replay-cohort`는 모든 8개 요청의 B0 token history를 동시에 강제한다. 강제 반환된 token이 B0와 같다는 사실은 정확성 증거가 아니다. 원래 sampler가 선택한 token과 강제 반환 token을 따로 기록하고, 같은 논리 history에서 강제 이전 logits와 sampler를 비교한다.

재현에는 기존 절대 경로의 동결 B0/B1 runtime, 소스 헤더, GCC/G++ 및 시스템 libraries, 모델이 필요하다. 이 ZIP에는 모델·가중치·실행 binary·전체 빌드가 없다. `protocol-and-identity.json`, `diagnostic/build-identity.json`, `diagnostic/operator-build.json`에 의존성과 SHA256이 있다. 다른 시스템에서 임의 빌드한 binary를 동결 B0/B1로 대체하면 같은 실험이 아니다. 원래 모델 SHA256도 replay 전에 검사한다.

## 안전한 종료와 증거 범위

launcher는 공유 measurement lock을 독점하고, 현재 고정 CPU envelope와 disabled sched_ext 상태를 확인한다. 일반 계정, 디스크 512MiB 이상, MemAvailable 약3GiB 이상, CPU85°C 미만을 요구한다. HTTP180초, readiness90초, 최종 launcher의 owned-server watchdog480초(quality600초)를 사용한다. Ctrl-C/SIGTERM은 자신이 만든 process group만 정리한다. `process.json`과 `cleanup.json`을 남긴다. 초기 성공 실행은 HTTP/readiness timeout 및 finally cleanup을 사용했으며, 이후 watchdog/신호 처리 보완 시점은 ledger에 기록했다.

강제 종료 후에는 `process.json`의 PID를 재사용 여부와 `/proc/PID/cmdline`로 확인한다. PID 번호만 보고 kill하지 않는다. 관련 없는 server/process를 종료하거나 `pkill llama-server`를 실행하지 않는다. 일반적인 종료는 launcher에 Ctrl-C를 보내고 `cleanup.json`의 PASS를 확인하는 것이다.

초기 infrastructure 실패 두 건과 BOS 처리 오류 품질 시도도 보존했다. 다른 prefix가 된 이후의 free-generation logits는 비교에서 제외한다. `preliminary-comparison-superseded.json`은 그 검사를 강화하기 전 출력으로, causal 결론에 사용하지 않는다.

ZIP에서 같은 logits bytes는 SHA256별 `logit-blobs/`에 한 번 저장하며 `LOGIT_BLOBS.json`이 원래 run 경로를 연결한다. 분석 코드는 이 연결을 직접 읽는다. 원래 로컬 raw 파일은 삭제하지 않았다. `manifest.json`은 ZIP 구성 파일의 SHA256을 검사한다. manifest 자체와 ZIP/sidecar는 자기참조를 피하기 위해 목록에서 제외한다.

저장 공간 정리는 사용자가 지정한 CMake dependency cache 625개로 한정했다. 약9.15MiB를 회수했고 모델·runtime·실험 증빙 등 보호 파일656개의 해시를 재확인했다. 복원용 archive와 기존 감사 ZIP은 보존했다.
