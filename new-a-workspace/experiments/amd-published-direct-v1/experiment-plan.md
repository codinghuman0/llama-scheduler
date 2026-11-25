# 배포 통합본 AMD 직접 비교

대상은 `codinghuman0/llama-scheduler`의 `integration-v2` 브랜치 `fcb2e082f50beb4d4f91d1b303b3240663fa0f03`이다. AMD Ryzen 5 5500U에서 같은 모델로 다음 세 구성을 비교한다.

| 이름 | 실제 런타임 | 스케줄러 |
|---|---|---|
| B0 | 원본 `7a2db1a0cf38e5f4eb278a58c3903d295258d0ea`의 보존된 재빌드 | `SCHED_OTHER` |
| A | 이전에 직접 확인한 R 수치 경로와 E pressure, disposable pool | `SCHED_OTHER` |
| I | 배포 커밋의 OpenMP release, `integrated-runtime-research`, AMD 5/6, pressure, roles pool, state-v2 | `SCHED_OTHER` |

모든 arm은 동일한 물리 코어 6개, 생성/배치 구성 5/6, HTTP 8, AVX2 OpenMP, 원본 모델, slots 8, context 8192, batch 512/ubatch 256, FA 활성, CPU-only다. primary는 동시에 제출한 서로 다른 8요청의 실제 1,024 생성 토큰 / 전체 HTTP wall time이다. 모델 로딩과 요청 세트 워밍업은 제외한다. 각 방문은 새 서버에서 한 번 워밍업하고 한 번 측정한다. `cache_n`은 0이어야 한다.

기존 요청 세트는 smoke에만 쓴다. 확인에 사용할 새 입력 두 세트는 smoke 전에 원본 모델로 토큰화해 해시를 고정한다. 여덟 요청의 입력 길이 분포는 기존 fixture와 맞춘다. 조건은 ambient와 CPU10의 0.25 core 목표 부하이다. cpu25 소비가 실제로 0.22–0.28 core인지 같은 HTTP 시간 구간에서 검증한다. 모든 측정은 공유 잠금 아래 직렬로 실행한다.

확인은 두 캠페인이다. 캠페인마다 조건별 8블록, 각 블록에 B0/A/I 세 visit이 있으며 요청 세트별로 모든 두 arm의 상대 순서가 균형을 이룬다. 전체 96 visits에서 계획 순서와 두 조건을 그대로 따른다. 프로토콜, build, 실행 도구, 분석 코드, prompt는 timing 전에 동결한다. 중단 블록은 그대로 보존하고 다음 미시도 블록부터 재개한다. 기술적으로 완료된 모든 타이밍과 출력 동등성 기준을 통과한 표본을 구분한다.

주 비교는 I/B0이고 A/B0 및 I/A는 보조 비교다. 각 stage에서 같은 입력과 이력이 주어진 두 arm의 생성 토큰을 정확히 비교한다. 각 캠페인·조건에서 I/B0 유효 8블록, 평균 대조군 대비 증가 ≥5%, 층화 paired bootstrap 95% 하한 >0%, 빠른 쌍 ≥6/8이어야 일관된 향상으로 판정한다. 하한 ≥5%도 따로 표시한다. 조건을 합쳐 실패를 숨기지 않는다. cpu25 소비, CPU초 및 phase별 요청 timings는 보조 지표다.

`sched_ext` 검증은 커널에 실제로 로드된 선택 child에서 별도 수행하는 연구 범위다. 이 비교에서 배포 통합본의 userspace 전체 효과를 산출한다. 팀 통합 보고서의 OpenMP 서비스별 pilot과 native `m4`는 각기 별도 작업 부하다.
