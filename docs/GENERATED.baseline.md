# Generated build artifacts

Generated files are intentionally confined to ignored `build/` and are
recreated by `make all`.

- `build/include/vmlinux.h` — C type and enum declarations emitted from the
  running kernel's `/sys/kernel/btf/vmlinux` by bpftool. It must never be
  committed because it is specific to the running kernel BTF.
- `build/llama_scx_simple.bpf.o` — Clang's BPF ELF object compiled from
  `src/llama_scx_simple.bpf.c`; this is the object the loader opens.
- `build/bin/llama_scx_simple` — userspace C/libbpf loader linked from
  `src/llama_scx_simple.c`.
- `build/bin/cpu_burn` — bounded synthetic CPU workload linked from
  `tests/cpu_burn.c`.

No skeleton header is generated. The installed bpftool 7.7 emits skeleton code
for a newer libbpf ABI than the installed libbpf 1.3.0, so the loader uses the
stable direct object APIs available in 1.3.0.
