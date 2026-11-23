# Workspace consolidation

Status: COMPLETE. One standalone source/runtime/scheduler folder, with the model available at models/model.gguf without an external path dependency. Original source and model contents preserved.

Evidence: maintenance/compact-20261122/report.md and maintenance/self-contained-20261122/report.md. Historical evidence is archive/legacy.tar.xz; conservative compiler intermediates removed, retained content hashes verified. Internal model is a hardlink, not an extra data copy.

Next verification command: python3 -B tools/verify.py --archive
Runtime configuration: bash run.sh --describe

Research state: experiments/persistent-pool-port-v1/GOAL_STATE.md. Numerical baseline gate remains WAITING_NUMERICAL_BASELINE; no model inference or BPF attach ran during maintenance. No numerical runtime/source changes were made.
