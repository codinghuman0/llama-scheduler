# llama-scheduler

`llama-scheduler`는 Ubuntu의 `sched_ext` 환경에서 실험용 BPF 스케줄러를
안전하게 검증하기 위한 C/libbpf 프로젝트입니다. 초기 구현은 Linux v6.17의
`tools/sched_ext/scx_simple`을 기반으로 하며, 기록된 실행 환경인 Ubuntu
`7.0.0-28-generic`의 BTF/UAPI와 호환되도록 조정했습니다.

프로젝트의 목적은 **일반 데스크톱/서버 작업을 교체하지 않고**, 명시적으로
선택한 유한 테스트 작업만 `SCHED_EXT`에서 실행해 스케줄러의 기준선과 계측을
검증하는 것입니다. `llama.cpp` 통합은 의도적으로 포함하지 않았습니다.

## 왜 sched_ext인가

`sched_ext`는 BPF로 스케줄링 정책을 실험하면서도 커널의 안전 장치와 표준
스케줄러를 함께 사용할 수 있게 합니다. 이 저장소는
`SCX_OPS_SWITCH_PARTIAL`만 사용합니다. 따라서 `SCHED_NORMAL`,
`SCHED_BATCH`, `SCHED_IDLE`의 일반 Ubuntu 작업은 Linux fair scheduler에
계속 남고, `SCHED_EXT`를 명시적으로 요청한 fork 자식만 `llama_simple`의
관리 대상이 됩니다.

안전 모델의 핵심은 다음과 같습니다.

- 현재 셸, Codex, systemd, SSH, 데스크톱, 관련 없는 프로세스의 정책을 바꾸지
  않습니다.
- `build/bin/llama_scx_child`가 fork한 자식만 `sched_setattr(SCHED_EXT)`를
  요청합니다. 부모 launcher는 원래 정책을 유지합니다.
- 자동 빌드/테스트는 BPF를 attach하지 않으며, 실제 load/unload와 SCHED_EXT
  선택은 승인된 운영자가 수동으로 수행합니다.
- 모든 합성 workload는 유한하며, 검증 runner는 timeout과 자체 process-group
  정리를 사용합니다.

## 저장소 구성

| 경로 | 내용 |
| --- | --- |
| `src/llama_scx_simple.bpf.c` | `scx_simple` 기반 partial-switching BPF 스케줄러와 bounded 계측 |
| `src/llama_scx_simple.c` | C/libbpf foreground loader, JSON/text 계측 보고서 출력 |
| `src/llama_scx_child.c` | 선택된 한 자식만 SCHED_EXT로 전환하는 launcher |
| `include/` | 기록된 kernel UAPI와 BPF/userspace 공용 계측 구조체 |
| `tests/` | 유한 CPU/sleep-wake workload 및 비권한 단위 테스트 |
| `scripts/run_validation.sh` | 수동 load 후 실행하는 기준선 검증 suite |
| `docs/` | 환경, 상태, 선택 자식, 검증, 계측의 상세 절차 |
| `third_party/linux-v6.17/` | GPL-2.0 Linux v6.17 `scx_simple` provenance reference |
| `results/` | 의도적으로 보존한 수동 검증 요약/JSON Lines 증거 |

## 빌드 요구 사항

기록된 대상은 Ubuntu `7.0.0-28-generic`입니다. 해당 kernel의 headers/BTF와
다음 도구가 필요합니다.

- `build-essential`, `clang`, `llvm`, `bpftool`
- `libbpf-dev`, `libelf-dev`, `zlib1g-dev`
- 실행 중인 kernel과 일치하는 `linux-headers-$(uname -r)`
- `python3`, `taskset` (검증 스크립트)

의존성 설치, kernel 변경, scheduler load는 이 저장소의 자동 명령에 포함되지
않습니다.

```sh
make clean
make -j"$(nproc)"
make check
```

`make check`는 비권한이며 scheduler를 load/attach하지 않습니다.

## 수동 load / unload

아래는 운영자용 절차입니다. 명시적 승인 후에만 실행하고, 이 에이전트나 CI에서
실행하지 마십시오.

```sh
cat /sys/kernel/sched_ext/state             # disabled 확인
sudo ./build/bin/llama_scx_simple -v        # foreground load
cat /sys/kernel/sched_ext/state             # enabled 확인
cat /sys/kernel/sched_ext/root/ops          # llama_simple 확인
# loader terminal에서 Ctrl+C
cat /sys/kernel/sched_ext/state             # disabled 복귀 확인
```

계측을 함께 수집하려면 정확한 출력 디렉터리를 지정합니다. 같은 경로가 이미
있으면 loader는 덮어쓰지 않고 실패합니다.

