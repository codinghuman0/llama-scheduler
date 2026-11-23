from pathlib import Path
import datetime,fcntl,gzip,hashlib,json,os,shutil
D=Path(__file__).resolve().parents[1];W=D.parents[1];O=D.parent/'persistent-pool-port-v1'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
with (W/'state/.measurement.lock').open('r') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);assert os.fstat(lock.fileno()).st_ino==800700
 before=json.loads((D/'evidence/protection-before.json').read_text())
 assert sha(W/'config/package-manifest.json')==before['source_manifest_sha256']
 for rel,row in before['files'].items():
  p=W/rel;assert sha(p)==row['sha256'],rel;assert p.stat().st_mode&0o777==row['mode'],rel
 for rel,digest in before['prepared_pool_files'].items():assert sha(O/rel)==digest,rel
 assert sha(W/before['archive']['path'])==before['archive']['sha256']
 assert sha(W/'models/model.gguf')==before['model']['sha256']
 assert (W/'models/model.gguf').stat().st_ino==before['model']['inode']
 originals=json.loads(gzip.open(W/'maintenance/compact-20261122/originals-preserved.json.gz','rt').read())
 for row in originals:assert sha(Path(row['path']))==row['sha256'],row['path']
 leftovers=[]
 for p in Path('/proc').glob('[0-9]*'):
  if int(p.name)==os.getpid():continue
  try:argv=(p/'cmdline').read_bytes().split(b'\0')
  except (PermissionError,FileNotFoundError,ProcessLookupError):continue
  if any(x.decode(errors='replace').startswith(str(D)) and not x.decode(errors='replace').endswith('check_protection.py') for x in argv):leftovers.append(int(p.name))
 assert not leftovers,leftovers
 assert Path('/sys/kernel/sched_ext/state').read_text().strip()=='disabled'
 result=dict(status='PASS',time=datetime.datetime.now(datetime.timezone.utc).isoformat(),latest_migration_manifest_unchanged=True,protected_workspace_files=len(before['files']),prepared_pool_files=len(before['prepared_pool_files']),outside_original_files=len(originals),model_sha256=before['model']['sha256'],archive_sha256=before['archive']['sha256'],model_inode_unchanged=True,protected_file_modes_unchanged=True)
 save(D/'evidence/protection-after.json',result)
 cleanup=dict(status='PASS',uid=os.getuid(),sudo_used=False,BPF_loaded=False,scheduler_state='disabled',measurement_lock_available=True,lock_inode=800700,owned_processes_remaining=leftovers,disk_free_bytes=shutil.disk_usage(W).free,originals_modified=False,note='Candidate runtimes and reproducibility inputs retained. No deletion of protected evidence/model/source.')
 save(D/'cleanup.json',cleanup);print(json.dumps(dict(protection=result,cleanup=cleanup),indent=2))
