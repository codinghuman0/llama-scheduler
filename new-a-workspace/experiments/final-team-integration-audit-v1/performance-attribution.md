# 기존 성능의 직접 재계산과 기여 해석

이번 감사의 새 성능 측정은0회다. 원본 attribution과 후속 replication을 각각 유지했다. `code/collect_usage.py`는 기존 read-only recalculate.py로 실제 token array·oracle·prompt count/cache_n·seed·worker policy/affinity·background load·planned order·완결 block을 확인했다. 두 캠페인 각각128 raw cohorts(warmup64+measured64),10 comparisons가 PASS다. 작은 검토 패키지의 timestamp/token-count 발췌는 `python3 -B code/recalculate_packaged.py`로 다시 계산할 수 있다.

## 고정된 지표와 범위

primary는 실제 generated tokens / cohort HTTP 전체 wall seconds다. atomic 8 distinct prompt 배열, 요청당128, cohort당1024 tokens. queueing/prefill/decode/policy/응답 완료를 포함하고, loading과 fresh server당 warmup 한 cohort를 제외한다. 비stream 응답이라 별도 TTFT를 측정하지 않았다. 두 fixture는 historical heldout-1/2이며 새 unseen population 검증이 아니다.

각 캠페인은4 arms ×2조건 ×8blocks =64 timed visits. 각 조건에서 cohort당4 blocks, 순서 균형 교차, 장비 내 직렬 실행이었다. gain_i=100*(candidate_tps_i/baseline_tps_i-1), 표에는 그8개 비율의 산술평균을 쓴다. 10,000회 cohort-stratified paired-block bootstrap, seed20261122, 선형 percentile95% CI다. 요청8개를 독립 n=8로 세지 않는다. 서로 다른 campaign을 합치거나 개선율을 더하지 않는다.

같은 AMD Ryzen5 5500U, 같은 model hash, CPU0,2,4,6,8,10, controller11, threads5/batch6, OpenMP, GPU0/specnone. CPU25는 CPU10에서 약0.25 core이며 장비 전체25%가 아니다. 실제 부하는 original0.251161~0.252916, replication0.250549~0.252892 core. 모든 arm의 measured 부하가 보존된0.22~0.28 범위였다.

## 절대 성능

아래 t/s는8 cohort t/s의 산술평균이다. 평균 t/s의 비율은 아래 primary mean paired gain과 같은 집계가 아니다.

| 캠페인 | 조건 | arm | mean t/s | mean cohort wall s |
|---|---|---|---:|---:|
| original | ambient | B0_L | 49.3031 | 20.7698 |
| original | ambient | F6_L | 57.1584 | 17.9156 |
| original | ambient | A_L | 57.2913 | 17.8739 |
| original | ambient | A_S | 57.3101 | 17.8685 |
| original | cpu25 | B0_L | 38.6799 | 26.5733 |
| original | cpu25 | F6_L | 45.8732 | 22.3457 |
| original | cpu25 | A_L | 51.0267 | 20.0731 |
| original | cpu25 | A_S | 50.7013 | 20.1989 |
| replication | ambient | B0_L | 49.4990 | 20.6878 |
| replication | ambient | F6_L | 57.3596 | 17.8527 |
| replication | ambient | A_L | 57.1233 | 17.9265 |
| replication | ambient | A_S | 57.5482 | 17.7943 |
| replication | cpu25 | B0_L | 39.9585 | 25.6834 |
| replication | cpu25 | F6_L | 46.0468 | 22.2876 |
| replication | cpu25 | A_L | 51.5211 | 19.8771 |
| replication | cpu25 | A_S | 50.8702 | 20.1307 |

## 각 캠페인의 다섯 직접 비교

