# 검증 환경과 적용 범위

두 최종 AMD portable 빌드의 source file 해시 목록과 sources.lock 해시가 일치한다. OpenMP build는 all markers, native build는 HINT/TRACE OFF와 state-v2를 선택했다. 같은 Qwen2 GGUF, CPU-only 및 동일 CPU 봉투로 검사했다.

| 환경·구성 | build | 실제 모델·설정 | kernel |
|---|---|---|---|
| AMD OpenMP, 기본 Linux, 역할별 pool + legacy E + state | PASS | fresh 두 8요청 fixture 및 lifecycle PASS, 동일 history B0/A equality | 해당 없음 |
| AMD OpenMP, 기본 Linux, 공유 pool + notification off | PASS | 8요청, R/Q4 phase 유지, smoke PASS | 해당 없음 |
| AMD OpenMP, 기본 Linux, adaptive + state | PASS | 5/6·8 task group·명시 threshold, model PASS | 해당 없음 |
| AMD OpenMP, scalar 또는 trace | PASS | singleton 및 각각 실제 선택된 transport, 동일 토큰 | 커널 attach 미실행 |
| AMD native, 기본 Linux, 역할별 pool + state-v2 | PASS | HINT OFF/TRACE OFF, lifecycle 및 OpenMP singleton equality | 해당 없음 |
| AMD native, 역할 mask/poll + fixed phase | PASS | 5/6 팀, 선택 envelope 및 strict CPU mask 관측, model smoke PASS | 조합 비허용 |
| AMD native, 역할별 `SCHED_BATCH` + park + state-v2 | PASS | 5개 Batch worker, Prefill futex 대기 3,444회, 8요청 exact, 풀 실패 회수와 graph abort 복구 PASS | Linux 경로 |
| AMD native, `m4` cap128 및 head64 | PASS | 두 checkpoint에서 전용 layer 호출 3,584회씩, 각각 warmup과 measured 5개 요청 exact | Linux 경로 |
| AMD OpenMP, serving + cap128 두 profile | PASS | pp/d1/d2/d4/m1/m3 12 visits, SSE 및 overlap PASS | 해당 없음 |
| AMD current BTF, selected-child FULL / Lite + state | 정적 PASS | observe, decode-handoff, locality-decode, locality-active의 C receiver/후보 gate 및 수동 준비 | KERNEL_NOT_RUN |
| Intel i5-1240P fixed6 / 4-8 | 공통 recipe 및 synthetic topology | MOCK_PASS, INTEL_NATIVE_PENDING | KERNEL_NOT_RUN |

동일 process에서 이전 요청의 slot history가 달라질 때 일부 생성 토큰이 달라지는 B0의 동작이 남아 있다. 같은 history의 B0/A/v2는 정확히 일치했다. 서로 다른 history의 동일성 및 모든 모델·ISA의 동등성은 이 검사의 범위 밖이다.

OpenMP에서는 native role priority, park와 head64를 거부한다. `SCHED_FIFO`와 barrier-hint receiver는 공통 선택지 범위 밖이다. Intel 실기와 선택 scheduler의 native 검증은 남아 있다. [기능 카드와 근거](feature-ledger.json)
