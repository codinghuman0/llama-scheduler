# 통합 경로

```mermaid
flowchart TD
  origin["서버 token origin과 제출 view"] --> phase["Semantic phase"]
  phase --> profile["Fixed / legacy E / adaptive profile"]
  profile --> graph["llama_decode_with_options / graph"]
  graph --> pool["Disposable / 공유 / 역할별 persistent"]
  pool --> cpu["OpenMP 또는 native CPU workers"]
  phase --> bridge["CPU phase setter"]
  bridge --> route["R Prefill reference, eligible Q4·Q6"]
  phase --> transport["off / scalar / state-v2 / trace"]
  transport --> rx["선택 PID의 v2 receiver"]
  rx --> observe["받은 phase, active/idle, run, sequence"]
  rx --> opt["선택한 Decode handoff 또는 이전 CPU 선호"]
  topology["CPUID + sysfs + 허용 CPU"] --> profile
  topology --> sched["선택 child, idle tiers, local/shared DSQ"]
  opt --> sched
  sched --> stats["FULL 또는 Lite diagnostics"]
  model["build manifest와 GGUF identity"] --> graph
  workloads["Atomic 8 또는 독립 SSE workloads"] --> origin
```

CPU phase setter는 server marker와 독립적으로 동작한다. 동일 phase라도 새 lifecycle에서 첫 작업은 다시 전송될 수 있다. State-v2는 TCP 요청의 model 계산시간을 직접 나타내는 타이머가 아니라 단일 CPU decoder의 TGID 단위 상태다. ACTIVE Unknown과 IDLE은 active 필드로 구분하고 동일 상태를 중복 발행하지 않는다. Sync는 donor가 요구한 제출 전후 완료 의미를 유지한다. 마지막 요청 종료, 예외, sleep, context 해제 시 idle을 보낸다.

수신기는 등록된 TGID의 main publisher로 제한한다. PID별 uprobe 링크는 런처의 소켓 ACK와 분리된 증거다. ABI/정확한 run ID/sequence/TID를 확인하고 잘못된 이벤트가 들어오면 session을 무효화한다. PID 종료는 pidfd로 관측하며 detachment 후 receiver 상태를 초기화한다. 재연결과 rewind는 지원 범위 밖이다.

FULL/Lite의 기본 `observe`는 tiered idle 선택과 shared weighted-vtime을 사용한다. `decode-handoff`는 적격 Decode의 enqueue에서 첫 tier의 허용 idle CPU와 kick을 선택한다. `locality-decode`는 적격 Decode의 `select_cpu`에서 이전 CPU가 첫 tier, 허용, online, idle이면 우선한다. `locality-active`는 동일한 검사를 Prefill·Decode·Mixed에 적용하는 비교용 정책이다. 모든 모드는 이동 금지 상태에서 후보를 건너뛰고 일반 경로로 복귀한다. 유효 상태가 없거나 selected TGID가 다르면 phase-dependent 분기는 실행하지 않는다. BPF 빌드와 모델 없는 검사를 실제 커널 검증과 별도로 기록한다.

Pool은 각 awake interval에서 생성한다. 같은 worker/mask/poll/priority 설정이면 공유하며, 역할별 설정이 다르면 owner가 두 pool을 보유한다. 명시적 공유 설정은 같은 mask/poll/priority에서 max worker capacity를 사용한다. 할당이나 worker 생성 실패 시 해당 단계까지 소유한 자원만 정리한다. 정상 해제는 synchronize, context detach, context/backend 해제, pool free 순서다. OpenMP는 GGML pool state를 재사용하고 OS worker와 barrier는 OpenMP 런타임이 관리한다. Native의 역할별 mask, polling, `SCHED_BATCH` 및 futex park는 일반 Linux 경로에 제공한다. 호출 스레드는 graph 종료 시 원래 정책을 복원한다.
