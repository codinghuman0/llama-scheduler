# Status

## Milestone: sched_ext ABI compatibility repair

Status: built and ready for one further user-run manual load attempt. This
repair did not load, attach, or otherwise change sched_ext. The final read-only
state is `disabled` and `/sys/kernel/sched_ext/enable_seq` is `0`.

### Root cause and target

- Recorded running kernel: `7.0.0-28-generic` (`docs/environment.txt`).
- First-load evidence: `results/manual/first-load.log` reports incompatible
  extern kfunc `scx_bpf_dsq_insert` BTF prototypes.
- Failing object declaration: `bool scx_bpf_dsq_insert(struct task_struct *,
  u64, u64, u64)`.
- Running-kernel BTF declaration: `void scx_bpf_dsq_insert(struct task_struct *,
  u64, u64, u64)`.
- The incompatible return type is the root cause; the argument list was
  already correct. The bool-returning form is the newer `___v2` API, not the
  kfunc exposed under `scx_bpf_dsq_insert` by this kernel.

### Compatibility change

- Replaced the v7.0 reference with exact Linux v6.17 `scx_simple` BPF and
  userspace sources under `third_party/linux-v6.17/`, tag object
  `6063257da111c7639d020c5f15bfb37fb839d8b6`, peeled commit
  `e5f0a698b34ed76002dc5cff3804a61c80233a7a`.
- SHA-256: `scx_simple.bpf.c`
  `f8b2d3ab08a326b09e3e7c8a6eeea43991a5b5265ff9bfb4444bf459e36e3f59`;
  `scx_simple.c`
  `f9a1c7a648575d4415377f7bba668c9064e89519b5b0ec05fd45c8edcc89e59f`.
- In `src/llama_scx_simple.bpf.c`, changed only DSQ insertion ABI use:
  `scx_bpf_dsq_insert()` now has the matching void return type and weighted
  vtime enqueue calls the v6.17 `void scx_bpf_dsq_insert_vtime(p, dsq, slice,
  vtime, flags)` kfunc instead of the newer two-argument wrapper.
- The shared DSQ, FIFO option, weighted-vtime calculation, dispatch ordering,
  callbacks, and `SCX_OPS_SWITCH_PARTIAL` are unchanged. No phase-aware logic
  or scheduler queues were added.
- Also updated `docs/PLAN.md` and the vendored-reference README provenance.

### BTF verification

The rebuilt object's five sched_ext externs match the live BTF by return type
and parameter count/type:

```text
scx_bpf_select_cpu_dfl:  s32 (task_struct *, s32, u64, bool *)
scx_bpf_dsq_insert:      void (task_struct *, u64, u64, u64)
scx_bpf_dsq_insert_vtime:void (task_struct *, u64, u64, u64, u64)
scx_bpf_dsq_move_to_local: bool (u64)
scx_bpf_create_dsq:      s32 (u64, s32)
```

The object and live BTF both expose `struct sched_ext_ops` as 448 bytes with
42 fields. The project uses only matching `select_cpu`, `enqueue`, `dispatch`,
`running`, `stopping`, `enable`, `init`, and `exit` callbacks. The live BTF
also confirms `SCX_OPS_SWITCH_PARTIAL = 8`.

### Build and checks

Commands run without sudo:

```text
make clean
make -j"$(nproc)"
make check
```

Results: all targets built successfully; `make check` completed the bounded
CPU workload under original policy `0` (`SCHED_NORMAL`). `git diff --check`
also passed. No verifier output exists because loading is deliberately outside
this milestone.

### Next manual checkpoint

After explicit approval, the user may run this exact foreground load command:

```text
sudo ./build/bin/llama_scx_simple -v
```

This command was not run by the agent. Before it is run, keep the current
shell, SSH daemon, systemd, and desktop tasks out of `SCHED_EXT`; do not enable
switch-all behavior. Preserve the loader's libbpf output and any scheduler exit
dump for the next status update.
