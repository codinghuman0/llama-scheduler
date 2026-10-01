# Codex prompt: one phase-policy experiment

Use the immutable `m11-semantic-phase-baseline-v1` tag as the starting point.
Work only on a separate `experiment/<name>` branch; do not commit, retag, or
push unless I explicitly ask.

Before changing code:

1. inspect the current Git state and preserve all user changes;
2. read `README.md`, `docs/EXPERIMENT_GUIDE.md`, `docs/LLAMA_PHASE.md`, the
   scheduler implementation, and relevant tests;
3. confirm the semantic fork still uses the revision in
   `config/versions.env`; and
4. identify the unchanged selected-child and `SCX_OPS_SWITCH_PARTIAL` safety
   boundaries.

Choose exactly one scheduling dimension for this experiment. State the
hypothesis, mechanism, neutral counter-evidence, risks, and acceptance criteria
before implementation. Do not combine it with idle-core selection, SMT
avoidance, migration suppression, phase-separated DSQs, phase-dependent
slices, or load-aware selection unless that is the single selected dimension.

Preserve the semantic UNKNOWN/PREFILL/DECODE/MIXED input and PID-specific
uprobe path. Preserve normal-user launcher/server ownership and ensure only the
selected server TGID uses `SCHED_EXT`. Add neutral diagnostic evidence and
focused unprivileged tests. Do not claim performance improvement from a single
run.

After implementation, report:

- files changed and why;
- build and unprivileged test results;
- baseline validation status;
- exact manual privileged commands still required;
- CPU, kernel, model, baseline tag, workload, co-load, run count, and metrics
  needed for evaluation; and
- any result that remains untested.

Keep all policy changes isolated on the experiment branch.
