# 확인되지 않은 사항과 필요한 증거

상태는 **PARTIAL_PROVENANCE**다. 핵심 A/B0/스케줄러의 identity를 잃어 BLOCKED인 상황은 아니다. 미확인 칸을 PASS로 정규화하지 않았다.

| 미확인 사항 | 필요한 정확한 자료/비교 | 현재 할 수 있는 주장 |
|---|---|---|
| dirty E/Q4/Q6/CPU bridge overlay의 최초 개인·commit | `runtime-prefill-pressure-v2`와 `phase-batch-q4-exact-v1`, `q6-batch`, phase bridge의 원래 branch commit 및 parent→patch 계보 | source/build hash와 실행은 연결되지만 개인별 최초 작성자는 UNKNOWN |
| 일부 scheduler common hunk의 최초 저자/차용 방향 | pinned public a9be078…와 로컬 import 이전 full parent history, 원래 Linux/scx_simple 대비 구분 patch | 공유 코드와 observe 파생을 확인; pin 최신판을 이번 신규 발명으로 세지 않음 |
| phase header의 최초 추가 commit | `tools/server/server-phase.h`를 포함한 해당 로컬 commit path history | archive base59와 final byte identity 및 classifier 내용은 확인. 선택 Git path walk가 그 header의 전체 도입 이력을 포함하지 않음 |
| 단일 clean revision 전체 재빌드 | 모든 overlay를 묶은 별도 commit/manifest, 동일 toolchain의 clean build와 loaded DSO/정확성 재검증 | 보존 source/명령/ELF/loaded chain까지 확인. 이번 감사는 build 금지 |
| 실제 huge-page 사용량·개별 효과 | 해당 run의 smaps residency와 동일 조건 advice on/off 비교 | madvise 요청과 로그는 실제 huge-page residency를 뜻하지 않음 |
| 모든 timing graph/physical ubatch에서의 선택 비율 | 비용 통제된 graph별 계측과 정의, 동일 오버헤드 검증 | 현재 E 분모는 select 호출; 전체 graph 분모는 null |
| phase event 횟수·measured-only scheduler counter | 구간 전후 동일 counter snapshot 또는 transition event trace | 현재 phase_seen은 bitmap; tier/attempt는 whole visit |
| Q4/Q6/API/HINT/메모리의 각각 성능 몫 | 해당 기능만 바꾸고 산술·phase·자원을 통제한 paired comparison | 개별 NOT_ISOLATED; F6/B0 묶음 효과만 있음 |
| semantic phase label 자체 가치 | 같은 정보/비용을 가진 비semantic controller와 비교 | CPU25 E/fixed6 선택 효과만 재현 |
| 모든 정적 정책보다 우월성 | fixed5 및 다른 정적 worker profile의 동등 조건 확인 | fixed6 대비 효과 |
| E×scheduler 상승효과 | fixed6_S까지 포함한 factorial 비교 | 지금 fixed6_S 없음; 전체 효과를 더해 interaction 추정 불가 |
| Lite의 순수 이득·FULL 비용 | 같은 scheduler 정책에서 계측 모드만 다른 비교 | final FULL 포함 순효과만 측정 |
| Intel 일반화 | 실제 Intel topology·동일 모델·재보정 정책·별도 확증 | AMD 5/6와 tier6/0/0 범위만 검증 |
| 일반 답변 품질·모든 shape/ISA | 별도 정확성·품질 평가 설계와 실행 | 기존 fixture token equality, R의 제한 8 logits checkpoint |
| donor serving harness의 모든 아이디어/부분 hunk 계보 | 현재 runner 도입 history와 donor4694fc…의 세부 비교 | final runner가 donor harness를 실행/import했다는 증거 없음; 직접 재사용으로 분류 안 함 |
| 캠페인간 CPU25 B0 속도 변동 원인 | 전원/열/주파수/배경 상태의 원인 분리 실험 | CAUSE_UNDETERMINED. 상대 gain 증가를 새 runtime 개선으로 주장하지 않음 |

## 이전 status가 서로 다른 이유

- `persistent-pool-port-v1/integration-delta.md`의 WAITING_NUMERICAL_BASELINE/NOT_RUN은 이식 준비 당시 상태다. 이후 `r-pool-validation-v1`의 R 및 수정 P 모델/lifecycle 검증과 시점이 다르다.
- R identity의 LINKED_NOT_MODEL_VALIDATED, E identity의 BUILT_NOT_INFERENCE_VALIDATED, P-padding-fix identity의 LINKED_PENDING_FRESH_FUNCTIONAL_GATE는 build 시점 기록이다. 뒤의 R-checkpoint/AP-functional-checkpoint와 충돌한다고 원본을 고치지 않았다.
- 원래 P는 null-padding guard에서 실패했다. 수정 P는 별도 overlay/identity다. observer-v1의 미지원 getter 실패도 observer-v2 결과로 덮어쓰지 않았다.
- HINT OFF 전체 context의 기존 `newa_resource` 미선언 오류는 남아 있다. HINT ON final을 확인한 것이 모든 build mode PASS는 아니다.
- 두 캠페인 `heldout-1/2`는 historical fixture label이다. 이번 재현·감사에서 unseen dataset이라는 뜻이 아니다.
- final A_L은 연구 역할이다. 기본 `run.sh`의 pre-R NEW_A 경로와 동일하지 않다. [진입점 증거](evidence/entrypoint-scope.json).

## 조회 실패를 숨기지 않음

public donor에서 local59→head 비교는 조회되지 않았다. 보존 Git object를 읽어 local59→공유5219→B0를 확인하고, 정확한 donor pin에 대해5219 ancestry를 별도로 확인했다. donor HEAD에 `server-phase.h` 파일을 가정한 조회도404였다. 실제 shared server/scx classifier와 local header 분리를 기준으로 조사했다. 감사용 raw 파일명 첫 시도 오류도 수정 이력을 남겼다. [조회·감사 시도 기록](evidence/audit-attempts.json).

이 목록은 새 실험을 자동으로 실행하라는 명령이 아니다. 이번 작업은 감사 패키지 완료 후 종료한다.
