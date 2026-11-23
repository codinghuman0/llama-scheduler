from pathlib import Path
import argparse,sys,resource,re
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
a=argparse.ArgumentParser();a.add_argument("--output",required=True,type=Path);options=a.parse_args()
import os,json,subprocess,fcntl,signal,datetime,hashlib,resource
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
def interrupted(*_):raise KeyboardInterrupt
signal.signal(signal.SIGTERM,interrupted)

D=Path(__file__).resolve().parents[1];W=Path(os.environ.get('NEWA_WORKSPACE',str(D.parents[1]))).resolve();S=W/'src/llama';R=W/'runtime/NEW_A';OUT=options.output.resolve();OUT.mkdir(parents=True,exist_ok=False)
case=json.loads((W/'config/arms.json').read_text())['C'];env=dict(case['env']);env.update(LD_LIBRARY_PATH=str(R),GGML_NEWA_POOL='off')
commands=[];checks={}
def run(argv,label,timeout=180):
 entry={'label':label,'argv':list(map(str,argv)),'cwd':str(D),'env':env,'timeout_s':timeout};commands.append(entry)
 (OUT/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
 with (OUT/(label+'.stdout')).open('w') as out,(OUT/(label+'.stderr')).open('w') as err:
  p=subprocess.Popen(entry['argv'],cwd=D,env=env,stdout=out,stderr=err,start_new_session=True)
  try:p.wait(timeout=timeout)
  except subprocess.TimeoutExpired:
   os.killpg(p.pid,signal.SIGTERM)
   try:p.wait(timeout=5)
   except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
   entry['timeout']=True
  except BaseException:
   if p.poll() is None:
    os.killpg(p.pid,signal.SIGTERM)
    try:p.wait(timeout=5)
    except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
   raise
  entry['returncode']=p.returncode
 checks[label]=p.returncode==0 and not entry.get('timeout')
 (OUT/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
 print(label,'PASS' if checks[label] else 'FAIL',flush=True)
 return checks[label]
with (W/'state/.measurement.lock').open('rb') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 assert os.getuid()!=0 and Path('/sys/kernel/sched_ext/state').read_text().strip()=='disabled'
 inc=['-I'+str(p) for p in [D/'overlay/tools/server',S/'tools/server',S/'common',S/'include',S/'ggml/include',S/'ggml/src',S/'tools/mtmd',S/'vendor',S]]
 link=['-L'+str(R),'-Wl,-rpath,'+str(R),'-lllama-common','-lllama','-lggml','-lggml-cpu','-lggml-base','-fopenmp','-pthread']
 prefix=['/usr/bin/c++','-std=c++17','-O2','-UNDEBUG',*inc]
 mask=['taskset','-c',','.join(map(str,case['cpus']))]
 if run([*prefix,'-DLLAMA_SCX_PHASE_HINT',D/'tests/pool-stress.cpp',*link,'-o',OUT/'pool-stress'],'compile-stress'):run([*mask,OUT/'pool-stress'],'stress')
 for mode,defs in [('off',[]),('hint',['-DLLAMA_SCX_PHASE_HINT']),('trace',['-DLLAMA_SCX_PHASE_HINT','-DLLAMA_SCX_PHASE_TRACE'])]:
  exe=OUT/('phase-'+mode)
  if run([*prefix,*defs,D/'tests/phase-modes.cpp',*link,'-o',exe],'compile-phase-'+mode):
   run([*mask,exe],'phase-'+mode)
   run(['nm','--defined-only',exe],'symbols-'+mode)
  run(['/usr/bin/c++','-std=c++17','-O0','-fsyntax-only','-DGGML_BACKEND_SHARED','-DGGML_SHARED','-DGGML_USE_CPU','-DLLAMA_SHARED','-DLLAMA_SUBPROCESS',*inc,*defs,D/'overlay/tools/server/server-context.cpp'],'context-'+mode,240)
  run(['/usr/bin/c++','-std=c++17','-O0','-fsyntax-only','-DGGML_BACKEND_SHARED','-DGGML_SHARED','-DGGML_USE_CPU','-DLLAMA_SHARED','-DLLAMA_SUBPROCESS',*inc,*defs,S/'tools/server/server-context.cpp'],'base-context-'+mode,240)
 for name in ['test-compute-profile.cpp','test-server-scx.cpp']:
  exe=OUT/Path(name).stem
  if run([*prefix,S/'tests'/name,*link,'-o',exe],'compile-'+Path(name).stem):run([*mask,exe],Path(name).stem)
 run(['patch','--dry-run','-p1','-d',S,'-i',D/'method.patch'],'patch-check')
 run(['/usr/bin/c++','--version'],'compiler-version')
 run(['ldd',OUT/'pool-stress'],'loaded-libraries')
 for mode in ['off','hint','trace']:
  p=OUT/('symbols-'+mode+'.stdout')
  if p.exists():
   text=p.read_text();checks['scalar-marker-'+mode]=('llama_scx_phase_v1' in text)==(mode!='off')
   checks['trace-marker-'+mode]=('llama_scx_decode_begin_v1' in text)==(mode=='trace')
   checks['no-v2-'+mode]='llama_scx_state_v2' not in text
 mapped=[]
 for line in ((OUT/'stress.stdout').read_text() if (OUT/'stress.stdout').exists() else '').splitlines():
  if not line.startswith('MAPPED_DSO\t'):continue
  path=Path(line.split('\t',1)[1]);mapped.append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
 checks['actual-dso-map']=bool(mapped) and any('libggml-cpu' in x['path'] for x in mapped) and any('libgomp' in x['path'] for x in mapped)
 for item in mapped:
  if Path(item['path']).name.startswith(('libggml','libllama')):checks['actual-dso-map'] &= Path(item['path']).resolve().is_relative_to(R)
 (OUT/'actual-loaded-libraries.json').write_text(json.dumps({'source':'/proc/self/maps inside successful unit process; not a model server','libraries':mapped},indent=2)+'\n')
 errors={x:re.findall(r"error: (.*)",(OUT/(x+'.stderr')).read_text()) for x in ['context-off','base-context-off']}
 inherited = not checks.get('context-off') and not checks.get('base-context-off') and bool(errors['context-off']) and errors['context-off']==errors['base-context-off'] and all('newa_resource' in x for x in errors['context-off'])
 gating={k:v for k,v in checks.items() if k not in ['context-off','base-context-off']}
 result={'status':('PASS_WITH_INHERITED_HINT_OFF_BUILD_FAILURE' if inherited else 'PASS') if all(gating.values()) and (inherited or (checks.get('context-off') and checks.get('base-context-off'))) else 'FAIL', 'hint_off_inherited_failure_confirmed':inherited,'checks':checks,'model_loaded':False,'BPF_loaded':False,'OpenMP':'Frozen actual NEW_A library; dynamic feature assertion','time':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 (OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)

raise SystemExit(1 if result["status"]=="FAIL" else 0)
