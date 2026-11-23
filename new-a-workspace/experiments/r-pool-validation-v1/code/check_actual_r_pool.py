from pathlib import Path
import datetime,fcntl,hashlib,json,os,resource,signal,subprocess
D=Path(__file__).resolve().parents[1];W=D.parents[1];S=W/'src/llama';O=D.parent/'persistent-pool-port-v1';R=D/'candidates/R/runtime';OUT=D/'results/actual-R-pool-units'
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
assert json.loads((D/'gate-results.json').read_text())['R']=='COMPATIBLE_IN_TESTED_SCOPE'
with (W/'state/.measurement.lock').open('r') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);OUT.mkdir(exist_ok=False)
 commands=[];env=json.loads((D/'cases.json').read_text())['R']['server_env'];env=dict(env,LD_LIBRARY_PATH=str(R))
 def run(argv,label):
  rec=dict(argv=list(map(str,argv)),environment=env,label=label,timeout_s=180);commands.append(rec);save(OUT/'commands.json',commands)
  with (OUT/(label+'.stdout')).open('w') as stdout,(OUT/(label+'.stderr')).open('w') as stderr:
   proc=subprocess.Popen(rec['argv'],env=env,stdout=stdout,stderr=stderr,start_new_session=True)
   try:proc.wait(timeout=180)
   except BaseException:
    if proc.poll() is None:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
    raise
  rec['returncode']=proc.returncode;save(OUT/'commands.json',commands);assert proc.returncode==0,label;print(label,'PASS',flush=True)
 includes=['-I'+str(p) for p in [O/'overlay/tools/server',S/'tools/server',S/'common',S/'include',S/'ggml/include',S/'ggml/src',S/'vendor',S]]
 link=['-L'+str(R),'-Wl,-rpath,'+str(R),'-lllama-common','-lllama','-lggml','-lggml-cpu','-lggml-base','-fopenmp','-pthread']
 for name in ['test-server-threadpool','pool-stress','phase-modes']:
  run(['/usr/bin/c++','-std=c++17','-O2','-UNDEBUG','-DLLAMA_SCX_PHASE_HINT',*includes,O/'tests'/(name+'.cpp'),*link,'-o',OUT/name],'compile-'+name)
  run(['/usr/bin/taskset','-c','0,2,4,6,8,10',OUT/name],'run-'+name)
 run(['/usr/bin/c++','-shared','-fPIC','-std=c++17','-O1','-Wall','-Wextra','-Werror','-I'+str(S/'ggml/include'),D/'code/pool-observer.cpp','-ldl','-pthread','-o',D/'build-server/pool-observer.so'],'compile-observer')
 mapped=[]
 for line in (OUT/'run-pool-stress.stdout').read_text().splitlines():
  if line.startswith('MAPPED_DSO\t'):
   path=Path(line.split('\t',1)[1]);mapped.append(dict(path=str(path),sha256=sha(path)))
 cpu=next(x for x in mapped if 'libggml-cpu' in x['path']);assert cpu['sha256']==sha(R/'libggml-cpu.so')
 result=dict(status='PASS',scope='Prepared ownership tests rerun against actual validated R CPU: registry ABI, shared/separate5/6 graph reuse, abort recovery, repeated error cleanup, scalar phase transport. Not model lifecycle proof.',actual_loaded_libraries=mapped,source_hashes={str(O/'tests'/(n+'.cpp')):sha(O/'tests'/(n+'.cpp')) for n in ['test-server-threadpool','pool-stress','phase-modes']},observer_sha256=sha(D/'build-server/pool-observer.so'),inherited_hint_off='Previous documented newa_resource undeclared failure remains; not fixed, full matrix not claimed')
 save(OUT/'result.json',result)
 with (D/'ledger.jsonl').open('a') as f:f.write(json.dumps(dict(time=datetime.datetime.now(datetime.timezone.utc).isoformat(),stage='actual-R-pool-units',status='PASS'))+'\n')
 print('Actual R pool units and separate model observer ready',flush=True)
