#!/usr/bin/env python3
"""Seal a compact, reconstructable integration-v2 review package."""
import argparse
import hashlib
import json
from pathlib import Path
import stat
import subprocess
import tempfile
import zipfile

REPO = Path(__file__).resolve().parents[3]
PREFIX = "new-a-workspace/"
EVIDENCE = REPO / PREFIX / "experiments/team-integration-v2"


def git(*args, cwd=REPO, accepted=(0,)):
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, timeout=30)
    if result.returncode not in accepted:
        raise RuntimeError(result.stderr.decode(errors="replace"))
    return result.stdout


def names(data):
    return [part.decode() for part in data.split(b"\x00") if part]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def make_patch(base):
    tracked = names(git("diff", "--name-only", "-z", base))
    untracked = names(git("ls-files", "--others", "--exclude-standard", "-z"))
    code = [p for p in untracked if any(p.startswith(PREFIX + group) for group in
            ("scripts/", "src/llama/", "tools/integration_v2/"))]
    seal = [str((EVIDENCE / name).relative_to(REPO)) for name in
            ("sources.lock.json", "cmake-common.json", "effective-config.schema.json", "INTEL_HANDOFF.md",
             "NOTICE.md", "amd-local-validation.md", "compatibility-matrix.md")]
    for path in tracked + code + seal:
        if not (REPO / path).is_file():
            raise ValueError("Review path is absent or not a file: " + path)
    patch = git("diff", "--binary", base, "--", *tracked)
    for path in sorted(set(code + seal) - set(tracked)):
        patch += git("diff", "--no-index", "--binary", "--", "/dev/null", path, accepted=(1,))
    with tempfile.TemporaryDirectory(prefix="newa-v2-patch-check-") as temp:
        scratch = Path(temp)
        git("init", "--quiet", cwd=scratch)
        for path in tracked:
            entry = git("ls-tree", base, "--", path)
            if not entry:
                continue
            old = scratch / path
            old.parent.mkdir(parents=True, exist_ok=True)
            old.write_bytes(git("show", f"{base}:{path}"))
            mode = entry.split(maxsplit=1)[0]
            old.chmod(0o755 if mode == b"100755" else 0o644)
        diff = scratch / "candidate.patch"
        diff.write_bytes(patch)
        git("apply", "--check", str(diff), cwd=scratch)
        git("apply", str(diff), cwd=scratch)
        for path in sorted(set(tracked + code + seal)):
            restored = scratch / path
            current = REPO / path
            if restored.read_bytes() != current.read_bytes() or (
                bool(restored.stat().st_mode & stat.S_IXUSR) != bool(current.stat().st_mode & stat.S_IXUSR)
            ):
                raise ValueError("Reconstruction differs: " + path)
    return patch, sorted(set(tracked + code + seal))


def package(output):
    base = json.loads((EVIDENCE / "sources.lock.json").read_text())["workspace"]["base"]
    patch, paths = make_patch(base)
    files = {"integration-v2.patch": patch}
    for path in sorted(EVIDENCE.rglob("*")):
        if path.is_symlink():
            raise ValueError("Unexpected symlink: " + str(path))
        if not path.is_file() or path.suffix not in (".md", ".json", ".jsonl", ".log", ".patch", ".py", ".txt"):
            continue
        if path.name in ("review-manifest.json", "integration-v2.patch"):
            continue
        body = path.read_bytes()
        if body[:4] in (b"\x7fELF", b"GGUF") or len(body) > 32 * 1024**2:
            raise ValueError("Unexpected executable, weight or oversized member: " + str(path))
        files[str(path.relative_to(EVIDENCE))] = body
    manifest = {
        "status": "PATCH_RECONSTRUCTION_PASS", "base": base,
        "scope": "Development review; see GOAL_STATE.md for pending host and feature gates",
        "reconstructed_paths": paths,
        "members": {name: {"sha256": digest(data), "bytes": len(data)} for name, data in files.items()},
    }
    files["review-manifest.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() or any(digest(archive.read(p)) != digest(data) for p, data in files.items()):
            raise ValueError("Review ZIP integrity check failed")
    with output.with_suffix(output.suffix + ".sha256").open("x") as stream:
        stream.write(f"{digest(output.read_bytes())}  {output.name}\n")
    print(f"{output}: {output.stat().st_size} bytes, {len(paths)} reconstructed paths")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    package(parser.parse_args().output)
