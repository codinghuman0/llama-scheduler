#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,os,zipfile
D=Path(__file__).resolve().parents[1];archive=D/'output-divergence-diagnosis-v1.zip'
assert not archive.exists()
assert json.loads((D/'evidence/preservation-after.json').read_text())['status']=='PASS'
assert json.loads((D/'evidence/recalculation-check/recalculation.json').read_text())['status']=='PASS'
assert json.loads((D/'quality-v2/summary.json').read_text())['status']=='COMPLETE'
blobdir=D/'logit-blobs';blobdir.mkdir(exist_ok=True);mapping={}
for p in sorted((D/'runs').rglob('*.f32')):
 digest=hashlib.sha256(p.read_bytes()).hexdigest();mapping[str(p.relative_to(D))]=digest;target=blobdir/digest
 if not target.exists():os.link(p,target)
 else:assert hashlib.sha256(target.read_bytes()).hexdigest()==digest
(D/'LOGIT_BLOBS.json').write_text(json.dumps(mapping,indent=2)+'\n')
excluded={'manifest.json','package-result.json','output-divergence-diagnosis-v1.zip','output-divergence-diagnosis-v1.zip.sha256'}
files={};omitted=[]
for p in sorted(D.rglob('*')):
 if not p.is_file():continue
 rel=str(p.relative_to(D))
 if p.name in excluded:continue
 if p.suffix in ['.so','.f32'] or '__pycache__' in p.parts:omitted.append(rel);continue
 files[rel]=hashlib.sha256(p.read_bytes()).hexdigest()
manifest=dict(kind='Review package; original f32 paths resolved via LOGIT_BLOBS.json; executable DSOs excluded',files=files,omitted_local_paths=omitted)
(D/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for rel in [*files,'manifest.json']:z.write(D/rel,rel)
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 for rel,digest in files.items():assert hashlib.sha256(z.read(rel)).hexdigest()==digest
result=dict(path=str(archive),bytes=archive.stat().st_size,sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),files=len(files)+1,logit_path_count=len(mapping),unique_logit_blobs=len(set(mapping.values())),status='ZIP_CRC_AND_MEMBER_HASH_PASS',excluded='Model/weights, credentials, runtime/diagnostic executable DSOs, whole builds; raw required logits included once per content hash')
(D/'package-result.json').write_text(json.dumps(result,indent=2)+'\n');(D/(archive.name+'.sha256')).write_text(result['sha256']+'  '+archive.name+'\n');print(json.dumps(result,indent=2))
