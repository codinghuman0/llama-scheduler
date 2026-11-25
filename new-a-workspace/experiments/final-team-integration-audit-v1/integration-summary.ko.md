# 최종 팀 통합 감사

통합 상태는 **FUNCTIONAL_INTEGRATION_MAPPED**, 세부 계보 상태는 **PARTIAL_PROVENANCE**다. 기존 실행에서 기능들이 실제로 연결됐음을 확인했다. 모든 팀원의 최신 기능을 합쳤다는 뜻은 아니며, 개인별 성능 기여율은 산정할 수 없다. 이번 감사는 기존 자료의 재계산·정적 조사만 수행했다. 새 모델 호출, 빌드, BPF 로드, sudo, Git 변경은 없다.

핵심 결론은 **공유 semantic phase/profile 기반 → 로컬 E 자원 선택 → 실제 CPU worker**가 최종 A에서 연결되고, A_S에서는 **동일 runtime → scalar marker → 실제 sched_ext 실행·관측**까지 연결됐다는 것이다. 커널 관측값을 E에 돌려주는 공동 제어 경로는 조사한 범위에서 찾지 못했다. 현재 observe의 CPU 배치는 phase-independent다.

## 최종 구성과 이름

| 이름 | 실제 구성·역할 |
|---|---|
| B0_L | `7a2db1a0cf38e5f4eb278a58c3903d295258d0ea`의 보존 재빌드 + Linux. 최신 upstream이나 유실된 원래 바이너리와의 byte identity가 아니다. |
| B1 | `runtime/B1`의 검증된 pre-R overlay/DSO 조합. CPU `ea47729c…`, server-impl `10fc183c…`. |
| pre-R E | B1 연산 라이브러리에 동결 E server-impl `9204b0d4…`를 연결한 `runtime/NEW_A`. B1 그 자체와 구별한다. |
| R | semantic Prefill custom Q4만 reference body로 복원한 CPU DSO `45ddfa4d…`. exact Q4 Decode/Mixed, Q6, phase bridge 유지. |
| A | R 연산 라이브러리 + byte-identical E server. donor pool owner 미포함; 기존 optional pool off. |
| F6_L | A와 sensor/guard/phase를 유지하고 적격 multi-token Decode 선택만 fixed6 + Linux. 완전한 phase-off가 아니다. |
| A_L | pressure A + Linux, 연구상 기본 성능 역할. |
| A_S | 동일 pressure A + selected-child observe/FULL/partial/fixed-affinity scheduler, 평가 역할. |
| P | donor pool을 선택 이식한 별도 server. padding guard 수정 후 실제 모델/lifecycle 검증, 제한 pilot 후 채택 보류. |

**실행 진입점 주의:** 현재 `new-a-workspace/run.sh`는 기본적으로 pre-R `runtime/NEW_A`를 선택한다. A_L 역할 지정 때 기본 경로/tag를 바꾸지 않았다는 원래 release map과 일치한다. 이 명령을 최종 A_L 실행이라고 소개하면 안 된다. 이번 감사도 경로를 변경하지 않았다. [실제 대응과 hash](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/evidence/entrypoint-scope.json), [동결 cases/release map](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/evidence/preserved/a-component-scheduler-replication-v1/frozen-release-map.json).

## 어디까지 통합됐는가

1. **공유 기반 재사용:** 로컬 `59abec45…`의 Git object와 donor pin을 대조했다. 공통 조상 `5219055a…`가 확인됐고, profile API 도입 `a9432639…`, semantic token-origin/서버 profile 도입 `5219055a…`는 공유 계보다. 최신 donor HEAD에서 이번에 처음 가져온 기능으로 세지 않는다. 로컬 lightweight source와 final의 profile API/engine, phase header는 hash-identical이다.
2. **로컬 연결·경량화:** `c2c39851…`, `2ec58295…`, `1bb4bd7d…`, `e5b38588…`, `c8b9d61d…`에서 transition marker, HINT/TRACE 분리와 진단 조건부화/제거를 추적했다. 이후 overlay는 marker가 userspace CPU setter도 호출하도록 연결한다. HINT를 끄면 CPU 연산 eligibility까지 달라질 수 있다.
3. **E 의사결정 실행:** 순수 Prefill의 선택 CPU 사용량과 process CPU 시간으로 관측한 경합 신호를 후속 적격 Decode의 GENERATION5/BATCH6 profile 선택에 사용했다. 최종 raw의 CPU25 선택 차이와 libgomp team 보고를 연결했다. 이는 사용자 공간의 병렬도 제어다.
4. **커널 실행 통합:** A_S의 대상 server/worker에 SCHED_EXT, 정확한 BPF/marker ELF, live monitor, 정상 정리 증거가 있다. 총 32 timed visits와 4 admission visits를 구분했다. FULL의 `phase_seen`은 비트맵이고 observe의 handoff moved는 전부 0이다. phase 수신이 phase-dependent 배치를 뜻하지 않는다.
5. **선택 이식 후 미채택:** donor pool header는 P overlay와 byte-identical이며 P ELF에는 owner가 있다. A ELF/source에는 그 owner가 없다. pool off 때문에 compute-profile API가 꺼진 것은 아니다. v2 active/idle, Lite, Intel4/8, donor serving harness는 최종 활성 기능으로 인정하지 않는다.