```sh
mkdir -p results/instrumentation
run_dir="results/instrumentation/$(date -u +%Y%m%d-%H%M%S)"
test ! -e "$run_dir"
sudo ./build/bin/llama_scx_simple -v -o "$run_dir"
```

상세 절차는 [docs/INSTRUMENTATION.md](docs/INSTRUMENTATION.md)를 따르십시오.

## 선택 자식 실행

scheduler가 `enabled`인 상태에서만, 한 개의 유한 자식을 선택합니다.

```sh
sudo ./build/bin/llama_scx_child -- ./build/bin/cpu_burn --seconds 10
```

launcher는 자식 PID를 출력하고, 부모의 scheduling policy가 변하지 않았는지
확인하며, 자식의 exit status를 그대로 반환합니다. scheduler가 비활성이면
명확한 오류와 status `1`로 거부합니다. 더 자세한 `/proc` 확인은
[docs/MANUAL_SELECTED_CHILD.md](docs/MANUAL_SELECTED_CHILD.md)에 있습니다.

## 기준선 검증

loader를 운영자가 foreground로 시작한 뒤, 다음은 sudo 없이 실행합니다.

```sh
./scripts/run_validation.sh
```

결과는 `results/validation/YYYYMMDD-HHMMSS/`에 JSON Lines와 사람이 읽는
요약으로 기록됩니다. Milestone 6의 기록된 수동 결과는 **7/7 scenarios PASS**
입니다. 단일 CPU workload, under/over-subscription, affinity, mixed sleep/wake,
예상 exec 실패, 예상 timeout을 포함합니다. 근거는
`results/validation/20260806-132646/summary.txt` 및
[docs/VALIDATION.md](docs/VALIDATION.md)입니다.

## Milestone 7 계측

계측은 scheduling decision을 변경하지 않고 다음을 수집합니다.

- enqueue, direct-local DSQ insert, shared DSQ insert, 실제 dispatch callback,
  running/stopping callback 횟수
- tracked SCHED_EXT task의 runtime, CPU migration, bounded per-task record
- stopping CPU 기준 per-CPU runtime, queue wait, current/peak tracked task 수
- lookup/update/capacity/cleanup/completed-record/tracking-state failure 수
- scheduler exit kind, code/reason, kernel API가 제공하는 message

`queue_wait_ns`는 `enqueue` callback이 기록한 가장 최근 timestamp부터 다음
`running` callback까지입니다. 재-enqueue는 이전 timestamp를 덮어쓰며,
`select_cpu`에서 local DSQ로 직접 삽입된 activation은 enqueue callback을 거치지
않으므로 이 수치에 포함되지 않을 수 있습니다.

수동 계측 결과는 `results/instrumentation/YYYYMMDD-HHMMSS/` 아래의
`instrumentation.json` (schema version 1)과 `summary.txt`에 기록됩니다.
세부 map 용량, PID reuse, dropped statistics와 제한은
[docs/INSTRUMENTATION.md](docs/INSTRUMENTATION.md)에 있습니다.

## 알려진 제한

- 실제 scheduler load와 Milestone 7 계측 검증은 수동 checkpoint이며 아직 이
  자동 handoff에서 실행하지 않습니다.
- task 통계는 1,024개 bounded live map과 1,024개 completed map에 제한됩니다.
  용량 또는 lifecycle 문제가 발생하면 failure counter가 증가하고 일부 task
  record가 누락될 수 있습니다.
- 결과의 runtime/queue wait/migration은 callback 기반 관측값이며 모든 kernel
  scheduler event를 대체하지 않습니다.
- raw workload log와 새 계측 결과는 기본적으로 Git에 추가하지 않습니다.

## 다음 단계: llama.cpp handoff

`llama.cpp` 통합은 다음 프로젝트 단계와 담당 팀원의 범위입니다. 권장 순서는
다음과 같습니다.

1. Milestone 7 수동 계측 절차를 실행하여 기준선 결과와 7/7 validation parity를
   기록합니다.
2. llama.cpp workload를 **새로운 선택 자식**으로 추가하되, 먼저 유한/timeout
   경계를 유지하고 일반 시스템 작업은 partial switching 밖에 둡니다.
3. 기존 JSON Lines validation과 instrumentation report를 기준선과 비교한 뒤,
   phase-aware 정책은 별도 milestone으로 검토합니다.

## 라이선스 및 provenance

프로젝트 소스의 SPDX 표기는 유지됩니다. 루트 [LICENSE](LICENSE)는 GPL-2.0
전문입니다. `third_party/linux-v6.17/`의 upstream `scx_simple` reference는
Linux v6.17 tag/commit provenance와 GPL-2.0 상태를
[third_party/linux-v6.17/README.md](third_party/linux-v6.17/README.md)에
기록합니다. 이 저장소는 upstream 저자 정보를 새로 주장하지 않습니다.
