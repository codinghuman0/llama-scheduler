# 세 저장소 2차 통합 개발 점검 보고

AMD Ryzen 5 5500U에서 기본 Linux로 R 수치 경로, phase별 resource profile, persistent pool, state-v2를 조합해 실제 모델을 실행했다. 기존 1차 통합은 A가 쓰는 수치 경로와 pre-R 기본 진입점이 달랐고 persistent pool과 state-v2가 별도 후보에 남아 있었다. 이제 소스 하나에서 새 바이너리와 DSO를 함께 만들며, 실행 전에 build 입력을 확인하고 실행 중 실제 로드 경로와 CPU 범위를 확인한다.

| 계층 | 1차 결과 | 이번 추가 또는 연결 |
|---|---|---|
| 수치 경로 | 동결 A는 R overlay를 적용한 DSO 사용 | 공통 소스에 R을 포함하고 OpenMP/native 호환의 Q4 계측과 Q6 빌드 조건을 수정했다. |
| Phase와 thread | semantic origin과 E의 AMD 5/6 route | norm/batch explicit 재사용, 유지된 E와 사람이 지정하는 adaptive 조건, 실제 CPUID로 고르는 AMD/Intel resource preset. |
| Pool | A는 disposable, P는 별도 검증 | donor owner와 해제 순서를 공통 runtime에 연결했다. disposable, 공유, 역할별을 고른다. native 역할별 affinity/poll/priority와 phase별 park를 실제 확인했고, 초기 자원 확보 실패와 일부 worker 실패의 정리를 추가했다. |
| 상태 전달 | scalar HINT가 CPU phase setter와 결합 | CPU bridge를 유지한 채 off, scalar, state-v2, trace를 선택한다. publisher의 active/idle와 receiver의 ABI·run/sequence 검증을 연결했다. |
| Scheduler와 topology | selected child, FULL, 기존 AMD CPU 범위 | donor의 CPUID, 가능한/허용된 CPU 교차와 guard, 비연속 CPU slot 매핑, FULL/Lite 공통 BPF. v2 상태를 쓰는 Decode handoff와 locality를 각각 선택할 수 있다. |
| Serving | 기존 8요청 atomic benchmark | 독립 SSE workload를 공통 build 검증 아래 실행한다. Mixed cap128과 native head64의 실제 겹침·커널 실행을 기록한다. |

팀원 runtime에서 가져온 것은 pool, v2 wire layout과 marker, serving harness, Mixed cap128/head64다. 이미 있던 semantic classifier·compute profile의 공통 계보는 중복 집계하지 않는다. scheduler 팀원의 topology, 동적 guard와 Lite instrumentation을 공통 scheduler build에 연결했다. 우리 보존 코드는 R/Q4/Q6, E의 pressure와 기존 wakeup/enqueue 후보에 사용했다. 이번 연결 코드는 CPU phase bridge 분리, owner lifecycle과 새 runtime identity, state-v2 수신기 및 run/collect adapter를 담당한다. 출처와 함수 단위 증거는 feature ledger에 있다.

AMD의 새 OpenMP 구성은 두 fresh 8요청 fixture에서 R/B0 oracle의 앞 16토큰과 일치했다. E와 역할별 pool 및 state-v2를 함께 켠 상태로 실제 요청을 처리했다. 단일 요청은 SSE 취소, 잘못된 grammar, 이후 요청 성공과 sleep/resume을 검사했다. 초기 native 조합에서도 Q4 Decode/Mixed와 Q6 호출 로그 및 state-v2 출력을 확인했다. 같은 서버 이력을 공유하지 않으면 일부 출력이 달라질 수 있다. 엄격한 비교에서 발견한 여섯 건을 원본 B0와 A에서도 재현했고, 요청 이력을 맞춘 전체 배열은 세 runtime에서 정확히 일치했다.

같은 OpenMP build에서 두 정책 구성을 pp/d1/d2/d4/m1/m3 각각 한 쌍씩 비교했다. 두 arm에서 cap128을 적용한 구성으로 실제 Mixed overlap도 기록했다. token 수와 시작·종료 시각에서 재계산한 pilot은 다음과 같다.

| workload | 보수 구성 tokens/s | 연구 구성 tokens/s | paired 차이 |
|---|---:|---:|---:|
| pp | 1.166 | 1.246 | +6.85% |
| d1 | 14.569 | 15.245 | +4.64% |
| d2 | 20.736 | 19.544 | −5.75% |
| d4 | 23.132 | 23.297 | +0.72% |
| m1 | 3.844 | 3.873 | +0.78% |
| m3 | 8.114 | 8.199 | +1.04% |

이 값은 한 쌍의 관측이다. CPU 시간, TTFT, token-gap, stall은 원시 SSE 결과에 요청별로 있고, pool이나 scheduler의 단독 효과로 추정하지 않는다. 기존 P의 AMD ambient 회귀와 이번 d2 관측에도 persistent pool, adaptive, Lite를 연구 구성으로 남긴다. 각각 graph의 반복 설정 비용, 외부 CPU 경쟁, 진단 callback 비용을 줄일 가설을 검증할 수 있다.

Native에서 `m4`를 두 source checkpoint에서 기능 확인했다. 각각 head64 커널의 layer 호출이 3,584회였고, 워밍업·측정 합계 1,040개 생성 토큰이 cap128 대조군과 정확히 일치했다. 두 checkpoint의 측정 방문은 71.816→67.267초와 71.851→69.830초였다. 서로 다른 source checkpoint의 단일 pair이므로 성능 판정은 `INCONCLUSIVE`다. `SCHED_BATCH`, phase별 park 및 풀 실패 복구의 정체와 검증 범위는 [AMD 재현 절차](amd-local-validation.md)에 기록했다.

현재 남은 실기는 Intel과 실제 커널 admission이다. FULL/Lite의 각 배치 전략은 헤더와 BTF가 고정된 공통 방법으로 빌드한다. v2 receiver 단위검사와 수동 checkpoint는 privileged attach와 별개다. 실제 verifier 결과, 선택 PID별 수신, 배치 결정·mask와 커널 detach는 운영자가 로더를 실행한 뒤 판정한다. 이 상태를 `KERNEL_NOT_RUN`과 `INTEL_NATIVE_PENDING`으로 기록한다. [Intel 및 커널 실행 절차](INTEL_HANDOFF.md)
