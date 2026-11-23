"""Copy only selected historical text records, without executing their commands."""
import hashlib,json,tarfile
from pathlib import Path
D=Path(__file__).resolve().parents[1];W=D.parents[1]
entries=json.loads((D/'evidence/archive-index.json').read_text())['entries'];wanted={}
prefix='new-a-performance/phase-scheduling-study-v1/identity/B1-components/'
for comp in ['build-prefill-attention-v2','build-phase-batch-q4-exact-v1']:
 for tail in ['build-report.json','tracked-overlay.patch','build-metadata/compile_commands.json']:
  key=prefix+comp+'/'+tail
  if key in entries:wanted[key]='evidence/historical-build/'+comp+'/'+tail
for tail in ['src/CMakeFiles/llama.dir/link.txt','src/CMakeFiles/llama.dir/flags.make']:
 key='new-a-lab/build-prefill-attention-v2/llama-build/'+tail;wanted[key]='evidence/historical-build/llama/'+tail
for tail in ['tools/server/server-phase.h','tools/sched_ext/UPSTREAM_BASELINE.json','tools/sched_ext/README.md','THIRD_PARTY_NOTICES.md','NOTICE','LICENSE']:
 key='llama.cpp-lightweight/'+tail
 if key in entries:wanted[key]='sources/base-59abec4/'+tail
by_hash={}
for key,dest in wanted.items():
 row=entries[key];assert row['type']=='file';by_hash.setdefault(row['sha256'],[]).append((key,dest))
records=[]
with tarfile.open(W/'archive/legacy.tar.xz','r|xz') as t:
 for member in t:
  digest=member.name.removeprefix('blobs/')
  if digest not in by_hash:continue
  content=t.extractfile(member).read();assert hashlib.sha256(content).hexdigest()==digest
  for key,dest in by_hash.pop(digest):
   p=D/dest;p.parent.mkdir(parents=True,exist_ok=True)
   if p.exists():assert p.read_bytes()==content
   else:p.write_bytes(content)
   records.append(dict(archive_path=key,sha256=digest,bytes=len(content),output=dest))
  if not by_hash:break
assert not by_hash
(D/'evidence/historical-build-extraction.json').write_text(json.dumps(records,indent=2)+'\n')
print(json.dumps(dict(files=len(records),bytes=sum(x['bytes'] for x in records))))
