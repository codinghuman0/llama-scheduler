# 교수님 설명용 요약

## 한 문장

공유된 semantic phase·compute-profile 기반에 Prefill 경합 관측을 이용한 Decode worker 선택과 검증된 CPU 연산 경로를 연결했고, historical llama.cpp 재빌드 대비 처리량 향상을 재현했지만 커널 스케줄러 교체의 일관된 추가 이득은 입증하지 못했습니다.

## 60~90초 구두 설명

“이번 연구에서는 CPU로 여러 LLM 요청을 처리할 때 Prefill과 Decode가 요구하는 실행 자원이 다르다는 점을 활용했습니다. 팀원과 공유하던 phase 판별과 compute-profile API를 기반으로, Prefill에서 CPU 경합을 관측하고 이후 Decode의 worker 수를 5개 또는 6개로 선택하도록 연결했습니다. 같은 모델과 CPU 한도에서, 경합 조건에서는 6개를 고정한 경우보다 이 선택 정책이 두 캠페인에서 약 11~12% 빨랐습니다.

기존에 검증한 작은 Decode/Mixed 배치의 Q4·Q6 CPU 연산 경로도 유지했습니다. 다만 Prefill Q4에서 수치 호환성 문제가 있었던 경로는 기준 구현으로 복원했고, 정해 둔 출력과 logits checkpoint에서 일치를 확인했습니다. 전체 Linux 실행 구성은 historical 원본 재빌드 대비 ambient에서 약 15~16%, 0.25 core 경합에서 약 29~32% 빨랐습니다. 이 수치는 구성 전체의 효과이지 개별 커널이나 팀원별 몫은 아닙니다.

커널 스케줄러도 실제 연결해 대상 worker의 SCHED_EXT 적용까지 검증했습니다. 그러나 최종 observe 구성은 phase를 관측할 뿐 phase별 CPU 배치를 바꾸지 않았고, 추가 성능은 일관되지 않았습니다. 별도로 이식한 persistent pool은 실제 모델 검증을 통과했지만 제한 pilot 결과가 엇갈려 채택하지 않았습니다. 따라서 성능 기본 구성은 A_L, 커널 통합 평가 구성은 A_S로 구분해 제출합니다.”

수치는 [캠페인별 표와 CI](performance-attribution.md)에 대응한다. 말하는 속도에 따라 약 60~90초 분량이며 숫자를 나열하기보다 계층과 검증 범위를 설명한다.

## 실제로 무엇을 어떻게 개선했나

| 기존 문제 | 실제 변경 | 작동 위치 | 증거 | 한계 |
|---|---|---|---|---|
| 여러 토큰이라는 이유만으로 batch 자원을 선택하면 semantic Decode와 Prefill을 구별하지 못함 | token-origin phase와 explicit profile 기반을 재사용해 정책 선택을 계산 자원까지 전달 | server batch → `llama_decode_with_options` → `graph_compute` → CPU/OpenMP | 공유 commit a943/5219, final source hash, API ELF, raw team/epoch | API 단독 성능 기여 미분리 |
| 경합에서 6-worker Decode가 항상 최선은 아님 | Prefill CPU counter로 경합 관측, 적격 8-task 후속 Decode를 5/6으로 선택 | `newa-prefill-pressure.h`, server profile 선택 | CPU25 A/F6 +11.33%, +12.13%; 두 CI 양수, 각8/8 faster | fixed6 대비; fixed5·모든 adaptive 정책 대비 우월성 아님 |
| 작은 batched CPU 연산에서 같은 weight 준비가 반복됨 | 기존 exact Q4 준비 공유와 Q6 경로 확장 유지 | CPU DSO/repack, Q4/Q6 eligibility | 별도 R 경로 진단에서 실행 관측, F6/B0 묶음 효과 | 개별 kernel 몫은 NOT_ISOLATED |
| custom Prefill Q4가 출력 분기를 바꿀 수 있음 | semantic Prefill만 reference body로 복원 | R policy header, CPU DSO | 실제 reference body 계수, 8 logits checkpoint byte equality, fixture token equality | 새 속도 최적화가 아닌 호환성 복원; 일반 품질 미검증 |
| runtime phase와 커널 실행 연결 여부 불분명 | scalar uprobe, selected child, FULL 진단과 정리 검증 | observe scheduler/loader | 정책7, loaded object/ELF, phase bit, monitor, moved0 | phase-dependent placement·일관된 추가 gain 없음 |
| pool 연결의 소유·재사용·해제 검증 필요 | donor owner를 P에 선택 이식, padding guard 최소 수정 | P 서버 전용 | steady512 graph attached, 생성6/해제6, cancel/error/sleep-resume | 최종 A에는 미포함, n4 pilot 방향 엇갈림 |

