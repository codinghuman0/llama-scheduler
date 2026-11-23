# A 구성 요소 기여 검증

상태: **CONFIRMED_SCOPED_SYSTEM_GAIN_ONE_CAMPAIGN**. 이번 구성 요소 캠페인은 **1개**이며, 이전 A/B0 독립 확인 2개와 구분합니다.

## 보존된 A와 이번 변경

기존 파일 6,914개의 내용과 mode를 확인했습니다. B0/R/A/P, 모델, 소스, 과거 원시 결과와 실패 기록은 변경하지 않았습니다. 새 최적화나 빌드는 없으며 신규 코드는 실행·검증·분석 도구뿐입니다.

기존 A/B0: ambient +16.55%, +16.33%; cpu25 +25.97%, +26.17% (각 캠페인 조건별 8 pairs). 이 결과는 기본 Linux에서의 누적 runtime 효과입니다. 이번 결과와 합산하지 않습니다.

B0_L은 역사적 원본 소스의 보존된 재빌드입니다. F6_L/A_L은 동일 A binary/DSO와 센서·guard를 유지하며 적격 multi-token Decode 선택만 fixed6/pressure로 다릅니다. A_S는 A_L에 기존 observe 스케줄러를 추가합니다. pool off, 같은 모델/입력/자원/정상 요청 내부 KV만 사용합니다.

## 직접 측정

| 조건 | 비교 | 평균 paired gain | bootstrap 95% 구간 | faster blocks | paired wall 감소 |
|---|---|---:|---|---:|---:|
| ambient | A_L/B0_L | +16.204% | [+15.843, +16.579]% | 8/8 | +13.942% |
| ambient | F6_L/B0_L | +15.934% | [+15.451, +16.448]% | 8/8 | +13.741% |
| ambient | A_L/F6_L | +0.235% | [-0.129, +0.626]% | 7/8 | +0.231% |
| ambient | A_S/A_L | +0.033% | [-0.298, +0.341]% | 5/8 | +0.030% |
| ambient | A_S/B0_L | +16.242% | [+15.769, +16.739]% | 8/8 | +13.968% |
| cpu25 | A_L/B0_L | +32.390% | [+27.700, +37.417]% | 8/8 | +24.194% |
| cpu25 | F6_L/B0_L | +18.952% | [+14.711, +23.339]% | 8/8 | +15.656% |
| cpu25 | A_L/F6_L | +11.328% | [+9.130, +13.637]% | 8/8 | +10.095% |
| cpu25 | A_S/A_L | -0.617% | [-1.686, +0.449]% | 2/8 | -0.647% |
| cpu25 | A_S/B0_L | +31.561% | [+26.526, +36.520]% | 8/8 | +23.709% |

| 조건 | arm | tokens/s 평균 | cohort wall s 평균 | process CPU s 평균 |
|---|---|---:|---:|---:|
| ambient | B0_L | 49.3031 | 20.7698 | 124.2825 |
| ambient | F6_L | 57.1584 | 17.9156 | 107.1475 |
| ambient | A_L | 57.2913 | 17.8739 | 106.9125 |
| ambient | A_S | 57.3101 | 17.8685 | 106.8738 |
| cpu25 | B0_L | 38.6799 | 26.5733 | 150.3313 |
| cpu25 | F6_L | 45.8732 | 22.3457 | 126.6863 |
| cpu25 | A_L | 51.0267 | 20.0731 | 104.9050 |
| cpu25 | A_S | 50.7013 | 20.1989 | 102.8563 |

완결된 block 내 직접 비율의 평균입니다. 절대값 평균의 비율과는 다릅니다. cohort별 4 blocks, 50:50 stratified paired bootstrap 10,000회(seed 20261122); 같은 resample에 모든 arm을 유지했습니다. cohort별 결과와 모든 block은 component-summary.json에 있습니다. 보조 비교의 CI는 다중 비교 오류율 보장이 아닙니다.

## E의 적격 Decode 선택 기여

- ambient: **inconclusive (동일한 실제 선택)**. A_L/F6_L +0.235%. 적격 multi-token 선택 [5,6] 횟수: F6_L [0, 1016], A_L [0, 1016]. F6_L shadow choices [6].
  실제 선택이 같으므로 이 조건의 작은 성능 차이를 adaptive worker-choice 이득으로 해석하지 않습니다.
- cpu25: **positive**. A_L/F6_L +11.328%. 적격 multi-token 선택 [5,6] 횟수: F6_L [0, 1016], A_L [1016, 0]. F6_L shadow choices [5].