| 캠페인 | 조건 | 비교 | mean paired gain % | bootstrap95% CI % | faster/8 |
|---|---|---|---:|---|---:|
| original | ambient | A_L/B0_L | +16.203718 | [+15.843335, +16.579199] | 8/8 |
| original | ambient | F6_L/B0_L | +15.934377 | [+15.451245, +16.447819] | 8/8 |
| original | ambient | A_L/F6_L | +0.234806 | [-0.129064, +0.626308] | 7/8 |
| original | ambient | A_S/A_L | +0.032870 | [-0.298443, +0.341224] | 5/8 |
| original | ambient | A_S/B0_L | +16.241910 | [+15.768904, +16.739479] | 8/8 |
| original | cpu25 | A_L/B0_L | +32.389636 | [+27.699838, +37.416916] | 8/8 |
| original | cpu25 | F6_L/B0_L | +18.951725 | [+14.710726, +23.339446] | 8/8 |
| original | cpu25 | A_L/F6_L | +11.327640 | [+9.130041, +13.636932] | 8/8 |
| original | cpu25 | A_S/A_L | -0.616854 | [-1.686154, +0.448725] | 2/8 |
| original | cpu25 | A_S/B0_L | +31.560920 | [+26.525535, +36.520062] | 8/8 |
| replication | ambient | A_L/B0_L | +15.406540 | [+14.785503, +15.927900] | 8/8 |
| replication | ambient | F6_L/B0_L | +15.883744 | [+15.212471, +16.446321] | 8/8 |
| replication | ambient | A_L/F6_L | -0.409712 | [-0.775458, +0.008946] | 1/8 |
| replication | ambient | A_S/A_L | +0.745311 | [+0.374549, +1.116527] | 7/8 |
| replication | ambient | A_S/B0_L | +16.264913 | [+15.558196, +16.842314] | 8/8 |
| replication | cpu25 | A_L/B0_L | +29.228905 | [+25.233339, +33.619174] | 8/8 |
| replication | cpu25 | F6_L/B0_L | +15.255742 | [+14.139068, +16.363328] | 8/8 |
| replication | cpu25 | A_L/F6_L | +12.126291 | [+8.741188, +15.971475] | 8/8 |
| replication | cpu25 | A_S/A_L | -1.255516 | [-1.803003, -0.697087] | 2/8 |
| replication | cpu25 | A_S/B0_L | +27.578559 | [+23.840556, +31.858996] | 8/8 |

전체 A_L/B0와 A_S/B0는 두 campaign·두 조건에서 mean>=5%, CI lower>0, faster>=75%를 통과한다. 이 범위에서 lower도5% 이상인 더 강한 증거다. 이를 모든 장비/요청에서 최소5% 보장으로 표현하지 않는다. 기존 scoped system 판정을 재확인한 것이고, 새로운 kernel 우위 판정이 아니다.

F6/B0는 E의 적응 선택을 제외한 runtime 묶음 효과다. F6에도 센서·guard·phase 전달·검증된 연산 경로가 남아 있으므로 Q4 단독 효과나 phase 전체 제거 비교가 아니다. A/F6 CPU25는 fixed6 대비5-worker 선택 효과가 두 번 positive다. ambient는 실제 선택이 같고 두 CI가0을 포함한다. phase label 자체의 고유 가치는 NOT_ISOLATED다.

A_S/A_L는 FULL 관측 비용까지 포함한 scheduler 구성의 순효과다. original 양 조건은 inconclusive, replication ambient는 positive, CPU25는 negative다. 계측 비용을 가정해 빼거나 “scheduler가 불필요하므로 모든 kernel 정책의 가능성도0”으로 확대하지 않는다. fixed6_S가 없어 E×scheduler 상승효과의 완전한 분해는 불가능하다.

## E 사용량: measured와 warmup/기능검사 분리

다음은 measured 정책 select 호출이다. B0에는 E epoch 계측이 없으므로 표의0을 “Decode가0”으로 해석하지 않는다. 전체 graph/physical ubatch 분모는 관측되지 않아 JSON에서null이다. 각 선택이 내부 여러 graph를 포함할 수 있다.

| 캠페인 | 조건 | arm | select calls | all Decode 5/6 | eligible multi 5/6 | Prefill6 / Mixed6 |
|---|---|---|---:|---|---|---|
| original | ambient | F6_L | 1032 | [0, 1016] | [0, 1016] | 8 / 8 |
| original | ambient | A_S | 1032 | [0, 1016] | [0, 1016] | 8 / 8 |
| original | ambient | A_L | 1032 | [0, 1016] | [0, 1016] | 8 / 8 |
| original | cpu25 | F6_L | 1032 | [0, 1016] | [0, 1016] | 8 / 8 |
| original | cpu25 | A_L | 1032 | [1016, 0] | [1016, 0] | 8 / 8 |
| original | cpu25 | A_S | 1032 | [1016, 0] | [1016, 0] | 8 / 8 |
| replication | ambient | F6_L | 1032 | [0, 1016] | [0, 1016] | 8 / 8 |
| replication | ambient | A_S | 1032 | [0, 1016] | [0, 1016] | 8 / 8 |
| replication | ambient | A_L | 1032 | [0, 1016] | [0, 1016] | 8 / 8 |
| replication | cpu25 | F6_L | 1032 | [0, 1016] | [0, 1016] | 8 / 8 |
| replication | cpu25 | A_L | 1032 | [1016, 0] | [1016, 0] | 8 / 8 |
| replication | cpu25 | A_S | 1032 | [1016, 0] | [1016, 0] | 8 / 8 |

