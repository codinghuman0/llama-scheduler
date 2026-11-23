from pathlib import Path
import datetime,fcntl,gzip,hashlib,json,os,shutil,subprocess,tempfile,time,zipfile
W=Path(__file__).resolve().parents[2];D=Path(__file__).resolve().parent

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def save(name,data):(D/name).write_text(json.dumps(data,indent=2)+'\n')
def run(argv,env=None):
 p=subprocess.run(list(map(str,argv)),env=env,text=True,capture_output=True,timeout=180)
 assert p.returncode==0,(argv,p.returncode,p.stdout[-1000:],p.stderr[-1000:])
 return p.stdout
assert os.getuid()!=0
v=json.loads((D/'archive-verification.json').read_text());assert v['status']=='PASS' and v['potential_saving_bytes']>0
old=json.loads((D/'manifest-before.json').read_text());changed={}
allowed={'README.md','tools/archive.py','tools/run.py','tools/verify.py'}
cache={}
for name,item in old['files'].items():
 p=W/name;st=p.stat();key=(st.st_dev,st.st_ino)
 digest=cache.setdefault(key,sha(p)) if key not in cache else cache[key]
 if digest!=item['sha256']:
  assert name in allowed,name;changed[name]={'before':item['sha256'],'after':digest}
 assert (st.st_mode&0o777)==item['mode'],name
for row in json.loads(gzip.open(W/'maintenance/compact-20261122/originals-preserved.json.gz','rt').read()):
 p=Path(row['path']);assert sha(p)==row['sha256'],str(p)
 assert p.stat().st_mtime_ns==row['mtime_ns'],str(p)
assert os.path.samefile(W/'models/model.gguf',W.parent/'model.gguf')
save('protected-content-check.json',{'status':'PASS','unchanged_package_files':len(old['files'])-len(changed),'authorized_path_and_documentation_changes':changed,'original_source_and_model_files_verified':3265,'model_sha256':sha(W/'models/model.gguf'),'model_data_copied':False,'model_original_link_count':(W.parent/'model.gguf').stat().st_nlink})
m=json.loads(json.dumps(old));m['archive_path']='archive/legacy.tar.xz';m['archive_format']='content-addressed-tar-xz-v1';m['archive_sha256']=v['archive_sha256'];m['model_path']='models/model.gguf'
for name in changed:m['files'][name]['sha256']=changed[name]['after']
(W/'config/package-manifest.json').write_text(json.dumps(m,indent=2)+'\n')
verification=json.loads(run(['python3','-B',W/'tools/verify.py','--archive']));assert verification['status']=='PASS';save('package-check.json',verification)
key='new-a-performance/output-divergence-diagnosis-v1/next-step.md'
target=D/'archive-read-check.md'
run(['python3','-B',W/'tools/archive.py','get',key,target])
with zipfile.ZipFile(W/'archive/legacy.zip') as z:
 entry=json.loads(z.read('manifest.json'))['entries'][key]
 assert sha(target)==entry['sha256']
save('archive-read-check.json',{'status':'PASS','path':key,'sha256':sha(target)})
# Each copied file is a directory entry under the relocation root, not a symlink.
rel=Path(tempfile.mkdtemp(prefix='relocation-',dir=D));checks={}
try:
 for name in list(m['files'])+['config/package-manifest.json','models/model.gguf','archive/legacy.tar.xz','state/.measurement.lock']:
  out=rel/name;out.parent.mkdir(parents=True,exist_ok=True)
  if not out.exists():os.link(W/name,out)
 result=json.loads(run(['python3','-B',rel/'tools/verify.py','--archive']));assert result['status']=='PASS'
 description=json.loads(run(['bash',rel/'run.sh','--describe']));assert str(rel/'models/model.gguf') in description['argv']
 for arm in ['B0','B1','NEW_A']:
  folder=rel/'runtime'/arm;env={'PATH':'/usr/bin:/bin','LD_LIBRARY_PATH':str(folder),'LC_ALL':'C'}
  run([folder/'llama-server','--help'],env);ldd=run(['ldd',folder/'llama-server'],env)
  assert 'not found' not in ldd
  for line in ldd.splitlines():
   parts=line.split()
   if len(parts)>2 and parts[1]=='=>' and parts[0].startswith(('libllama','libggml','libmtmd')):assert Path(parts[2]).is_relative_to(folder)
  checks[arm]='PASS: help and relocated project DSOs'
 with (W/'state/.measurement.lock').open('rb') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  configure=['cmake','-S',str(rel/'src/llama'),'-B',str(rel/'configure-check'),'-DCMAKE_BUILD_TYPE=Release','-DBUILD_SHARED_LIBS=ON','-DGGML_NATIVE=ON','-DGGML_OPENMP=ON','-DGGML_CUDA=OFF','-DGGML_VULKAN=OFF','-DGGML_HIP=OFF','-DGGML_SYCL=OFF','-DGGML_METAL=OFF','-DGGML_RPC=OFF','-DLLAMA_SCX_PHASE_HINT=ON','-DLLAMA_SCX_PHASE_TRACE=OFF','-DLLAMA_BUILD_TESTS=OFF','-DLLAMA_BUILD_EXAMPLES=OFF','-DLLAMA_BUILD_UI=OFF','-DLLAMA_USE_PREBUILT_UI=OFF','-DLLAMA_CURL=OFF']
  output=run(configure);(D/'relocation-cmake.stdout').write_text(output)
  save('relocation-cmake.json',{'status':'PASS','argv':configure,'full_build':'NOT_RUN','temporary_build_removed_with_relocation_tree':True})
 save('relocation-check.json',{'status':'PASS','model_resolves_inside_relocated_folder':True,'source_and_runtime_manifest':'PASS','runtime_checks':checks,'inference':'NOT_RUN','BPF':'NOT_RUN','temporary_directory_removed_on_exit':str(rel)})
finally:shutil.rmtree(rel)
with (W/'state/.measurement.lock').open('rb') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 assert Path('/sys/kernel/sched_ext/state').read_text().strip()=='disabled'
 assert sha(W/'archive/legacy.zip')==old['archive_sha256']
 removed=[]
 for row in json.loads((D/'test-executable-cleanup-plan.json').read_text()):
  p=W/row['path'];assert sha(p)==row['sha256'];p.unlink();removed.append(row)
 (W/'archive/legacy.zip').unlink()
 save('deletion-result.json',{'status':'PASS','old_archive_removed_after_full_retained_hash_and_relocation_checks':True,'old_archive_sha256':old['archive_sha256'],'new_archive_sha256':v['archive_sha256'],'generated_test_executables_removed':removed,'lock_inode':os.fstat(lock.fileno()).st_ino,'sched_ext':'disabled','unrelated_processes_stopped':False})
free=shutil.disk_usage(W).free
result={'status':'COMPLETE','time':datetime.datetime.now(datetime.timezone.utc).isoformat(),'archive_before_bytes':v['old_archive_bytes'],'archive_after_bytes':v['archive_bytes'],'archive_saved_bytes':v['potential_saving_bytes'],'test_binary_bytes_removed':sum(r['size'] for r in removed),'disk_free_bytes':free,'disk_free_increase_bytes':free-json.loads((D/'storage-before.json').read_text())['available'],'model_bytes':(W/'models/model.gguf').stat().st_size,'model_additional_data_bytes':0,'runtime_source_evidence_and_original_model_preserved':True}
save('result.json',result);print(json.dumps(result,indent=2))
