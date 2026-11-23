# Frozen A: E worker choice and existing scheduler attribution

No new model/runtime/kernel optimizations. B0_L is the historical original rebuild under Linux. F6_L and A_L use the exact same validated A ELF/DSOs, with only `NEWA_DECODE_RESOURCE=fixed6` versus `pressure`. A_S adds the preserved partial `observe` SCHED_EXT scheduler to A_L. Persistent pool remains off. See protocol.json, cases.json, scheduler-selection.md and the final component-summary.md.

Existing two-campaign A/B0 performance evidence remains at `../a-b0-direct-confirmation-v1/`. This new goal has only one four-arm campaign. The old positive result does not establish independent E or scheduler effects.

Run as the ordinary account in this directory:

```bash
./reproduce.sh verify
./reproduce.sh recalculate --name attribution-v1
./reproduce.sh analyze --name attribution-v1
```

Raw numerical recalculation requires Python 3 and the review files, no model, runtime or root. Full `verify`/`analyze` also audit the existing workspace runtime and protected files. No build is needed or performed.

For a separately authorized independent reproduction in the unchanged current workspace:

```bash
sudo -v
./reproduce.sh admission --name independent-scheduler-admission-v1
./reproduce.sh smoke --name independent-linux-smoke-v1
./reproduce.sh full --name independent-attribution-v1
```

These commands require the preserved source/runtime/model paths and supported AMD host/kernel/BTF, and refuse reused result namespaces. They acquire the existing measurement lock and clean up only their own processes. Privilege is restricted to the existing loader and read-only BPF diagnostics. SCHED_EXT must be disabled before and after visits. New admission names update the current admission pointer while keeping raw previous runs. Do not rerun the current campaign to replace failures or increase significance. Reproduction beyond the requested single campaign is the next separate task.

The package omits model weights, runtime binaries and full builds. Identity manifests and protected-file hashes point to the live workspace. The review archive contains this experiment's raw results, copied small prior checkpoints, analysis and source excerpts. It includes local paths/process identities; it is a local review artifact, not a publication or upload.

Assisted by Codex: runner adaptations, raw analysis and reporting. No source/ELF changes to A, B0 or scheduler.
