"""Freeze a small local review ZIP, excluding models, credentials and builds."""
from pathlib import Path
import hashlib,json,re,zipfile
D=Path(__file__).resolve().parents[1]
archive=D/'persistent-pool-port-v1-review.zip'
assert not archive.exists(),'Keep existing review ZIPs; use a distinct package revision'
excluded={'REVIEW-MANIFEST.json','review-zip.json','completion-audit.json','persistent-pool-port-v1-review.zip','persistent-pool-port-v1-review.zip.sha256'}
files={}
for p in sorted(D.rglob('*')):
 if not p.is_file():continue
 rel=str(p.relative_to(D))
 if rel in excluded or '__pycache__' in p.parts:continue
 assert not p.is_symlink()
 raw=p.read_bytes()
 assert not raw.startswith((b'\x7fELF',b'GGUF')) and p.suffix not in ['.gguf','.o','.a','.zip'],rel
 assert not re.search(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----)',raw),rel
 files[rel]={'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'mode':p.stat().st_mode&0o777}
manifest={'scope':'Review only. Requires protected new-a-workspace for model-free replay. No model execution path. Historical evidence is labeled and not new performance data.','files':files}
(D/'REVIEW-MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for rel in [*files,'REVIEW-MANIFEST.json']:
  p=D/rel;info=zipfile.ZipInfo('persistent-pool-port-v1/'+rel,date_time=(2026,11,22,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=(p.stat().st_mode&0o777)<<16
  z.writestr(info,p.read_bytes())
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 actual=json.loads(z.read('persistent-pool-port-v1/REVIEW-MANIFEST.json'));assert actual==manifest
 assert len(z.namelist())==len(files)+1
 for name,row in actual['files'].items():
  info=z.getinfo('persistent-pool-port-v1/'+name);raw=z.read(info)
  assert hashlib.sha256(raw).hexdigest()==row['sha256'] and len(raw)==row['bytes'] and (info.external_attr>>16)&0o777==row['mode']
digest=hashlib.sha256(archive.read_bytes()).hexdigest()
(D/(archive.name+'.sha256')).write_text(digest+'  '+archive.name+'\n')
result={'status':'PASS','archive':archive.name,'sha256':digest,'bytes':archive.stat().st_size,'member_files':len(files)+1,'source_file_hashes_verified':len(files),'CRC':'PASS','weights_credentials_build_binaries':'EXCLUDED','uploaded':False}
(D/'review-zip.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