파일/행번호/전체 SHA는 [통합 경로](runtime-integration-map.md)와 [기능별 표](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/integration-matrix.json)에 있다.

## 팀원 저장소와 연결 작업

| 저장소·계층 | 확인 가능한 재사용 | 통합 과정의 연결 작업 | 주장하지 않는 것 |
|---|---|---|---|
| `hsju2021/llama.cpp-fork` | 공통 조상의 semantic phase/profile API, P의 byte-identical pool header | HINT 경량화, CPU setter bridge, E controller 연결; P lifecycle adaptation | 최신 donor의 전 기능 사용, API 또는 개인의 성능 몫 |
| `euichan0418/new-a-llm-scheduler` 계열 | topology/tier, loader, selected-child, phase uprobe, FULL 진단 공통 기반 | 로컬 observe 파생, fixed-affinity 검증·실험 적용 | Linux `scx_simple`의 DSQ/vtime를 팀 고유 발명으로 계산 |
| 로컬 누적 runtime 연구 | Q4/Q6/메모리 관련 overlay, E server, R 호환성 복원 | 정확한 overlay/DSO 조합 동결, 비교군·ablation·재현과 출처 연결 | dirty overlay의 최초 개인 저자를 추정하거나 LOC로 점수 부여 |

Git author는 해당 commit의 저장소 metadata다. 사람의 전체 연구 공헌, 설계 토론, 실험 기여와 동일하지 않다. 일부 overlay의 per-hunk author/commit은 UNKNOWN이며 추정으로 채우지 않았다.

## 최종 역할과 미채택 기능

**A_L:** 최종 연구상 기본 성능 구성. **A_S:** 같은 runtime에 observe/FULL을 연결한 평가 구성. **P:** 모델 검증 후 pilot 보류 후보. A_L 역할 지정은 현재 workspace 기본 `run.sh`를 변경했다는 뜻이 아니다.

donor pool, v2 active/idle, Runtime Lite, Intel4/8/P4+E4, donor serving harness를 최종 활성 성과에 포함하지 않는다. 기존 optional pool도 off이며, native phase barrier는 OpenMP 경로에서 비활성이다. custom Prefill attention off와 일반 Flash Attention on은 다른 설정이다.

## 실험 범위를 함께 말하기

동일 모델·가중치·양자화, GPU0/speculationnone, cache 재사용 없이 서로 다른 8 prompt를 한 atomic 요청 배열로 도착시켰다. 요청당128 generated tokens, cohort당1024 tokens다. CPU envelope는 0,2,4,6,8,10의 여섯 physical core이며 E가 활성 worker만 바꾼다. CPU25는 CPU10의 약0.25 core 부하다. 두 기존 캠페인은 각각 조건당8 paired blocks, cohort당4개다. 여덟 요청을 여덟 독립 반복으로 세지 않는다.

기준은 최신 llama.cpp가 아니라 historical `7a2db1a0…`의 보존 재빌드다. 두 prompt cohort도 이번 감사에서 새로 확보한 unseen 데이터가 아니다. 측정 fixture의 token equality와 제한된 R logits 일치는 확인했지만, 일반 답변 품질·다른 모델·Intel까지의 동등성과 개선은 검증하지 않았다.

이번 감사에서 추가한 것은 계보 추적·ELF/loaded identity 연결·raw 재계산·기여 구분과 이 설명 자료다. 새 알고리즘, 새 runtime, 새 성능 측정은 추가하지 않았다.
