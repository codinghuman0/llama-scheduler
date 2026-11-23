#!/usr/bin/env python3
"""Verify the standalone package without building, inference, sudo, or BPF attach."""
from pathlib import Path
import argparse,fcntl,hashlib,json,os,subprocess
ROOT=Path(__file__).resolve().parents[1]
def sha(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--archive',action='store_true');p.add_argument('--model',type=Path,default=ROOT/'models/model.gguf');a=p.parse_args()
 m=json.loads((ROOT/'config/package-manifest.json').read_text());errors=[];checked=0;cache={}
 with (ROOT/'state/.measurement.lock').open('rb') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  for rel,row in m['files'].items():
   path=ROOT/rel
   if not path.is_file() or path.is_symlink():errors.append([rel,'missing/unexpected symlink']);continue
   st=path.stat();key=(st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns)
   if key not in cache:cache[key]=sha(path)
   if cache[key]!=row['sha256'] or (st.st_mode&0o777)!=row['mode']:errors.append([rel,'hash/mode'])
   checked+=1
  for arm in ['B0','B1','NEW_A']:
   folder=ROOT/'runtime'/arm
   result=subprocess.run(['ldd',str(folder/'llama-server')],env={'PATH':'/usr/bin:/bin','LD_LIBRARY_PATH':str(folder)},text=True,capture_output=True)
   if result.returncode or 'not found' in result.stdout:errors.append([arm,'library resolution'])
   for line in result.stdout.splitlines():
    fields=line.split()
    if len(fields)>2 and fields[1]=='=>' and fields[0].startswith(('libllama','libggml','libmtmd')):
     if not Path(fields[2]).resolve().is_relative_to(folder):errors.append([arm,'external project DSO',line])
  old=m['retired_roots']
  if any((ROOT/n).exists() for n in old):errors.append(['layout','retired root recreated'])
  if any((ROOT/n).exists() for n in ['llama.cpp','model.gguf']):errors.append(['layout','redundant compatibility alias recreated'])
  if a.archive and sha(ROOT/m.get('archive_path','archive/legacy.zip'))!=m['archive_sha256']:errors.append(['archive','sha256'])
  if a.model and sha(a.model)!=m['model_sha256']:errors.append(['model','sha256'])
 print(json.dumps({'status':'FAIL' if errors else 'PASS','files_checked':checked,'archive_checked':a.archive,'model_checked':bool(a.model),'errors':errors,'inference':'NOT_RUN','BPF_attach':'NOT_RUN'},indent=2))
 return bool(errors)
if __name__=='__main__':raise SystemExit(main())
