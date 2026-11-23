# 새 구성 요소 재현 캠페인

새 캠페인 상태: **CONFIRMED_SCOPED_SYSTEM_GAIN_ONE_CAMPAIGN**. 기존 기여 분석과 별개인 새 실행 정확히 1회입니다. 동일 AMD 장비에서 시간적으로 분리했으며 외부 팀/장비 재현이나 새로운 workload 일반화가 아닙니다.

A(E-R), model, runtime/DSO, E sensor/threshold/margin/guards, observe BPF object를 변경하지 않았습니다. persistent pool off. 원본과 cases/fixtures/order/identity는 동일하며 harness 변경은 출력 격리·현재 실행 연결·누락 검출 강화뿐입니다. patch와 protocol-diff.json을 함께 보존했습니다.

| 조건 | 비교 | mean paired gain | bootstrap 95% CI | faster | wall 감소 |
|---|---|---:|---|---:|---:|
| ambient | A_L/B0_L | +15.407% | [+14.786, +15.928]% | 8/8 | +13.345% |
| ambient | F6_L/B0_L | +15.884% | [+15.212, +16.446]% | 8/8 | +13.701% |
| ambient | A_L/F6_L | -0.410% | [-0.775, +0.009]% | 1/8 | -0.415% |
| ambient | A_S/A_L | +0.745% | [+0.375, +1.117]% | 7/8 | +0.736% |
| ambient | A_S/B0_L | +16.265% | [+15.558, +16.842]% | 8/8 | +13.984% |
| cpu25 | A_L/B0_L | +29.229% | [+25.233, +33.619]% | 8/8 | +22.433% |
| cpu25 | F6_L/B0_L | +15.256% | [+14.139, +16.363]% | 8/8 | +13.207% |
| cpu25 | A_L/F6_L | +12.126% | [+8.741, +15.971]% | 8/8 | +10.626% |
| cpu25 | A_S/A_L | -1.256% | [-1.803, -0.697]% | 2/8 | -1.284% |
| cpu25 | A_S/B0_L | +27.579% | [+23.841, +31.859]% | 8/8 | +21.453% |

## 새 캠페인 절대 성능

| 조건 | arm | tokens/s 평균 | cohort wall s 평균 | server CPU s 평균 |
|---|---|---:|---:|---:|
| ambient | B0_L | 49.4990 | 20.6878 | 123.7938 |
| ambient | F6_L | 57.3596 | 17.8527 | 106.7887 |
| ambient | A_L | 57.1233 | 17.9265 | 107.2237 |
| ambient | A_S | 57.5482 | 17.7943 | 106.4387 |
| cpu25 | B0_L | 39.9585 | 25.6834 | 145.8100 |
| cpu25 | F6_L | 46.0468 | 22.2876 | 126.2875 |
| cpu25 | A_L | 51.5211 | 19.8771 | 104.0613 |
| cpu25 | A_S | 50.8702 | 20.1307 | 102.7675 |

## 독립 구성 요소 판정

새 실행 판정: `{"overall_system": "PASS", "E_ambient": "inconclusive_same_observed_choice", "S_ambient": "positive", "E_cpu25": "positive", "S_cpu25": "negative"}`.
- ambient: E의 실제 eligible multi-token worker 선택이 다른 block=[]; A_S와 A_L의 선택이 다른 block=[].
- cpu25: E의 실제 eligible multi-token worker 선택이 다른 block=[1, 2, 3, 4, 5, 6, 7, 8]; A_S와 A_L의 선택이 다른 block=[].

F6_L은 압력 센서와 shadow choice, 유효성/연속성 검사, semantic phase 전달을 유지하고 적격 multi-token Decode만6으로 고정합니다. single-token5 예외와 UNKNOWN/MIXED fallback은 기존 소스 그대로입니다. 이 fixture에서 모든 fallback을 별도 유발했다는 뜻은 아닙니다.

