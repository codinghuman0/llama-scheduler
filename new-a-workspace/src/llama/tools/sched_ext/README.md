# llama.cpp sched_ext research component

This subtree is an optional Linux sched_ext research component. The main
llama.cpp project remains MIT-licensed. Files derived from Linux
`sched_ext/scx_simple` and the scheduler component are GPL-2.0 and are
intentionally kept inside this separately licensed subtree.

## Licensing and provenance

The full scheduler GPLv2 text is in [LICENSE](LICENSE). Linux-derived files retain their GPL-2.0 SPDX and original author notices; project scheduler/control, validation and benchmark tooling retain their existing GPL-2.0 terms. See the repository [licensing and provenance notice](../../THIRD_PARTY_NOTICES.md) for the component inventory, upstream sources and publication checklist. The external benchmark model and runtime bundles are not distributed; inherited vocabulary-only GGUF test fixtures are distinct from model weights. The validated Base checkpoint remains documented in [LIGHTWEIGHT_BASE_V1_CHECKPOINT.md](LIGHTWEIGHT_BASE_V1_CHECKPOINT.md).

The privileged sched_ext loader will remain a separate executable from
`llama-server`. `llama-server` must remain runnable as a normal user and must
not link libbpf or privileged scheduler-loading functionality.

The normal llama.cpp build must not require:

- Linux sched_ext
- libbpf
- bpftool
- kernel headers
- kernel BTF
- root privileges

The active `llama_scx.bpf.c` is derived from Linux v6.17 `scx_simple`.
It keeps the weighted-vtime shared DSQ and default idle-CPU local insertion,
uses partial switching, and removes example statistics and FIFO mode.
The `validation/` directory contains the frozen golden instrumented oracle.
The validated implementation remains recoverable from:

- repository: https://github.com/codinghuman0/llama-scheduler
- local golden tag: `validation-scheduler-baseline-v1`
- exact commit: `ffc03c82738e31977cf402061422b0ef0148fe67`

The future integration sequence is:

```text
validated scheduler import
    -> one-repository golden validation
    -> minimal phase transport
    -> observer-effect removal
    -> lightweight neutral scheduler
    -> performance baseline
    -> scheduling policies
```

`provenance/linux-v6.17/` contains unmodified historical Linux source copies.
These files must not be edited as part of the project scheduler. Active
scheduler sources live directly under `tools/sched_ext/` and must not
modify the provenance copies in place.

Build only the active scheduler as a normal user:

```sh
make -C tools/sched_ext all
```

Generated BTF declarations, the BPF object, loader and reused selected-child
launcher stay in ignored `tools/sched_ext/build/`. The Makefile never loads
BPF, generates a skeleton, runs a workload or rebuilds llama.cpp. The loader
opens the BPF object directly with the installed libbpf.

The loader requires separate `--server-exe` and `--marker-elf` arguments,
plus `--phase-uid` and `--phase-register-socket`. For the current shared build,
the marker ELF is `build-lightweight-dev/bin/libllama-server-impl.so`, while
the executable is `build-lightweight-dev/bin/llama-server`. ELF file identities
are held separately and checked against the selected process. Registration
uses the existing abstract SOCK_SEQPACKET `REGISTER 1 PID` / `ACK 1 PID STATUS`
protocol. The unchanged launcher uses `--phase-register-socket`.

After validation, the loader initializes selected state, attaches one
PID-scoped entry uprobe to `llama_scx_phase_v1`, checks target liveness, and
then ACKs success. A pidfd tracks the selected process. SIGINT/SIGTERM are
handled through signalfd. A 1000 ms poll timeout checks only terminal scheduler
exit state; it reads no phase and prints no periodic output. Teardown signals
only the selected pidfd, waits up to 5 seconds for SIGTERM and then up to
5 seconds for SIGKILL, and detaches all links. Keep the launcher alive so it
can reap its child.

The GPL-side control ABI has three 32-bit fields: selected TGID, current phase
and exit kind. It occupies 12 bytes in global `.data`; upstream virtual time
stays separate in `.bss`. Only the marker handler uses phase during operation.
Scheduling callbacks never read phase. DECODE can remain stored while the
server is idle; phase is the last semantic transition, not an activity signal.

The active implementation is build/static-inspection only until its separate
runtime acceptance. It contains no phase, load, topology or worker policy.

The MIT llama-server side and GPL scheduler side will not share a GPL-only ABI
header. During the initial refactor, they will keep separately licensed,
matching declarations. Numeric and layout equivalence will be validated by
compile-time assertions and/or tests.
