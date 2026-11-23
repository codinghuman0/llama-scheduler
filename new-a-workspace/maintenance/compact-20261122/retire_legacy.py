from pathlib import Path
import os,stat,json,hashlib,fcntl,gzip,subprocess,datetime
W=Path('/home/codinghuman/projects/new-a-workspace');D=Path(__file__).resolve().parent
all_snapshot=json.loads((D/'snapshot-before.json').read_text());roots=json.loads((D/'archive-check.json').read_text())['original_roots']
snapshot=[x for x in all_snapshot if Path(x['path']).parts[0] in roots]
assert all(not Path(x['path']).is_absolute() and '..' not in Path(x['path']).parts for x in snapshot)
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def disk():
 v=os.statvfs(W);return {'available_bytes':v.f_bavail*v.f_frsize,'free_inodes':v.f_favail}
def check_activity():
 found=[]
 for p in Path('/proc').glob('[0-9]*'):
  if int(p.name)==os.getpid():continue
  try:
   name=(p/'comm').read_text().strip()
   if name.startswith(('llama-server','llama_scx','llama_new_a','clang','cc1','cmake','ninja')) or name in ['make','gcc','g++','cc','ld']:found.append((p.name,name))
   if p.stat().st_uid!=os.getuid():continue
   for q in [p/'cwd',p/'exe',*(p/'fd').iterdir()]:
    try:t=os.readlink(q)
    except (OSError,FileNotFoundError):continue
    if any(t==str(W/r) or t.startswith(str(W/r)+'/') for r in roots):found.append((p.name,t))
  except (OSError,FileNotFoundError):continue
 assert not found,found
 assert Path('/sys/kernel/sched_ext/state').read_text().strip()=='disabled'
 return {'conflicts':found,'sched_ext':'disabled','note':'Read-only /proc inspection; no unrelated process stopped; system-service restricted FDs not universally readable.'}
plan={'scope':'Latest explicit user request authorizes replacing the six legacy trees with one standalone project; previous cache-only boundary superseded for these verified archived copies.','root':str(W),'allowlist_file':'snapshot-before.json','allowlist_entries':len(snapshot),'source_roots':roots,'preserved_outside_scope':['/home/codinghuman/projects/llama.cpp','/home/codinghuman/projects/model.gguf'],'exception':{'old':'new-a-runs/.measurement.lock','new':'state/.measurement.lock','action':'rename same inode while exclusively locked'},'archive':'archive/legacy.zip','archive_proof':'archive-check.json','active_replacements':['src/llama','runtime/B0','runtime/B1','runtime/NEW_A','scheduler','config','tools'],'method':'Only individually inventoried files/symlinks unlinked; empty directories removed after; no following symlinks, no git reset/clean/gc, no external deletion.'}
(D/'deletion-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
assert os.getuid()!=0
with (W/'new-a-runs/.measurement.lock').open('rb') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 lockino=os.fstat(lock.fileno()).st_ino;assert lockino==800700
 activity=check_activity();before=disk()
 archive=json.loads((D/'archive-check.json').read_text());assert archive['status']=='PASS' and sha(W/'archive/legacy.zip')==archive['archive_sha256']
 current=set()
 for r in roots:
  for root,ds,fs in os.walk(W/r,followlinks=False):
   assert not os.path.ismount(root)
   for n in list(ds):
    p=Path(root)/n
    if p.is_symlink():current.add(str(p.relative_to(W)));ds.remove(n)
   current.update(str((Path(root)/n).relative_to(W)) for n in fs)
 assert current=={x['path'] for x in snapshot},('unrecorded/missing files',list(current^{x['path'] for x in snapshot})[:15])
 mismatches=[];metadata_changes=[]
 for x in snapshot:
  p=W/x['path'];s=p.lstat()
  assert p.parent.resolve().is_relative_to(W)
  if x['type']=='symlink':ok=p.is_symlink() and os.readlink(p)==x['target']
  else:ok=stat.S_ISREG(s.st_mode) and sha(p)==x['sha256']
  if not ok:mismatches.append(x['path'])
  if (s.st_ino,s.st_mtime_ns)!=(x['inode'],x['mtime_ns']):metadata_changes.append(x['path'])
 assert not mismatches,mismatches
 # Protect original model/source separately from new source snapshots.
 previous=W/'new-a-performance/workspace-cleanup-20261122T061623Z/file-inventory-before.jsonl.gz'
 originals=[]
 for line in gzip.open(previous,'rt'):
  x=json.loads(line)
  if x['relative']=='model.gguf' or x['relative'].startswith('llama.cpp/'):
   assert sha(x['path'])==x['sha256'];originals.append(x)
 with gzip.open(D/'originals-preserved.json.gz','wt') as f:json.dump(originals,f)
 for path,row in json.loads((D/'runtime-preservation.json').read_text()).items():assert sha(W/path)==row['sha256']
 check_activity()
 assert not (W/'state/.measurement.lock').exists()
 os.rename(W/'new-a-runs/.measurement.lock',W/'state/.measurement.lock')
 assert (W/'state/.measurement.lock').stat().st_ino==lockino
 removed=0
 with gzip.open(D/'deleted-paths.jsonl.gz','wt') as log:
  for x in snapshot:
   if x['path']=='new-a-runs/.measurement.lock':continue
   p=W/x['path'];s=p.lstat()
   assert Path(x['path']).parts[0] in roots and p.is_relative_to(W)
   assert not p.is_relative_to(W.parent/'llama.cpp') and p != W.parent/'model.gguf'
   # Prevent swapping a target between validation and unlink.
   assert (s.st_dev,s.st_ino)==(x['dev'],x['inode']),str(p)
   p.unlink();removed+=1;log.write(json.dumps({'path':str(p),'type':x['type'],'archived':True})+'\n')
 for r in roots:
  for root,ds,fs in os.walk(W/r,topdown=False,followlinks=False):
   assert not fs,(root,fs)
   Path(root).rmdir()
 assert all(not (W/r).exists() for r in roots)
 for path,row in json.loads((D/'runtime-preservation.json').read_text()).items():assert sha(W/path)==row['sha256']
 for x in originals:assert sha(x['path'])==x['sha256']
 assert os.fstat(lock.fileno()).st_ino==(W/'state/.measurement.lock').stat().st_ino==lockino
 after=disk()
 result={'status':'PASS','removed_entries':removed,'legacy_roots_removed':roots,'runtime_files_sha256':'PASS','original_files_sha256':len(originals),'model_and_original_untouched':True,'lock_inode':lockino,'metadata_only_changes_since_archive':metadata_changes,'process_check':activity,'disk_before_deletion':before,'disk_after_deletion':after,'net_available_gain_since_pack_started':after['available_bytes']-archive['free_before'],'completed':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 (D/'deletion-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2),flush=True)
