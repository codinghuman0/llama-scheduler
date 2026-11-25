#!/usr/bin/env python3
"""Preview this workspace's Git payload without staging, deleting or uploading."""
import argparse
import collections
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(argv):
    return subprocess.run(argv, cwd=ROOT, check=True, capture_output=True).stdout


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def audit():
    # A disposable index makes the preview work even before git init. Ignore
    # global excludes so that another machine gets the same workspace policy.
    with tempfile.TemporaryDirectory(prefix='newa-git-preview-') as temp:
        gitdir = Path(temp) / 'index.git'
        run(['git', 'init', '--bare', '--quiet', str(gitdir)])
        git = ['git', '-c', 'core.excludesFile=/dev/null',
               '--git-dir=' + str(gitdir), '--work-tree=' + str(ROOT)]
        selected = [os.fsdecode(p) for p in run(
            git + ['ls-files', '--others', '--exclude-standard', '-z']).split(b'\0') if p]
        ignored = [os.fsdecode(p) for p in run(
            git + ['ls-files', '--others', '--ignored', '--exclude-standard', '-z']).split(b'\0') if p]

    files = []
    failures = []
    secret_findings = []
    credential_patterns = [
        rb'\bgh[pousr]_[A-Za-z0-9]{36,255}\b',
        rb'\bgithub_pat_[A-Za-z0-9_]{60,255}\b',
        rb'\bAKIA[A-Z0-9]{16}\b',
        rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
    ]
    for rel in sorted(selected):
        p = ROOT / rel
        if p.is_symlink() or not p.is_file():
            failures.append({'path': rel, 'reason': 'Review symlink or nested repository before upload'})
            continue
        size = p.stat().st_size
        with p.open('rb') as f:
            magic = f.read(8)
        if magic[:4] == b'\x7fELF' or magic[:8] == b'!<arch>\n':
            failures.append({'path': rel, 'reason': 'Compiled binary escaped .gitignore'})
        if size >= 50 * 1024 * 1024:
            failures.append({'path': rel, 'reason': 'Exceeds this preview policy: 50 MiB per file'})
        if p.suffix.lower() in {'.gguf', '.safetensors', '.zip', '.xz'}:
            failures.append({'path': rel, 'reason': 'Weight/archive escaped .gitignore'})
        # High-confidence candidate patterns only; show locations, never values.
        if size <= 20 * 1024 * 1024 and b'\0' not in magic:
            data = p.read_bytes()
            for pattern in credential_patterns:
                for match in re.finditer(pattern, data):
                    secret_findings.append({'path': rel, 'line': data[:match.start()].count(b'\n') + 1,
                                            'reason': 'Credential-shaped text needs review; may be a fixture'})
        files.append({'path': rel, 'bytes': size, 'sha256': digest(p)})

    required = [
        '.gitignore', 'GITHUB_BACKUP.md', 'build.sh', 'run.sh',
        'src/llama/LICENSE', 'src/llama/tools/ui/frozen-ui.cpp',
        'src/llama/tools/server/newa-prefill-pressure.h',
        'src/llama/ggml/src/ggml-cpu/newa-q4-decode-exact.h',
        'scheduler/handoff.bpf.c', 'scheduler/loader.c', 'scheduler/include/vmlinux.h',
        'experiments/r-pool-validation-v1/candidates/R/overlay/ggml/src/ggml-cpu/newa-q4-policy.h',
        'experiments/r-pool-validation-v1/candidates/A/identity.json',
        'experiments/a-component-scheduler-attribution-v1/component-summary.json',
        'experiments/a-component-scheduler-replication-v1/replication-summary.json',
        'experiments/final-team-integration-audit-v1/code/recalculate_packaged.py',
        'experiments/final-team-integration-audit-v1/evidence/performance-blocks.json',
        'experiments/final-team-integration-audit-v1/evidence/performance-recalculation.json',
        'scripts/intel_experiment.sh', 'scripts/integration_v2.sh', 'scripts/intel-integration-v2-smoke.sh',
        'scripts/experiment-common.sh', 'scripts/prefill-pcore-smoke.sh', 'tools/cli_ko.py', 'tools/intel_experiment.py',
        'experiments/a-component-scheduler-replication-v1/fixtures.json',
        'experiments/a-component-scheduler-replication-v1/code/contention.py',
        'experiments/a-component-scheduler-replication-v1/code/load.py',
        'experiments/amd-prefill-placement-ac-v1/measure.py', 'experiments/amd-prefill-placement-ac-v1/analyze.py',
        'experiments/amd-prefill-placement-ac-v1/results.json', 'experiments/amd-published-direct-v1/final-analysis.json',
        'src/llama/tools/ui/ui.h',
        'tools/intel_policy_evidence.py', 'tools/test_intel_experiment.py',
        'docs/INTEL_EXPERIMENT.ko.md', 'docs/INTEL_CODEX_HANDOFF.ko.md',
        'docs/INTEL_COMPATIBILITY_CHECK.ko.md',
    ]
    selected_set = set(selected)
    failures.extend({'path': p, 'reason': 'Required source/evidence ignored'} for p in required if p not in selected_set)
    # Existing tracked files are unaffected by .gitignore; report that case.
    tracked_ignored = []
    probe = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', '--show-toplevel'], capture_output=True, text=True)
    own_repo = probe.returncode == 0 and Path(probe.stdout.strip()).resolve() == ROOT
    if probe.returncode == 0:
        tracked_ignored = [os.fsdecode(p) for p in run(
            ['git', '-C', str(ROOT), 'ls-files', '-ci', '--exclude-standard', '-z', '--', '.']).split(b'\0') if p]
        failures.extend({'path': p, 'reason': 'Already tracked: ignore alone cannot remove it'} for p in tracked_ignored)

    groups = collections.defaultdict(lambda: {'files': 0, 'bytes': 0})
    ignored_bytes = 0
    for rel in ignored:
        p = ROOT / rel
        if p.is_file():
            size = p.stat().st_size
            ignored_bytes += size
            groups[rel.split('/')[0]]['files'] += 1
            groups[rel.split('/')[0]]['bytes'] += size
    unique_content = {x['sha256']: x['bytes'] for x in files}
    return {
        'status': 'PASS' if not failures and not secret_findings else 'REVIEW_REQUIRED',
        'root': str(ROOT), 'own_git_repository': own_repo,
        'measurement': 'Uncompressed file bytes; hardlink paths counted separately. Not disk space freed or network transfer size.',
        'included_files': len(files), 'included_bytes': sum(x['bytes'] for x in files),
        'unique_content_files': len(unique_content), 'unique_content_bytes': sum(unique_content.values()),
        'ignored_files': len(ignored), 'ignored_bytes': ignored_bytes,
        'ignored_by_top_directory': dict(groups),
        'largest_included': sorted(files, key=lambda x: x['bytes'], reverse=True)[:15],
        'required_paths_verified': required, 'tracked_ignored': tracked_ignored,
        'failures': failures, 'credential_pattern_findings': secret_findings,
        'scan_scope': 'Common token/private-key patterns in selected files <=20 MiB; not a complete secret/privacy audit.',
        'files': files,
        'mutations': 'None to repository/index/existing data. Only temporary Git metadata and optional JSON report.',
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='Save the full local payload manifest (prefer ignored maintenance/github-prep-*/).')
    args = parser.parse_args()
    report = audit()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'files'}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report['status'] == 'PASS' else 1)
