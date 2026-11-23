from pathlib import Path
import copy,datetime,fcntl,hashlib,json,os,shlex,shutil,signal,subprocess,tarfile
D=Path(__file__).resolve().parents[1];W=D.parents[1];S=W/'src/llama';O=D.parent/'persistent-pool-port-v1';H=D/'evidence/history/server-build';BUILD=D/'build-server';A=D/'candidates/A/runtime';P=D/'candidates/P';R=P/'runtime'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def stop(*_):raise KeyboardInterrupt
signal.signal(signal.SIGTERM,stop)
state=read(D/'gate-results.json');assert state['R']==state['E-R']=='COMPATIBLE_IN_TESTED_SCOPE'
assert os.getuid()!=0 and Path('/sys/kernel/sched_ext/state').read_text().strip()=='disabled'
assert shutil.disk_usage(W).free>1024**3
with (W/'state/.measurement.lock').open('r') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);BUILD.mkdir(exist_ok=False);(BUILD/'obj').mkdir();(BUILD/'logs').mkdir();R.mkdir(parents=True)
 shutil.copytree(O/'overlay',P/'overlay');shutil.copy2(O/'method.patch',D/'patches/P-prepared-pool.patch')
 for p in A.iterdir():
  if p.name!='libllama-server-impl.so':os.link(p,R/p.name)
 frozen=read(H/'pressure/identity.json');old='/home/codinghuman/projects';decode=old+'/new-a-performance/phase-scheduling-study-v1/artifacts/runtime-decode-cost-v1';pressure=old+'/new-a-performance/phase-scheduling-study-v1/artifacts/runtime-prefill-pressure-v2';src=old+'/new-a-lab/llama-phase-barrier'
 with tarfile.open(W/'archive/legacy.tar.xz','r|xz') as t:entries=json.load(t.extractfile(t.next()))['entries']
 moves=[(pressure+'/src',str(P/'overlay/tools/server')),(decode+'/src',str(H/'decode/src')),(decode+'/ui',str(H/'decode/ui')),(decode+'/obj',str(BUILD/'obj')),(old+'/new-a-lab/build-phase-barrier/openmp/tools/server',str(S/'tools/server')),(old+'/new-a-lab/build-phase-barrier/openmp/tools/ui',str(H/'decode/ui')),(src,str(S))]
 def relocate(value):
  for before,after in moves:value=value.replace(before,after)
  return value
 commands=[]
 def run(argv,label,timeout=300):
  item=dict(argv=list(map(str,argv)),cwd=str(BUILD),environment={'PATH':'/usr/bin:/bin','LC_ALL':'C'},timeout_s=timeout,label=label);commands.append(item);save(BUILD/'commands.json',commands)
  with (BUILD/'logs'/(label+'.log')).open('w') as log:
   proc=subprocess.Popen(item['argv'],cwd=BUILD,env=item['environment'],stdout=log,stderr=log,start_new_session=True)
   try:proc.wait(timeout=timeout)
   except BaseException:
    if proc.poll() is None:
     os.killpg(proc.pid,signal.SIGTERM)
     try:proc.wait(timeout=5)
     except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
    raise
  item['returncode']=proc.returncode;save(BUILD/'commands.json',commands);assert proc.returncode==0,label;print(label,'PASS',flush=True)
 recreated={}
 for record in read(H/'decode/commands.json'):
  if record['log'] not in ['tu-12.log','tu-13.log','tu-14.log']:continue
  argv=[relocate(v) for v in record['argv']]
  for current,logical in [(str(H/'decode/src'),decode+'/src'),(str(H/'decode/ui'),decode+'/ui'),(str(S),src)]:argv.append('-fmacro-prefix-map='+current+'='+logical)
  run(argv,record['log'].removesuffix('.log'))
  old_object=record['argv'][record['argv'].index('-o')+1];obj=Path(argv[argv.index('-o')+1]);expected=entries[old_object.removeprefix(old+'/')]['sha256'];actual=sha(obj)
  recreated[obj.name]=dict(sha256=actual,archived_sha256=expected,byte_identical=actual==expected)
 save(BUILD/'recreated-object-identity.json',recreated)
 # Re-link the unchanged E server first; reject unnoticed build-input drift.
 link=next(x['argv'] for x in frozen['commands'] if x['log']=='link.log')
 def link_argv(context,output):
  result=[]
  for value in link:
   if value.startswith(decode+'/obj/'):value=str(BUILD/'obj'/Path(value).name)
   elif value==pressure+'/libserver-context.a':value=str(context)
   elif value.startswith(decode+'/') and value.endswith('.a'):value=str(H/'decode'/Path(value).name)
   elif '/runtime/bin/' in value:value=str(A/Path(value).name)
   result.append(value)
  result[result.index('-o')+1]=str(output);return result
 run(link_argv(H/'pressure/libserver-context.a',BUILD/'parent-relinked.so'),'parent-relink')
 parent_equal=sha(BUILD/'parent-relinked.so')==sha(A/'libllama-server-impl.so')
 save(BUILD/'parent-relink.json',dict(byte_identical=parent_equal,actual_sha256=sha(BUILD/'parent-relinked.so'),frozen_E_sha256=sha(A/'libllama-server-impl.so'),recreated_objects=recreated))
 assert parent_equal,'Unchanged E relink differs; investigate before P'
 argv=[relocate(v) for v in frozen['compilation']['argv']];argv[argv.index('-o')+1]=str(BUILD/'obj/7-server-context.cpp.o');argv[argv.index('-MF')+1]=str(BUILD/'obj/7-server-context.cpp.o.d')
 for current,logical in [(str(P/'overlay/tools/server'),pressure+'/src'),(str(H/'decode/src'),decode+'/src'),(str(H/'decode/ui'),decode+'/ui'),(str(S),src)]:argv.append('-fmacro-prefix-map='+current+'='+logical)
 run(argv,'P-context')
 archive=BUILD/'libserver-context.a';shutil.copy2(H/'pressure/libserver-context.a',archive)
 run(['/usr/bin/ar','r',archive,BUILD/'obj/7-server-context.cpp.o'],'P-context-archive');run(['/usr/bin/ranlib',archive],'P-context-index')
 run(link_argv(archive,R/'libllama-server-impl.so'),'P-full-server-link')
 # All arithmetic libraries and launch helper remain exactly A/R.
 for p in A.iterdir():
  if p.name!='libllama-server-impl.so':assert sha(p)==sha(R/p.name),p.name
 # Validate included unchanged headers against the frozen E recorded source hashes.
 source_hashes=frozen['source_hashes'];checks={}
 for dep in (BUILD/'obj').glob('*.d'):
  content=dep.read_text().replace('\\\n',' ')
  for token in shlex.split(content.split(':',1)[1]):
   path=Path(token)
   if not path.is_absolute() or not path.exists():continue
   path=path.resolve()
   if path.is_relative_to(S):
    key=src+'/'+str(path.relative_to(S))
    if str(path.relative_to(S))=='tools/server/newa-prefill-pressure.h':key=pressure+'/src/newa-prefill-pressure.h'
    assert key in source_hashes,(key,'missing archived E header hash')
    assert sha(path)==source_hashes[key],key;checks[str(path.relative_to(S))]=sha(path)
 save(BUILD/'unchanged-header-check.json',dict(status='PASS',headers=checks))
 cases=read(D/'cases-AP.json');case=copy.deepcopy(cases['A']);case['runtime']='P';case['server_argv'][0]=str(R/'llama-server');case['server_env'].update(LD_LIBRARY_PATH=str(R),GGML_NEWA_POOL='donor');case['artifacts']={str(R/Path(k).name):sha(R/Path(k).name) for k in case['artifacts']};cases['P']=case;save(D/'cases-AP.json',cases)
 save(P/'identity.json',dict(status='FULL_SERVER_LINKED_NOT_MODEL_VALIDATED',parent_relink_byte_identical=parent_equal,arithmetic_DSOs_identical_to_A=True,source='Exactly previously prepared donor pool overlay on unchanged E',source_hashes={str(p.relative_to(P)):sha(p) for p in (P/'overlay').rglob('*') if p.is_file()},runtime_hashes={p.name:sha(p) for p in R.iterdir()},case=case,commands='../../build-server/commands.json',macro_prefix_map='Non-arithmetic path mapping restores original __FILE__ spellings; unmodified E relink required byte identity'))
 with (D/'ledger.jsonl').open('a') as f:f.write(json.dumps(dict(time=datetime.datetime.now(datetime.timezone.utc).isoformat(),stage='P-build',status='FULL_SERVER_LINKED',unchanged_E_relink_byte_identical=parent_equal))+'\n')
 print('P server fully linked, frozen E parent relink byte-identical',flush=True)
