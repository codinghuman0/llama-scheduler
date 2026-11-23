# Intel handoff: local portability evidence

This directory records the pre-push compatibility check, not an Intel performance
campaign. The actual host is AMD Ryzen 5 5500U. The target is Intel i5-1240P / Ubuntu.
Intel hardware execution and kernel scheduler loading are **NOT_RUN**.

- `verification.json`: final check status and measured policy/cleanup observations.
- `smoke/`: all 15 visits and raw HTTP, policy, CPU/load, DSO, and cleanup evidence.
- `build/`: exact input/source hashes, configure commands, compile commands and logs
  for both new AVX2 builds. No compiled binary or model is included.
- `failed-ui-build/`: first build failure (missing UI alias header), fixed in recipe 2.
  Generated source/build copies from that failed attempt were removed; logs retained.
- `unit-tests.log`, `root-make-check.log`: nonprivileged tests.
- `preservation.json`: original model and all preserved best A runtime hashes checked.

The source runtime is unchanged. The Intel build recipe copies the preserved R
Q4 policy into a staging tree and uses the same frozen, disabled UI in B0/A.
These binaries are freshly rebuilt artifacts, not the frozen AMD binary identity.
The `smoke` outputs use 16 tokens/request and do not establish any performance gain.
The longer `pilot` path is provided for the teammate, not claimed as a local full run.

Reproduction (from `new-a-workspace/`):

```bash
python3 -B tools/test_intel_experiment.py
bash scripts/intel_experiment.sh check
bash scripts/intel_experiment.sh smoke --model /absolute/path/to/model.gguf
```

On the original AMD host, the same smoke command included `--allow-non-intel` and
`--baseline-repo /home/codinghuman/projects/llama.cpp`. The latter only avoids the
pinned GitHub source fetch; it does not change B0's commit. No sudo was used.
For the actual Intel setup, follow `../../docs/INTEL_EXPERIMENT.ko.md`.