각 measured arm/조건의1,016 eligible multi calls는8cohorts×127calls이며 tokens가 아니다. 이 raw에서는 각 cohort가8-token eligible126calls와4-token tail1call로 끝난다. warmup, functional-check, measured는 [observed-usage.json](observed-usage.json)의48개 group에 따로 기록돼 있다. 총144visits는 timed128 + Linux smoke12 + scheduler admission4이며, 각 visit의 warmup을 성능 반복수로 더하지 않았다. libgomp affinity-format `NEWA_TEAM`은 변화 시점의 team 보고로 전체 graph 계수가 아니다.

## Scheduler 사용량: whole-visit 통계

| 캠페인 | 단계 | 조건 | visits | tier0 / tier1 / tier2 / fallback | Decode attempts | moved |
|---|---|---|---:|---|---:|---:|
| original | functional | cpu25 | 2 | [3037, 0, 0, 93] | 42 | 0 |
| original | performance | ambient | 8 | [2164, 0, 0, 453] | 344 | 0 |
| original | performance | cpu25 | 8 | [12265, 0, 0, 383] | 171 | 0 |
| replication | functional | cpu25 | 2 | [2786, 0, 0, 119] | 56 | 0 |
| replication | performance | ambient | 8 | [2104, 0, 0, 447] | 341 | 0 |
| replication | performance | cpu25 | 8 | [11991, 0, 0, 405] | 184 | 0 |

이는 warmup/startup/teardown을 포함한 서버 수명 전체의 callback/attempt 계수다. timed visit으로 묶었다고 measured-only delta가 되는 것은 아니다. phase_seen14는 Prefill/Decode/Mixed를 관측한 비트마스크이며14회 이벤트가 아니다. phase event count는null이다. topology6/0/0에서 tier1/2가0인 것은 Intel E/SMT 정책 성과가 아니다. 모든36 A_S visit의 mask/tracking/event-drop 검사 오류는0이고 live monitor는 PASS다.

## Pool P/A: 독립 n4 pilot

| 조건 | mean paired gain % | bootstrap95% CI % | faster/4 |
|---|---:|---|---:|
| ambient | -1.654649 | [-3.304312, -0.004986] | 1/4 |
| cpu25 | +1.051083 | [+0.177626, +2.266769] | 3/4 |

P/A는 별도 n4 pilot이며 full confirmation이 아니다. E actual choice는 pair 간 동일했다. P steady512 graphs 모두 persistent attached, A512는 disposable이며 P creation/free 각6회는 초기화와 두 resume/teardown을 포함한다. OpenMP에서 GGML pool allocation과 OS worker creation/parking은 다르다. 따라서 pool이 최종 gain에 기여했다고 말하지 않으며, 결과 방향이 엇갈려 TESTED_NOT_ADOPTED로 남긴다.

## R 경로와 정확성 진단은 timing과 별개

진단 한 서버 수명에서 reference Q4 body의 phase[Unknown,Prefill,Decode,Mixed] 계수는[0,3935,0,2628], retained exact Q4 worker0 calls는[0,0,167201,2656], Q6 worker0 chunks는[0,15739,462873,14003]이다. 서로 다른 단위이며 합쳐 graph 수나 사용 비율을 만들지 않는다. timing과 무거운 route/numeric/lifecycle 진단은 분리돼 있다.

R free-generation과 제한 logits/observer의 후속 PASS는 보존 build identity의 초기 NOT_MODEL_VALIDATED를 소급 변경하지 않는다. 초기 P guard 실패, observer-v1 실패도 보존돼 있다. 일반 품질 동등성은 검증하지 않았다.

## 캠페인간 변동과 금지하는 기여 계산

이전 runtime-only A/B0 CPU25의 B0 약41.08/40.99t/s와 달리 component original은38.68, replication39.96이었다. A는 각각 약51t/s였다. 그 변동 원인은 CAUSE_UNDETERMINED다. runtime 변경이 없으므로 상대 gain이26%에서32%로 커진 것을 새 코드 개선이라고 쓰지 않는다. 유효한 느린 B0 block도 모두 포함했다.

개별 Q4/Q6/API/HINT/메모리, 개인별 몫은 NOT_ISOLATED다. fixed5 대비, phase label만의 효과, fixed6_S interaction도 없다. gain을 더해 전체 성과를 만들지 않았고 단순 캠페인간 평균 비율을 paired gain으로 바꾸지 않았다.
