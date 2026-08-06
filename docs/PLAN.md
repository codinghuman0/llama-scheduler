# Baseline sched_ext milestone

The initial scheduler is a C/libbpf adaptation of Linux v6.17
`tools/sched_ext/scx_simple.bpf.c`, pinned in `third_party/linux-v6.17/`.
The recorded target is Ubuntu kernel `7.0.0-28-generic`; its BTF exports the
callbacks, kfuncs, and `SCX_OPS_SWITCH_PARTIAL` used by this project.

`src/llama_scx_simple.bpf.c` preserves scx_simple's shared dispatch queue:
weighted virtual-time scheduling by default and FIFO with `-f`. Its only
scheduling-policy difference is `SCX_OPS_SWITCH_PARTIAL`. Consequently, only
tasks that explicitly select `SCHED_EXT` are managed. `SCHED_NORMAL`,
`SCHED_BATCH`, and `SCHED_IDLE` tasks remain under Ubuntu fair scheduling.

`src/llama_scx_simple.c` is a foreground libbpf loader. It has no option to
move tasks or switch all tasks. It records kernel exit reason, message, and
dump data after link destruction triggers the exit callback. It opens the BPF object directly
because local bpftool 7.7 generates a skeleton requiring a newer libbpf than
the installed 1.3.0.

The non-privileged check is `make check`, which runs finite CPU-bound and
sleeping/waking workloads plus dry-run validation tests without changing any
scheduling policy. The manual `scripts/run_validation.sh` suite is blocked
until an operator has explicitly started the partial-switching loader.

No scheduler load, attachment, system configuration, kernel, bootloader, or
systemd change is part of this milestone. A future privileged checkpoint must
be manually approved and run by the user, and must verify that the invoking
shell, systemd, SSH daemon, and desktop tasks are not `SCHED_EXT`.
