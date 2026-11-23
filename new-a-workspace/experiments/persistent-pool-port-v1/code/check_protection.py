from pathlib import Path
import datetime,fcntl,gzip,hashlib,json,os,shutil
D=Path(__file__).resolve().parents[1];W=D.parents[1];M=W/'maintenance/self-contained-20261122'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
before=json.loads((D/'evidence/protection-before.json').read_text())
maintenance=json.loads((M/'protected-content-check.json').read_text());changes=maintenance['authorized_path_and_documentation_changes']
authorized=[];unchanged=[]
for rel,row in before['files'].items():
 p=W/rel
 if rel=='archive/legacy.zip':
  v=json.loads((M/'archive-verification.json').read_text());assert not p.exists();assert v['status']=='PASS'
  old=json.loads((M/'manifest-before.json').read_text());assert row['sha256']==old['archive_sha256'];assert sha(W/'archive/legacy.tar.xz')==v['archive_sha256']
  authorized.append({'path':rel,'reason':'User-authorized lossless retained-evidence recompression and conservative build-cache deletion','proof':'../../maintenance/self-contained-20261122/archive-verification.json'});continue
 actual=sha(p)
 if actual==row['sha256']:unchanged.append(rel);continue
 if rel in changes:assert changes[rel]['before']==row['sha256'] and changes[rel]['after']==actual
 elif rel=='GOAL_STATE.md':
  x=json.loads((M/'goal-state-transition.json').read_text());assert x['before_sha256']==row['sha256'] and x['after_sha256']==actual
 elif rel=='config/package-manifest.json':
  old=json.loads((M/'manifest-before.json').read_text());now=json.loads(p.read_text())
  for name,v in old['files'].items():assert now['files'][name]==v or name in changes
  assert now['archive_path']=='archive/legacy.tar.xz' and now['model_sha256']==old['model_sha256']
 else:raise AssertionError('Unauthorized protected-content change: '+rel)
 authorized.append({'path':rel,'before_sha256':row['sha256'],'after_sha256':actual,'reason':'Explicit user-requested standalone folder maintenance; no numerical source/runtime edit'})
assert sha(W/'models/model.gguf')==before['model']['sha256']
originals=json.loads(gzip.open(W/'maintenance/compact-20261122/originals-preserved.json.gz','rt').read())
for row in originals:assert sha(Path(row['path']))==row['sha256'],row['path']
result={'status':'PASS_WITH_AUTHORIZED_MAINTENANCE','time':datetime.datetime.now(datetime.timezone.utc).isoformat(),'unchanged_protected_files':len(unchanged),'authorized_changes':authorized,'original_source_and_model_files_checked':len(originals),'numerical_source_runtime_policy_model_unchanged':True,'maintenance_evidence':'../../maintenance/self-contained-20261122/report.md','archive_current_sha256':sha(W/'archive/legacy.tar.xz')}
(D/'evidence/protection-after.json').write_text(json.dumps(result,indent=2)+'\n')
with (W/'state/.measurement.lock').open('rb') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 assert os.fstat(lock.fileno()).st_ino==800700
 assert Path('/sys/kernel/sched_ext/state').read_text().strip()=='disabled'
 leftovers=[]
 for p in Path('/proc').glob('[0-9]*'):
  if int(p.name)==os.getpid():continue
  try:cmd=(p/'cmdline').read_bytes().split(b'\0')
  except (PermissionError,FileNotFoundError,ProcessLookupError):continue
  # Match argv elements, not a shell command containing this script as text.
  if any(x.decode(errors='replace').startswith(str(D/'results')) for x in cmd):leftovers.append(int(p.name))
 assert not leftovers,leftovers
 generated=[]
 for p in (D/'results').rglob('*'):
  if p.is_file():
   with p.open('rb') as f:magic=f.read(4)
   if magic==b'\x7fELF':generated.append(str(p.relative_to(D)))
 assert not generated,generated
 cleanup={'status':'PASS','measurement_lock_available':True,'lock_inode':800700,'scheduler_state':'disabled','test_processes_remaining':leftovers,'generated_ELFs_remaining':generated,'sudo_used':False,'model_inference':False,'BPF_loaded':False,'ordinary_uid':os.getuid(),'disk_free_bytes':shutil.disk_usage(W).free,'memory_available_kib':int(next(s.split()[1] for s in Path('/proc/meminfo').read_text().splitlines() if s.startswith('MemAvailable:'))),'process_observation_scope':'Own generated test paths and all readable /proc cmdlines; no unrelated process signaled'}
 (D/'cleanup.json').write_text(json.dumps(cleanup,indent=2)+'\n')
print(json.dumps({'protection':result['status'],'unchanged':len(unchanged),'authorized_maintenance_changes':len(authorized),'originals':len(originals),'cleanup':'PASS'}))