센서 raw counter, threshold=.125, margin=.02, epoch/task 연속성 및 invalidation은 독립 재계산했습니다. fixed6은 센서와 검사를 끄지 않습니다. 단일 token Decode의 5-worker 예외 및 Mixed/UNKNOWN 6-worker fallback은 소스에 보존되어 있으며, 본 8-request fixture가 모든 fallback을 따로 유발한 검증은 아닙니다. submitted 선택과 실제 OpenMP 팀 로그를 함께 확인했습니다.

## S의 추가 효과와 최종 조합

- ambient A_S/A_L: +0.033%, inconclusive; 동일 userspace 정책에 S를 추가한 효과입니다.
- ambient A_S/B0_L: +16.242%, positive; system gate=True, CI 하한 >=5%=True.
  A_S 실제 선택: {'eligible_multitoken_5_6': [0, 1016], 'shadow_choices': [6], 'locked_epochs': 8}. A_L과 aggregate 선택 일치: True. 선택이 다르면 scheduler와 E의 매개 효과를 포함합니다.
- cpu25 A_S/A_L: -0.617%, inconclusive; 동일 userspace 정책에 S를 추가한 효과입니다.
- cpu25 A_S/B0_L: +31.561%, positive; system gate=True, CI 하한 >=5%=True.
  A_S 실제 선택: {'eligible_multitoken_5_6': [1016, 0], 'shadow_choices': [5], 'locked_epochs': 8}. A_L과 aggregate 선택 일치: True. 선택이 다르면 scheduler와 E의 매개 효과를 포함합니다.

S는 보존된 **observe**, FULL diagnostics, partial switching, fixed affinity 구성입니다. phase 상태와 Decode shadow attempts를 기록하지만 실제 phase 기반 배치 변경은 하지 않습니다. 따라서 이 결과를 새로운 phase-aware kernel dispatch 정책의 증명으로 부르지 않습니다. loader/launcher와 부하 generator는 Linux, 선택 server/worker는 SCHED_EXT; matching marker ELF/PID, actual ops/BPF IDs/tags, phase bits, zero mask/tracking failure, zero handoff moves, 일정 enable_seq/무 bypass 증가, 정상 cleanup을 확인했습니다. 안전 진단 비용을 제거하거나 성능에서 빼지 않았습니다.

기존 A는 기본 실사용 구성으로 보존합니다. 스케줄러 조합은 본 캠페인의 기여 분석 연구 구성입니다. S 효과가 음수라면 원본 대비 최종 조합 gain과 별도로 그대로 보고합니다.

## 정확성·실패·범위

기능 smoke 8 fresh servers; 유효 measured visits 64. 모든 유효 warmup/measurement에서 실제 128 tokens/request, 8 distinct requests, cache_n=0, 기존 B0 oracle exact tokens를 확인했습니다. 한 요청의 token이나 여덟 요청을 독립 반복으로 세지 않았습니다.
실제 measured cpu25 소비 범위: [0.25116146998796585, 0.2529155665560898] core. 동일 CPU10 affinity와 정상 정책, .0125 CPU seconds/.05 seconds 부하입니다. 총 CPU seconds는 arm의 wall time에 따라 달라도 평균 core 소비를 검증했습니다.
실패/미실행: 0 planned visits; results/attribution-v1/campaigns.json 참조. 본 측정 전 분석기에서 load policy를 SCHED_EXT로 잘못 기대한 검사를 수정했습니다. 실제 runner는 처음부터 load policy 0을 검증했습니다. 모델 방문을 대체하지 않았고 수정 기록을 보존했습니다.

같은 AMD·모델·기존 두 cohort·고정 부하 범위입니다. Intel, 일반 품질, 모든 입력/길이, 변동 부하, 모든 static 정책에 대한 우월성을 입증하지 않습니다. fixed6_S/fixed5가 없으므로 완전한 요인 상호작용 분해가 아닙니다. 이번 결과는 한 캠페인이며 A_S 또는 E가 두 번 독립 재현된 결과가 아닙니다. throughput 증가와 wall 감소를 구분하며 CPU seconds는 에너지가 아닙니다. nonstream TTFT/p95 token latency는 측정하지 않았습니다. 과거 dynamic-affinity 실패는 해결되지 않았습니다.

## 재현과 다음 단계 하나

```bash
./reproduce.sh verify
./reproduce.sh recalculate --name attribution-v1
./reproduce.sh analyze --name attribution-v1
```

다음 단계: 동결된 네 arm 구성 요소 캠페인을 별도로 독립 재현합니다. 현재 goal에서는 반복을 추가하지 않습니다. 실행 명령과 권한/cleanup 범위는 README.md와 reproduce.sh에 있습니다.
