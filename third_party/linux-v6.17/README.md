# Linux v6.17 `scx_simple` reference

This directory vendors the upstream BPF reference from Linux tag `v6.17`,
commit `e5f0a698b34ed76002dc5cff3804a61c80233a7a`:

`https://github.com/torvalds/linux/blob/v6.17/tools/sched_ext/scx_simple.bpf.c`

It is kept as an unmodified GPL-2.0 provenance artifact and is not compiled.
`src/llama_scx_simple.bpf.c` is the renamed implementation. It preserves the
reference's shared-DSQ weighted-vtime default and optional FIFO mode, while
adding `SCX_OPS_SWITCH_PARTIAL` for the project's safety requirement. The
reference's userspace source is also vendored. The project provides a
separate C/libbpf loader with the same `-f` and `-v` behavior.
