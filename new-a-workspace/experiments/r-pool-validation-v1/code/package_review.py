from pathlib import Path
import datetime,fcntl,hashlib,json,zipfile
D=Path(__file__).resolve().parents[1];W=D.parents[1];O=D.parent/'persistent-pool-port-v1'
assert json.loads((D/'completion-audit.json').read_text())['status']=='PASS'
name='r-pool-validation-v1-review.zip';target=D/name;assert not target.exists()
def sha(data):return hashlib.sha256(data).hexdigest()
def include(p):
 rel=p.relative_to(D)
 if not p.is_file() or '__pycache__' in rel.parts:return False
 if p.suffix in ['.o','.a','.so','.pyc','.zip','.gguf','.d'] or '.so.' in p.name:return False
 if 'runtime' in rel.parts:return False
 if p.name in ['review-members.json','review-zip.json',name+'.sha256']:return False
 with p.open('rb') as f:
  if f.read(4)==b'\x7fELF':return False
 return True
with (W/'state/.measurement.lock').open('r') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 files={str(p.relative_to(D)):p for p in D.rglob('*') if include(p)}
 for rel in ['method.patch','source-pin.json','baseline-runtime-identity.json','integration-delta.md','protocol.json','fixtures.json','tests/test-server-threadpool.cpp','tests/pool-stress.cpp','tests/phase-modes.cpp','overlay/tools/server/server-threadpool.h']:
  files['prepared-pool-reference/'+rel]=O/rel
 for rel in ['LICENSE','tools/sched_ext/LICENSE','vendor/cpp-httplib/LICENSE','tools/ui/src/lib/vendors/nerdamer-prime/LICENSE','tools/ui/src/lib/vendors/big-integer/LICENSE']:
  files['licenses/llama/'+rel]=W/'src/llama'/rel
 entries=[]
 with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for rel,p in sorted(files.items()):
   raw=p.read_bytes();entries.append(dict(path=rel,size=len(raw),sha256=sha(raw)));info=zipfile.ZipInfo(rel);info.create_system=3;info.external_attr=(p.stat().st_mode&0xFFFF)<<16;info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,raw)
  manifest=dict(schema=1,scope='Source/patch/protocol/core raw review package. Existing integrated workspace, system libraries and original model are required to execute; no model weights or full runtime/build clone.',entries=entries)
  blob=(json.dumps(manifest,indent=2)+'\n').encode();z.writestr('REVIEW_MANIFEST.json',blob)
 with zipfile.ZipFile(target) as z:
  assert z.testzip() is None
  for entry in entries:assert sha(z.read(entry['path']))==entry['sha256']
 (D/'review-members.json').write_bytes(blob)
 digest=sha(target.read_bytes());(D/(name+'.sha256')).write_text(digest+'  '+name+'\n')
 record=dict(status='PASS',path=name,size_bytes=target.stat().st_size,sha256=digest,members=len(entries)+1,member_manifest='review-members.json',zip_test='PASS',every_member_hash_verified=True,excluded=['model weights','runtime binaries','objects/static archives','full source/build clones','Python cache'],time=datetime.datetime.now(datetime.timezone.utc).isoformat())
 (D/'review-zip.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2))
