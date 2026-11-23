from pathlib import Path
import tarfile,json,hashlib
D=Path(__file__).resolve().parents[1];W=D.parents[1]
root='new-a-performance/phase-scheduling-study-v1/'
keys=[root+'runs/identity-smoke-v1/ambient/block-1/'+a+'/runtime.json' for a in ['B0','B1']]
keys += [root+'runs/replay-disk-recovery-v1-campaign-1/ambient/block-1/C/runtime.json',root+'protocol.json',root+'code/prepare_fixtures.py',root+'code/study.py']
keys += [root+'heldout-prompts.json',root+'runs/heldout-fixtures-v1/fixtures.json',root+'runs/regression-fixtures-v1/fixtures.json']
with tarfile.open(W/'archive/legacy.tar.xz','r|xz') as t:
 m=json.load(t.extractfile(t.next()))['entries'];need={}
 for key in keys:
  row=m[key];assert row['type']=='file';need.setdefault(row['sha256'],[]).append(key)
 for item in t:
  digest=item.name.removeprefix('blobs/')
  if digest not in need:continue
  raw=t.extractfile(item).read();assert hashlib.sha256(raw).hexdigest()==digest
  for key in need.pop(digest):
   target=D/'evidence/archive'/key;target.parent.mkdir(parents=True,exist_ok=True)
   if target.exists():assert target.read_bytes()==raw
   else:target.write_bytes(raw)
  if not need:break
 assert not need
print('Historical runtime maps and protocol restored with byte verification:',len(keys))
