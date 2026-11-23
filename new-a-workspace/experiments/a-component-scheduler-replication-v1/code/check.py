"""Verify frozen inputs and all pre-existing workspace content."""
import gzip,json,os
from pathlib import Path
from common import *
def protection():
 with gzip.open(D/'evidence/protected-before.json.gz','rt') as f:old=json.load(f)
 cache={};bad=[]
 for rel,row in old.items():
  p=W/rel
  if 'link' in row:
   if not p.is_symlink() or os.readlink(p)!=row['link']:bad.append(rel)
   continue
  if not p.is_file():bad.append(rel);continue
  st=p.stat();key=(st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns)
  if key not in cache:cache[key]=sha(p)
  if cache[key]!=row['sha256'] or st.st_size!=row['size'] or (st.st_mode & 0o777)!=row['mode']:bad.append(rel)
 return dict(status='PASS' if not bad else 'FAIL',protected_files=len(old),changed=bad)
if __name__=='__main__':
 verify_inputs();no_model_process();guard();r=protection();print(json.dumps(r,indent=2));assert r['status']=='PASS'