세부 34개 기능은 [통합 표](integration-matrix.md), [JSON](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/integration-matrix.json), [CSV](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/integration-matrix.csv)에 출처·채택·실행·성능의 네 축으로 기록했다. 파일/LOC 비율을 통합률이나 개인 점수로 환산하지 않았다.

## 성능과 기여는 별도 판정

기존 기여 캠페인과 재현 캠페인을 각각 재계산했다. 조건별 완결 paired block은 각 8개다.

| 비교 | ambient: 기존 / 재현 | CPU25: 기존 / 재현 | 해석 |
|---|---:|---:|---|
| A_L/B0_L | +16.20 / +15.41% | +32.39 / +29.23% | Linux 위 전체 조합의 직접 성과 |
| F6_L/B0_L | +15.93 / +15.88% | +18.95 / +15.26% | 적응 선택을 제외한 누적 묶음 효과 |
| A_L/F6_L | +0.23 / −0.41% | +11.33 / +12.13% | CPU25에서 E 선택 기여 재현 |
| A_S/A_L | +0.03 / +0.75% | −0.62 / −1.26% | observe/FULL 추가 이득 일관성 없음 |
| A_S/B0_L | +16.24 / +16.26% | +31.56 / +27.58% | scheduler를 포함한 전체 조합 |

E의 독립 기여는 **CPU25에서 fixed6 대비 positive**다. phase label 자체의 고유 기여는 **not-isolated**다. 커널 scheduler의 추가 효과는 기존 캠페인 양 조건 inconclusive, 재현 ambient positive/CPU25 negative다. 모든 개선율은 block별 직접 비율의 평균이며 더하지 않는다. 전체 system gain이 scheduler의 필요성이나 기여를 입증하지 않는다. 모든 CI·절대 t/s·faster 비율은 [성능 기여 보고서](performance-attribution.md)에 있다.

## 정확성·범위·남은 구멍

AMD Ryzen 5 5500U의 고정 6 physical-core envelope, CPU-only, OpenMP, 동일 모델 hash, 두 atomic 8-prompt cohort, 각 128 generated tokens 범위다. CPU25는 CPU10에서 약 **0.25 core**를 소비하는 부하이며 장비 전체 25%가 아니다. `heldout-1/2`는 역사적 이름이며 이번 재현에서 새로 보지 않은 prompt라는 뜻이 아니다.

보존 raw에서 출력 token과 cache_n=0, 동일 입력·seed·온도·worker affinity/policy·실제 부하를 다시 확인했다. 별도 R 정확성 자료는 16 fresh servers/144 완료 generation, 제한된 8 logits checkpoint의 byte equality를 기록한다. 모든 모델·shape의 일반 품질 동등성 증명이 아니다. native barrier는 OpenMP 빌드에서 비활성이고, huge-page advice는 실제 huge-page residency 증거가 아니다.

동결 source → compile/link 기록 → ELF hash → 실제 loaded DSO를 연결했지만 **모든 overlay가 하나의 clean commit에서 재빌드 가능하다는 증명은 없다**. 이번에는 clean build를 금지된 범위로 수행하지 않았다. 일부 dirty E/CPU overlay의 정확한 개인/도입 commit 귀속, scheduler 공통 hunk의 최초 저자는 UNKNOWN으로 남긴다. [누락 증거](missing-evidence.md)에 필요한 자료를 적었다.

교수님께는 “공유 phase/profile 기반을 실제 자원 선택과 CPU 연산 경로에 연결해 성과를 검증했고, 커널 연결도 실행했지만 커널의 일관된 추가 속도 우위는 얻지 못했다”고 설명할 수 있다. [발표용 문서](professor-brief.ko.md)와 [예상 질문 9개](professor-qa.ko.md)를 함께 제공한다.
