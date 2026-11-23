# NEW_A phase scheduling 결과

**상태: CONFIRMED_SYSTEM_GAIN**

첫 ORIGINAL 캠페인은 디스크 안전 기준으로62회 후 중단됐습니다. 그 원시 기록을 보존하고 통계에 섞지 않았습니다. 이후 사전 등록한 회복 캠페인 두 개를 각각64회 처음부터 실행했습니다. 동결된 후보·지표·반복 수·성공 기준은 유지했습니다. 원시 REPLAY 표기와 원래 confirmation_success=false를 바꾸지 않고 recovery_confirmation_success를 별도로 판정했습니다.

Primary는 실제 generated tokens / cohort 전체 HTTP wall time입니다. 각 캠페인의 ambient/cpu25마다8 paired blocks를 사용했습니다. 다음은 블록별 개선율의 평균이며, 요청8개를 독립 반복으로 부풀리지 않았습니다.

| 회복 캠페인 | 조건 | 비교 | Baseline tokens/s | Candidate tokens/s | 평균 paired gain | Bootstrap95% | Faster pairs |
|---|---|---|---:|---:|---:|---|---:|
| 1 | ambient | C/B0 | 46.7744 | 55.2041 | +18.024% | [+17.621, +18.426]% | 100.0% |
| 1 | ambient | B1/B0 | 46.7744 | 54.8950 | +17.362% | [+16.370, +18.025]% | 100.0% |
| 1 | ambient | C/B1 | 54.8950 | 55.2041 | +0.577% | [-0.150, +1.586]% | 50.0% |
| 1 | ambient | C/C-off | 55.3190 | 55.2041 | -0.206% | [-0.508, +0.114]% | 37.5% |
| 1 | cpu25 | C/B0 | 39.4996 | 48.0405 | +21.637% | [+19.598, +23.746]% | 100.0% |
| 1 | cpu25 | B1/B0 | 39.4996 | 46.2536 | +17.106% | [+15.254, +18.397]% | 100.0% |
| 1 | cpu25 | C/B1 | 46.2536 | 48.0405 | +3.889% | [+2.091, +5.549]% | 87.5% |
| 1 | cpu25 | C/C-off | 45.4972 | 48.0405 | +5.589% | [+4.350, +6.935]% | 100.0% |
| 2 | ambient | C/B0 | 46.9322 | 55.4318 | +18.110% | [+17.851, +18.386]% | 100.0% |
| 2 | ambient | B1/B0 | 46.9322 | 55.1274 | +17.463% | [+17.061, +17.907]% | 100.0% |
| 2 | ambient | C/B1 | 55.1274 | 55.4318 | +0.555% | [+0.003, +1.079]% | 62.5% |
| 2 | ambient | C/C-off | 55.3743 | 55.4318 | +0.105% | [-0.201, +0.462]% | 37.5% |
| 2 | cpu25 | C/B0 | 39.3080 | 47.1674 | +20.043% | [+17.366, +23.051]% | 100.0% |
| 2 | cpu25 | B1/B0 | 39.3080 | 46.2038 | +17.559% | [+16.145, +19.212]% | 100.0% |
| 2 | cpu25 | C/B1 | 46.2038 | 47.1674 | +2.117% | [+0.022, +4.186]% | 62.5% |
| 2 | cpu25 | C/C-off | 45.6710 | 47.1674 | +3.285% | [+1.347, +5.433]% | 100.0% |

기존 누적 개선은 B1/B0, 이번 통합 변경은 C/B1, 신규 의사결정 ablation은 C/C-off입니다. C/B0는 직접 측정했으며 비율을 더해 만들지 않았습니다.

Phase 정책의 독립 worker-choice 기여: **inconclusive**. 조건별: {"ambient": "inconclusive", "cpu25": "positive"}. 실제 선택이 같았던 조건의 작은 시간 차이는 worker 선택의 효과로 해석하지 않습니다. 음수 timing 결과도 표에 그대로 포함했습니다.

같은 userspace 정책의 탐색 pilot(n=2)에서 연구 scheduler/Linux는 ambient -0.581% / cpu25 -2.658%였습니다. 순수 kernel scheduler 이득은 입증되지 않았습니다.

단일 요청·긴 입력·짧은 출력 회귀와 불확실성은 result-summary.json의 regression.by_cohort에 있습니다. 배경 부하의 실제 CPU 소비는 delivered_load_by_campaign에 있습니다.

B0/B1의 기존 출력 차이와 반복·불완전한 답변을 review/output-quality-scope.md에 기록했습니다. 이 결과는 고정 생성 작업의 처리량이며 올바르거나 유용한 답변의 처리량·품질 향상 증거가 아닙니다.

적용 범위: 현재 AMD5500U의 동일6-CPU envelope,8개 동시 distinct request, 고정128-token 출력. Intel은 미측정입니다. 선택 mask 밖의 SMT 간섭, Prefill 이후 바뀐 부하와 메모리/주파수 효과는 센서의 보장 범위가 아닙니다.

재계산: `bash recovery/reproduce.sh analyze`. 검사: `bash recovery/reproduce.sh verify`. 실제 재실행: `bash recovery/reproduce.sh smoke|pilot|full` 중 한 모드 (일반 계정, 터미널 sudo -v; 새 REPLAY로 보존). 원래 실패한 ORIGINAL 분석을 성공으로 덮어쓰지 마십시오.

중단 사유: 사전 등록한 회복 확인·회귀·기여 분석 완료 후 제출 패키지 검증. 패키지 검증 전에는 goal 완료로 표시하지 않습니다.