E의 CPU25 판정은 A_L/F6_L CI lower>0와 실제 선택 차이에 근거합니다. 별도5% 기준을 추가하지 않았습니다. ambient에서 두 설정의 선택이 같으면 작은 시간 차이를 선택 효과로 주장하지 않습니다. E에는 semantic phase가 쓰이지만, 이 ablation은 semantic label 자체의 다른 controller 대비 고유 가치를 분리하지 않습니다.

observe/FULL/partial/fixed-affinity S는 phase를 기록하지만 phase-dependent placement를 하지 않습니다. A_S/A_L은 동일 userspace 정책에 S를 추가한 효과이며 실제 E 선택이 달라지면 매개 효과도 포함합니다. CI가0을 포함하면 inconclusive이며 효과0, 동등성, 무오버헤드가 입증된 것이 아닙니다. fixed6_S 또는 fixed5 arm이 없어 완전한 interaction 분해나 모든 static 정책 대비 우월성을 주장하지 않습니다.

실제 SCHED_EXT server/worker, Linux loader/launcher/load, ops/BPF tags, marker ELF/PID, phase bits, FULL mask/tracking/drop/export errors, handoff moved=0, no bypass/detach/fallback 및 정상 cleanup을 검사했습니다. old dynamic-affinity 실패는 여전히 미해결입니다. OpenMP 로그의 관측된 team 크기 집합을 모든 graph의 연속 관측으로 해석하지 않습니다.

## 호출 수·정확성·재계산

실제 호출 집계: `{"fresh_server_starts": 72, "completion_HTTP_calls": 144, "individual_generations": 1152, "actual_generated_tokens": 147456, "warmup_cohorts": 72, "excluded_functional_check_cohorts": 8, "primary_measured_cohorts": 64, "new_full_logits_diagnostic_calls": 0, "warmup_individual_generations": 576, "functional_check_individual_generations": 64, "primary_measured_individual_generations": 512, "valid_smoke_visits": 8}`.

하나의 atomic prompt-array /completion에 distinct request8개, 각128 generated tokens입니다. 독립 HTTP client8개 workload가 아닙니다. 각 fresh server의 동일 warmup1회는 제외하고 측정1회만 primary에 사용했습니다. 모든 유효 warmup/측정 출력은 frozen B0 oracle과 직접 비교했으며 teacher forcing은 사용하지 않았습니다. 기존 R logits checkpoint와 이번 token equality의 범위는 다릅니다. 새 전체 logits 검사는0회입니다.

Primary는 실제 generated tokens / 전체 cohort HTTP wall seconds입니다. queueing·prefill·decode·정책 비용·응답 read/JSON parse를 포함하고 loading과 warmup을 제외합니다. 8개 요청이나1024 tokens가 아니라8 paired blocks가 반복 단위입니다. cohort별4 blocks, 동일 가중치,10,000 stratified resamples(seed20261122), 기존 선형 percentile을 유지했습니다. 다섯 contrast는 같은 complete-block resample을 공유합니다.

강화된 모델 없는 재계산: PASS. 원본 코드와 정상 자료의 출력 dictionary가 정확히 같음을 확인했고, 임시 복사본에서 한 방문을 누락시키면 nonzero INCOMPLETE_INVALID가 됨을 확인했습니다. 원본 코드는 수정하지 않았습니다.

CPU25는 CPU10의 .0125 process CPU seconds/.05 seconds 고정 간섭, 약0.25 core입니다. 머신 전체25% 또는 cgroup quota25%가 아닙니다. measured .22-.28 core, affinity와 Linux policy를 실제 counter로 검증했습니다. CPU seconds는 에너지가 아니며 nonstream TTFT/p95 token latency는 측정하지 않았습니다.

기본 성능 실행의 역할은 A_L, A_S는 scoped integration/evaluation입니다. runtime 경로나 기본 symlink를 교체하지 않았습니다. 이번 goal 후 추가 기능 연구나 세 번째 기여 캠페인을 자동 실행하지 않습니다. 현재 지원 범위의 제출용 연구 기준점이며 production-ready 선언이 아닙니다.
