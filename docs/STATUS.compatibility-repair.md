# Status

## Milestone: sched_ext compatibility-repair baseline

Status: complete. The baseline has a clean non-privileged rebuild, a passing
source-level ABI regression guard, and a successful manually verified load and
unload. No scheduler was loaded or attached during this documentation pass.

### Target and root cause

- Running kernel: `7.0.0-28-generic`, recorded in `docs/environment.txt`.
- The initial manual attempt failed because the BPF object declared
  `bool scx_bpf_dsq_insert(struct task_struct *, u64, u64, u64)`, while this
  kernel's sched_ext BTF exposes `void scx_bpf_dsq_insert(struct task_struct *,
  u64, u64, u64)`. The argument list matched; the return type did not.
- The compatible reference/API basis is Linux v6.17 `scx_simple`, tag object
  `6063257da111c7639d020c5f15bfb37fb839d8b6`, peeled commit
  `e5f0a698b34ed76002dc5cff3804a61c80233a7a`, vendored in
  `third_party/linux-v6.17/`.

### Implemented compatibility and policy guarantees

- `src/llama_scx_simple.bpf.c` uses the matching void-returning
  `scx_bpf_dsq_insert()` and v6.17 five-argument
  `scx_bpf_dsq_insert_vtime()` kfuncs. The object BTF and live BTF agree on
  all used sched_ext kfuncs: `select_cpu_dfl`, `dsq_insert`,
  `dsq_insert_vtime`, `dsq_move_to_local`, and `create_dsq`.
- The used `sched_ext_ops` callbacks (`select_cpu`, `enqueue`, `dispatch`,
  `running`, `stopping`, `enable`, `init`, and `exit`) match the live
  448-byte/42-field ops structure.
- `SCX_OPS_SWITCH_PARTIAL` remains in `llama_simple_ops`; live BTF confirms
  its value is `8`.
- Scheduling policy was not changed by this repair: the shared DSQ, weighted
  virtual-time default, FIFO option, and dispatch order are unchanged. No
  phase-aware logic or queues were added. With partial switching, ordinary
  `SCHED_NORMAL`, `SCHED_BATCH`, and `SCHED_IDLE` tasks remain under the Linux
  fair scheduler; only explicit `SCHED_EXT` opt-ins are managed.

### Source-level regression check

- `Makefile` adds `check-scx-api`, included in `make check`.
- It fails if `scx_bpf_dsq_insert` is declared with `bool` instead of `void`,
  or if the newer `__scx_bpf_dsq_insert_vtime` wrapper reappears.
- A temporary negative test changing only that declaration to `bool` was
  confirmed to fail the guard; repository sources were not changed by the
  test.

### Successful manual verification

Primary evidence: `results/manual/baseline-load-success.txt` and
`results/manual/second-load.log`.

- At `2026-07-29T04:33:38+09:00`, the rebuilt BPF object loaded successfully
  on `7.0.0-28-generic`.
- `/sys/kernel/sched_ext/state` was observed as `enabled` and the active
  scheduler name was `llama_simple`.
- The userspace loader emitted normal statistics while running. Ctrl+C stopped
  it cleanly, and the final sched_ext state was `disabled`.

### Final non-privileged verification

Commands run without sudo:

```text
make clean
make -j"$(nproc)"
make check
```

Results: all targets built successfully; the source-level ABI regression check
passed; the bounded synthetic workload completed under original policy `0`
(`SCHED_NORMAL`). The manual verification is recorded evidence, not an action
performed during this pass.
