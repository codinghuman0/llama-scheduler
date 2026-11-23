# Frozen A component replication

This directory owns all outputs of exactly one fresh four-arm campaign. The original `../a-component-scheduler-attribution-v1` is read-only provenance. Do not run the original runner/analyzer/finalizer with a new `--name`: those commands overwrite its summary, ledger and admission pointers.

Runtime A(E-R), B0 rebuild, model, ELF/DSOs, arithmetic kernels, E policy and observe/FULL scheduler are unchanged. B0_L/F6_L/A_L/A_S, requests and the original Latin order are byte-identical inputs. New protocol changes only isolate the run, prohibit the old Linux fallback, require fresh admission, and strengthen incomplete-data rejection. See harness.patch and protocol-diff.json. Mutable harness files are independent copies, never hardlinks to the original.

The new experiment has 2 scheduler admission visits, 6 Linux smoke visits, and exactly 64 measured fresh-server visits. Every visit uses one excluded warmup cohort and one check/measured cohort: atomic prompt-array /completion, eight distinct requests, 128 tokens/request. CPU25 means the fixed CPU10 0.25-core interference generator, not 25 percent of the whole machine or a cgroup quota.

## Model-free review

From this directory, these commands need Python 3 and the review files, no model/runtime/root:

```bash
./reproduce.sh recalculate
./reproduce.sh recalculate-original
```

The strict recalculator requires all 64 planned visits, 128 raw cohorts and 10 contrasts. Missing visits return nonzero INCOMPLETE_INVALID. Its output on complete original data is exactly equal to the old arithmetic implementation. A removed-visit negative test is preserved in evidence/recalculation-completeness-test.json.

## Workspace verification and registered execution

The following commands use the preserved current workspace and exact supported AMD/kernel/BTF. Run as the ordinary account. No builds or new scheduler policies are performed.

```bash
./reproduce.sh verify
sudo -v
./reproduce.sh admission
./reproduce.sh smoke
./reproduce.sh full
./reproduce.sh analyze
```

These target only this directory and fixed registered names. Existing result namespaces are refused. After completion they cannot start another campaign or replace an invalid visit. These are the recorded reproduction commands, not permission to add a third component campaign. Any future new execution must be separately registered in another isolated sibling directory with fresh protection/admission; this goal stops at the requested submission reference.

The existing measurement lock, ordinary-user inference, selected-child root loader, read-only BPF diagnostics, identity-specific cleanup, FULL guard, fixed CPU mask, thermal/memory/disk gates and watchdog remain. Root credentials are neither saved nor bypassed. S admission failure is BLOCKED, not permission for a three-arm substitute. Runtime timeout/error stops the registered plan; failures and all NOT_RUN entries remain.

## Reports and provenance

- replication-summary.md/json: only the new campaign.
- campaign-comparison.md/json: original and new component campaigns separately, with the two earlier runtime-only A/B0 campaigns as reference. No pooled CI.
- claim-evidence-matrix.md: claim scope and untested properties.
- frozen-release-map.json: A_L default-performance role and A_S scoped-evaluation role, exact source/ELF/model identities and argv/env. No old runtime/default path/tag is overwritten.
- reference-original/: essential copies of original raw evidence for portable numerical review. Full original archive SHA256 is 38e174805e0d59abb24b30d31e5c93bdbac09a099798a2b20feb587cf7c2af4f; this is not a model/runtime hash.
- review ZIP/manifest/SHA and package-validation.json: CRC, membership, all member hashes and extracted model-free recalculation of both campaigns.

These are temporally separated runs on one AMD machine with historical fixtures, not external-team/device replication or general workload validation. Observe records phase but has no phase-dependent placement. CI containing zero means inconclusive, not equivalence. OpenMP team-size sets are not continuous per-graph observations. CPU seconds is not energy; no new full-logits or TTFT/p95-token-latency campaign. Baseline variation remains CAUSE_UNDETERMINED without a causal experiment.

The package is a local submission/review reference, not production-ready certification. It includes local paths/process identities but excludes model weights, runtime copies and full build trees. Nothing is uploaded or pushed. Codex assisted the isolated harness, audits and reports.
