# Native Ubuntu verification — 2026-08-19

## Scope

- host / kernel
- source revision
- 기존 VM checkpoint와 별개의 verification임
- llama.cpp는 scope 밖

## Native compatibility repairs

### Userspace UAPI
- KERNEL_RELEASE default → uname -r
- system exported UAPI 사용
- selected kernel sched.h에서 SCHED_EXT == 7 검증

### BPF spin-lock map BTF
- live_task_stats
- tracking_state
- typed key/value BTF declarations

## Static verification

- make clean
- make -j$(nproc)
- make check
- validation 14/14
- instrumentation 9/9
- kfunc BTF audit

## Runtime verification

- verifier/load PASS
- state enabled
- ops llama_simple
- selected child only policy 7
- shell/launcher remain policy 0
- Ctrl+C unload
- final state disabled

## Validation evidence

20260819-130515
→ inactive_scheduler 1/1 PASS

20260819-130748
→ active suite 7/7 PASS

## Instrumentation evidence

canonical local run:
results/instrumentation/native-ch-laptop-20260819-loadcheck-01

핵심 counter들

## Invariant validation

all PASS

## Known metric limitation

queue_wait_ns limitation

## Provenance

VM historical:
docs/environment.txt
results/validation/20260806-132646/

Native:
docs/environment.native...
results/validation/20260819-...
