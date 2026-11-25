#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""Build only the existing nonprivileged CPUID helper, never BPF."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / 'new_a_portable/cpu_probe.c'
HEADER = HERE.parent / 'new_a/new_a.h'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_probe(path):
    path = Path(path).resolve()
    info = path.stat()
    if info.st_uid != os.getuid() or info.st_mode & (stat.S_ISUID | stat.S_ISGID | 0o022):
        raise ValueError('CPU probe는 사용자 소유여야 하며 setid 및 그룹·다른 사용자 쓰기 권한이 없어야 합니다.')
    proof = json.loads(path.with_name('probe-build.json').read_text())
    if proof != dict(schema=1, binary=path.name, binary_sha256=sha(path), source_sha256=sha(SOURCE), header_sha256=sha(HEADER), bpf='NOT_BUILT_OR_LOADED'):
        raise ValueError('CPU probe 빌드와 소스의 해시가 일치하지 않습니다.')
    return proof['binary_sha256']


def build(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    binary = output / 'cpu-probe'
    subprocess.run(['cc', '-O2', '-Wall', '-Wextra', '-Werror', '-std=gnu11', '-I' + str(HEADER.parent), str(SOURCE), '-o', str(binary)], check=True, timeout=30)
    binary.chmod(0o755)
    with (output / 'probe-build.json').open('x') as stream:
        json.dump(dict(schema=1, binary=binary.name, binary_sha256=sha(binary), source_sha256=sha(SOURCE), header_sha256=sha(HEADER), bpf='NOT_BUILT_OR_LOADED'), stream, indent=2)
        stream.write('\n')
    return binary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(build(args.output))
