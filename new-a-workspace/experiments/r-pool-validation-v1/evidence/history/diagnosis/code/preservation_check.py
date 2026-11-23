#!/usr/bin/env python3
from pathlib import Path
import datetime,hashlib,json,os,subprocess
D=Path(__file__).resolve().parents[1];before=json.loads((D/'evidence/preservation-before.json').read_text());files=[];repos=[]
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
for p,h in before['protected'].items():
 actual=sha(p) if Path(p).is_file() else None;files.append(dict(path=p,before=h,after=actual,equal=h==actual))
for r in before['repositories']:
 row={'path':r['path']}
 for k,args in {'head':['rev-parse','HEAD'],'status':['status','--porcelain=v1','-uall'],'refs':['show-ref']}.items():
  p=subprocess.run(['git','-C',r['path'],*args],env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'},capture_output=True,text=True);v=dict(rc=p.returncode,stdout=p.stdout,stderr=p.stderr);row[k]=v;row[k+'_equal']=v==r[k]
 repos.append(row)
ok=all(x['equal'] for x in files) and all(all(x[k+'_equal'] for k in ['head','status','refs']) for x in repos)
result=dict(status='PASS' if ok else 'FAIL',created=datetime.datetime.now(datetime.timezone.utc).isoformat(),files=files,repositories=repos,authorized_cache_exception='625 CMake dependency *.o.d caches removed only; protected source/binary/model/raw/archive and refs unchanged; cleanup report outside study in new-a-lab/cache-only-cleanup-20261122T045607Z')
(D/'evidence/preservation-after.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(status=result['status'],protected_files=len(files),repositories=len(repos))));assert ok
