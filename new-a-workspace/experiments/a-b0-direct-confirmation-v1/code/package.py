"""Create a small source/raw review ZIP and verify every contained member."""
import fcntl,hashlib,json,zipfile
from common import *
name='a-b0-direct-confirmation-v1-review.zip';target=D/name
assert not target.exists()
assert read(D/'completion-audit.json')['status']=='PASS'
with (W/'state/.measurement.lock').open('r') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);no_model_process()
 files=[]
 for p in sorted(D.rglob('*')):
  if not p.is_file() or '__pycache__' in p.parts:continue
  if p.name in [name,'REVIEW_MANIFEST.json','review-zip.json',name+'.sha256']:continue
  if p.suffix in ['.gguf','.so','.o','.a','.zip','.pyc'] or '.so.' in p.name:continue
  with p.open('rb') as f:
   assert f.read(4)!=b'\x7fELF',str(p)
  files.append(p)
 entries=[]
 with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for p in files:
   rel=str(p.relative_to(D));raw=p.read_bytes();entries.append(dict(path=rel,size=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
   info=zipfile.ZipInfo(rel);info.create_system=3;info.external_attr=(p.stat().st_mode&0xffff)<<16;info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,raw)
  manifest=dict(schema=1,entries=entries,scope='Code/inputs/raw/analysis review; integrated workspace runtime and original model required for inference; no runtime/model/build clone')
  blob=(json.dumps(manifest,indent=2)+'\n').encode();z.writestr('REVIEW_MANIFEST.json',blob)
 with zipfile.ZipFile(target) as z:
  assert z.testzip() is None
  for row in entries:assert hashlib.sha256(z.read(row['path'])).hexdigest()==row['sha256']
  assert z.getinfo('reproduce.sh').external_attr>>16 & 0o100
  assert z.read('REVIEW_MANIFEST.json')==blob
 (D/'REVIEW_MANIFEST.json').write_bytes(blob)
 record=dict(status='PASS',path=name,size_bytes=target.stat().st_size,sha256=sha(target),members=len(entries)+1,member_manifest='REVIEW_MANIFEST.json',external_member_manifest='REVIEW_MANIFEST.json',all_member_hashes_verified=True,zip_crc='PASS',time=now())
 save(D/'review-zip.json',record);(D/(name+'.sha256')).write_text(record['sha256']+'  '+name+'\n');print(json.dumps(record,indent=2))
