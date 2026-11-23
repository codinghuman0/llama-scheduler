from pathlib import Path
import datetime,fcntl,hashlib,json,os,re,signal,subprocess
D=Path(__file__).resolve().parents[1];W=D.parents[1];R=D/'candidates/R-diagnostic/runtime';out=D/'results/route-synthetic'
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
with (W/'state/.measurement.lock').open('r') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);out.mkdir(exist_ok=False)
 assert os.getuid()!=0
 argv=['/usr/bin/c++','-std=c++17','-O2','-UNDEBUG',str(D/'code/route-probe.cpp'),'-L'+str(R),'-Wl,-rpath,'+str(R),'-lggml-cpu','-o',str(out/'route-probe')]
 records=[]
 for label,command,env in [('compile',argv,dict(os.environ)),('run',['/usr/bin/taskset','-c','0,2,4,6,8,10',str(out/'route-probe')],dict(PATH='/usr/bin:/bin',LC_ALL='C',LD_LIBRARY_PATH=str(R),GGML_NEWA_Q4_TILE32='phase_batch'))]:
  record=dict(label=label,argv=command,environment={k:v for k,v in env.items() if k in ['PATH','LC_ALL','LD_LIBRARY_PATH','GGML_NEWA_Q4_TILE32']});records.append(record)
  with (out/(label+'.stdout')).open('w') as stdout,(out/(label+'.stderr')).open('w') as stderr:
   proc=subprocess.Popen(command,env=env,stdout=stdout,stderr=stderr,start_new_session=True)
   try:proc.wait(timeout=60)
   except BaseException:
    if proc.poll() is None:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
    raise
  record['returncode']=proc.returncode;save(out/'commands.json',records);assert proc.returncode==0,label
 text=(out/'run.stderr').read_text()
 ref=list(map(int,re.search(r'NEWA_R_REFERENCE_BODY calls=(\d+)/(\d+)/(\d+)/(\d+)',text).groups()))
 exact=list(map(int,re.search(r'NEWA_Q4_TILE32 stats worker0_calls=(\d+)/(\d+)/(\d+)/(\d+)',text).groups()))
 assert ref==[1,2,1,1] and exact==[0,0,3,3],(ref,exact)
 result=dict(status='PASS',reference_body_by_phase=ref,exact_q4_by_phase=exact,scope='Separate route test; zero quantized buffers only validate finite output and control flow, not general arithmetic correctness',CPU_DSO_sha256=sha(R/'libggml-cpu.so'),source_sha256=sha(D/'code/route-probe.cpp'))
 save(out/'result.json',result);print(json.dumps(result))
 with (D/'ledger.jsonl').open('a') as log:log.write(json.dumps(dict(time=datetime.datetime.now(datetime.timezone.utc).isoformat(),stage='R-route-synthetic',**result))+'\n')
