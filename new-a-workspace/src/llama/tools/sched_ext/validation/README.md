# Golden sched_ext validation implementation

This directory contains the imported GOLDEN VALIDATION implementation from [llama-scheduler](https://github.com/codinghuman0/llama-scheduler).

- Golden local tag: `validation-scheduler-baseline-v1`
- Exact source commit: `ffc03c82738e31977cf402061422b0ef0148fe67`

This implementation intentionally contains heavy diagnostic and validation instrumentation. It is not the final performance scheduler and must not be used as the source for performance claims.

Its purpose is to provide:

- a behavioral reference
- semantic phase validation
- a selected-child isolation reference
- a regression oracle during the lightweight rewrite

Source implementation files should remain byte-identical to the golden version whenever possible. Build-file differences are permitted only when relocation or path handling requires them.

Run `make` from this directory to build the BPF object, userspace loader, selected-child launcher, and bounded test workloads under `build/`. The golden build opens the BPF object directly and intentionally does not generate a BPF skeleton header.

The build process does not load or attach the scheduler. Loading the scheduler remains a separate privileged operation and is not part of validation builds.
