# Generated build artifacts

Generated files are confined to ignored `build/` and recreated by `make all`.

- `build/include/vmlinux.h` — C declarations emitted from the running kernel
  BTF; never commit it.
- `build/llama_scx_simple.bpf.o` — BPF ELF compiled from the scheduler source.
- `build/bin/llama_scx_simple` — foreground scheduler loader.
- `build/bin/llama_scx_child` — selected-child launcher; it is not a loader
  and cannot attach a scheduler.
- `build/bin/cpu_burn` — finite CPU-bound workload that does not change its
  own scheduling policy.
- `build/bin/sleep_wake` — finite sleeping/waking workload that does not change
  its own scheduling policy.
- `results/instrumentation/YYYYMMDD-HHMMSS/instrumentation.json` and `summary.txt`
  — manual-run bounded instrumentation reports; never overwritten.

`include/llama_sched_uapi.h`, `tests/test_scx_child.sh`, `scripts/`, and the files in
`docs/` are tracked source/documentation, not generated output.
