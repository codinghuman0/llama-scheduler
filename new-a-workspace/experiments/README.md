# 실험 자료

| 폴더 | 용도 |
|---|---|
| `team-integration-v2` | 런타임 구성, 소스 출처, Intel/AMD 실행 안내 |
| `amd-published-direct-v1` | 원본 B0·이전 A·통합 런타임의 AMD 비교 결과와 집계 |
| `amd-prefill-placement-ac-v1` | 동일 런타임의 Linux·neutral·prefill-pcore AMD 실측, 다른 장비의 `placement` 측정·분석 도구 |
| 나머지 이전 캠페인 | 공개 비교 요약, 입력 fixture, 부하 생성기, R 커널 출처 등 현재 코드가 참조하는 파일 |

이전 일곱 캠페인의 전체 소스·봉인된 프로토콜·원시 기록은 커밋 `25ab433140eafc6cbb3b259b017c2a9252b37900`에서 열 수 있습니다. 현행 실행에 필요한 파일은 배포 브랜치에 남겼습니다. 팀원이 실험을 돌리면 원시 응답과 로그는 각 장비의 `state/`에 생성됩니다. 모델과 생성된 바이너리도 장비별로 관리합니다. [보존된 전체 캠페인 트리](https://github.com/codinghuman0/llama-scheduler/tree/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments)
