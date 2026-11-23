#!/usr/bin/env python3
from pathlib import Path
import hashlib,json
D=Path(__file__).resolve().parents[1];j=json.loads((D/'manifest.json').read_text());fail=[]
for rel,digest in j['files'].items():
 p=D/rel
 if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=digest:fail.append(rel)
assert not fail,fail
print(json.dumps(dict(status='PASS',files=len(j['files']),scope='Package checksums; runtime/model verification occurs separately before replay')))
