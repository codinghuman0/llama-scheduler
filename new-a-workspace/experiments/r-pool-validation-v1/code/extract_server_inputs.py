from pathlib import Path
import hashlib,json,tarfile
D=Path(__file__).resolve().parents[1];W=D.parents[1];O=D.parent/'persistent-pool-port-v1'
assert json.loads((D/'gate-results.json').read_text())['R']=='COMPATIBLE_IN_TESTED_SCOPE'
root=D/'evidence/history/server-build';root.mkdir(exist_ok=False)
def sha(b):return hashlib.sha256(b).hexdigest()
prefix='new-a-performance/phase-scheduling-study-v1/artifacts/'
selected={k:'study-code/'+Path(k).name for k in ['new-a-llm-scheduler/experiments/controlled_load/contention.py','new-a-llm-scheduler/experiments/controlled_load/load.py']}
for name in ['prefill_pressure_evidence.py']:
 selected['new-a-performance/phase-scheduling-study-v1/code/'+name]='study-code/'+name
for name in ['commands.json','identity.json','libserver-context.a']:
 selected[prefix+'runtime-prefill-pressure-v2/'+name]='pressure/'+name
for name in ['commands.json','identity.json','libllama-ui.a','libcpp-httplib.a','libllama-common-base.a','src/server.cpp','src/server-http.cpp','src/server-models.cpp','ui/ui.h']:
 selected[prefix+'runtime-decode-cost-v1/'+name]='decode/'+name
with tarfile.open(W/'archive/legacy.tar.xz','r|xz') as t:
 entries=json.load(t.extractfile(t.next()))['entries'];wanted={}
 for key,rel in selected.items():
  row=entries[key];assert row['type']=='file';wanted.setdefault(row['sha256'],[]).append((key,rel))
 for member in t:
  digest=member.name.removeprefix('blobs/')
  if digest not in wanted:continue
  blob=t.extractfile(member).read();assert sha(blob)==digest
  for key,rel in wanted.pop(digest):
   p=root/rel;p.parent.mkdir(exist_ok=True,parents=True);p.write_bytes(blob)
  if not wanted:break
 assert not wanted
(root/'manifest.json').write_text(json.dumps({key:dict(path=rel,sha256=entries[key]['sha256'],size=entries[key]['size']) for key,rel in selected.items()},indent=2)+'\n')
print('Restored',len(selected),'minimal pinned server linker/source inputs; no full build clone')
