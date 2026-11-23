from pathlib import Path
import json,os,hashlib,subprocess,fcntl,datetime,signal
D=Path(__file__).resolve().parents[1];W=D.parents[1];S=W/'src/llama';R=W/'runtime/NEW_A';OUT=D/'results/model-free-1';OUT.mkdir(exist_ok=False)
config=json.loads((W/'config/arms.json').read_text())['C'];env=dict(config['env']);env['LD_LIBRARY_PATH']=str(R);env['GGML_NEWA_POOL']='off'
commands=[]
def run(argv,label,limit=120):
 record={'argv':list(map(str,argv)),'cwd':str(D),'env':env,'timeout_s':limit};commands.append(record)
 (OUT/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
 with (OUT/(label+'.stdout')).open('w') as out,(OUT/(label+'.stderr')).open('w') as err:
  p=subprocess.Popen(record['argv'],cwd=D,env=env,stdout=out,stderr=err,start_new_session=True)
  try:p.wait(timeout=limit)
  except subprocess.TimeoutExpired:
   os.killpg(p.pid,signal.SIGTERM)
   try:p.wait(timeout=5)
   except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
   record['timed_out']=True
  record['returncode']=p.returncode
 (OUT/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
 return record['returncode']==0 and not record.get('timed_out')
with (W/'state/.measurement.lock').open('rb') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 assert os.getuid()!=0 and Path('/sys/kernel/sched_ext/state').read_text().strip()=='disabled'
 includes=['-I'+str(p) for p in [D/'overlay/tools/server',S/'common',S/'include',S/'ggml/include',S/'ggml/src',S/'vendor']]
 link=['-L'+str(R),'-Wl,-rpath,'+str(R),'-lllama-common','-lllama','-lggml','-lggml-cpu','-lggml-base','-fopenmp','-pthread']
 passed=run(['/usr/bin/c++','-std=c++17','-O2','-UNDEBUG',*includes,D/'tests/test-server-threadpool.cpp',*link,'-o',OUT/'test-server-threadpool'],'compile-owner')
 if passed:passed=run(['taskset','-c',','.join(map(str,config['cpus'])),OUT/'test-server-threadpool'],'owner-and-graphs')
 (OUT/'result.json').write_text(json.dumps({'status':'PASS' if passed else 'FAIL','scope':'Donor ownership tests plus actual frozen OpenMP DSOs, shared5/separate5/6, poll50; no model','commands':commands,'time':datetime.datetime.now(datetime.timezone.utc).isoformat()},indent=2)+'\n')
 print(json.dumps({'status':'PASS' if passed else 'FAIL','results':str(OUT)}))
