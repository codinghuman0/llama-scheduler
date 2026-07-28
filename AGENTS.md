# Project Rules

## Safety

- Never modify the bootloader.
- Never install or boot a new kernel without explicit user approval.
- Never enable the custom scheduler at boot.
- Never modify systemd services.
- Never run commands that reboot, shut down, suspend, or kill the user session.
- Never load a sched_ext scheduler without explicit user approval.
- Never switch all ordinary system tasks to sched_ext.
- Use SCX_OPS_SWITCH_PARTIAL for every experimental scheduler.
- Never place the current shell, SSH daemon, systemd, or desktop processes
  under SCHED_EXT.
- Do not use sudo unless the user explicitly approves the exact command.
- Do not use --dangerously-bypass-approvals-and-sandbox.
- Do not suppress BPF verifier errors.
- Preserve scheduler exit dumps and verifier logs.

## Development Process

- Work one milestone at a time.
- Before changing code, inspect the current repository and relevant kernel
  headers.
- Use examples compatible with the running kernel.
- Do not assume sched_ext APIs are stable across kernel versions.
- Build after every meaningful change.
- Run only non-privileged tests automatically.
- Stop at every kernel-load checkpoint and provide the exact command for the
  user to execute manually.
- After each milestone, update docs/STATUS.md.
- Record commands, results, known issues, and the next milestone.
- Keep changes scoped.
- Commit only after build and non-privileged tests pass.

## Initial Scope

- C and libbpf implementation.
- Start from a kernel-compatible scx_simple example.
- Partial switching only.
- Synthetic test workload before llama.cpp.
- No phase-aware policy until the baseline scheduler works.
