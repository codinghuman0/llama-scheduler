#!/usr/bin/env python3
"""Limited correctness repeats with immutable Linux runtimes. No throughput analysis."""
import fcntl,hashlib,http.client,json,os,re,shutil,signal,socket,subprocess,time,threading
from pathlib import Path
D=Path(__file__).resolve().parents[1];W=Path('/home/codinghuman/projects')
def read(p):return json.loads(p.read_text())
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def http_json(port,path,payload=None,timeout=180):
 c=http.client.HTTPConnection('127.0.0.1',port,timeout=timeout)
 try:
  c.request('GET' if payload is None else 'POST',path,None if payload is None else json.dumps(payload).encode(),{'Content-Type':'application/json'})
  r=c.getresponse();raw=r.read();assert r.status==200,(path,r.status,raw[:200]);return json.loads(raw)
 finally:c.close()
def temperatures():
 out={}
 for d in Path('/sys/class/hwmon').glob('hwmon*'):
  try:name=(d/'name').read_text().strip()
  except OSError:continue
  for p in d.glob('temp*_input'):
   try:out[name+':'+p.name]=int(p.read_text())/1000
   except OSError:pass
 return out
def guard():
 assert os.getuid()!=0 and Path('/sys/kernel/sched_ext/state').read_text().strip()=='disabled'
 assert shutil.disk_usage(W).free>=512*1024**2
 assert int(re.search(r'MemAvailable:\s+(\d+)',Path('/proc/meminfo').read_text())[1])>=3000000
 assert temperatures().get('k10temp:temp1_input',100)<85

def visit(case,fixture,folder,diagnostic=None):
 guard();folder.mkdir();command=list(case['server_argv']);env=dict(case['server_env'])
 with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
 command[command.index('--port')+1]=str(port)
 if diagnostic is not None:
  config=dict(diagnostic['config'],output=str(folder),role_file=str(folder/'diagnostic-role.txt'))
  save(folder/'diagnostic-config.json',config)
  env.update(LD_PRELOAD=diagnostic['overlay'],NEWA_DIAG_CONFIG=str(folder/'diagnostic-config.json'))
  assert sha(diagnostic['overlay'])==diagnostic['overlay_sha256']
  for extra,digest in diagnostic.get('extra_overlays',{}).items():
   assert sha(extra)==digest;env['LD_PRELOAD']+=':'+extra
  if diagnostic.get('extra_overlays'):env['NEWA_Q4_PROBE_OUTPUT']=str(folder/'operator-probe.json')
 for p,h in case['artifacts'].items():assert sha(p)==h,p
 save(folder/'request.json',fixture);save(folder/'launch.json',dict(argv=command,environment=env,cpus=[0,2,4,6,8,10],temperature_before=temperatures(),scope='correctness only'))
 proc=None;timer=None;result={}
 def interrupted(signum,frame):raise KeyboardInterrupt('diagnostic interrupted')
 handlers={sig:signal.signal(sig,interrupted) for sig in [signal.SIGTERM,signal.SIGINT]}
 try:
  with (folder/'server.stdout.log').open('w') as stdout,(folder/'server.stderr.log').open('w') as stderr:
   proc=subprocess.Popen(['/usr/bin/taskset','-c','0,2,4,6,8,10',*command],env=env,stdout=stdout,stderr=stderr,start_new_session=True)
   save(folder/'process.json',dict(pid=proc.pid,owned_process_group=proc.pid))
   def expired():
    if proc.poll() is None:os.killpg(proc.pid,signal.SIGKILL)
   timer=threading.Timer(480,expired);timer.daemon=True;timer.start()
   deadline=time.monotonic()+90
   while True:
    assert proc.poll() is None,'Server exited before ready'
    try:http_json(port,'/health',timeout=1);break
    except (OSError,AssertionError,http.client.HTTPException):
     assert time.monotonic()<deadline,'Ready timeout';time.sleep(.1)
   pid=proc.pid;actual=Path(f'/proc/{pid}/cmdline').read_bytes().rstrip(b'\0').decode().split('\0');assert actual==command
   actual_env=dict(x.split('=',1) for x in Path(f'/proc/{pid}/environ').read_bytes().rstrip(b'\0').decode().split('\0'));assert actual_env==env
   mapped=sorted({line.split()[-1] for line in Path(f'/proc/{pid}/maps').read_text().splitlines() if '/' in line})
   loaded={p:sha(p) for p in mapped if Path(p).is_file() and ('.so' in Path(p).name or p==command[0])};assert all(loaded.get(p)==h for p,h in case['artifacts'].items())
   save(folder/'runtime.json',dict(argv=actual,environment=actual_env,mapped=mapped,loaded_elf_sha256=loaded,affinity=sorted(os.sched_getaffinity(pid)),scheduler_state=Path('/sys/kernel/sched_ext/state').read_text().strip()))
   save(folder/'props.json',http_json(port,'/props'))
   tok=[]
   for item,req in zip(fixture['items'],fixture['requests']):
    v=http_json(port,'/tokenize',dict(content=item['prompt'],add_special=True));assert v['tokens'][:fixture['input_token_cap']]==req['prompt'];tok.append(v)
   save(folder/'tokenization.json',tok)
   requests=fixture['requests'];payload=dict(requests[0],prompt=[r['prompt'] for r in requests]);payload.pop('id_slot');save(folder/'atomic-payload.json',payload)
   for role in ['warmup','measured']:
    if diagnostic is not None:(folder/'diagnostic-role.txt').write_text(role+'\n')
    guard();values=http_json(port,'/completion',payload)
    save(folder/(role+'-http-body.json'),values)
    if isinstance(values,dict) and len(requests)==1:values=[values]
    assert isinstance(values,list) and sorted(v['index'] for v in values)==list(range(len(requests)));values.sort(key=lambda v:v['index'])
    save(folder/(role+'-responses.json'),values)
    for v,r in zip(values,requests):
     assert len(v['tokens'])==v['tokens_predicted']==r['n_predict']==128
     assert v['tokens_evaluated']==v['timings']['prompt_n']==len(r['prompt']) and v['timings']['cache_n']==0
     assert v['generation_settings']['temperature']==0 and v['generation_settings']['seed']==424242
    result[role]=[v['tokens'] for v in values]
    print(json.dumps(dict(event='COHORT_COMPLETE',run=folder.name,role=role,requests=len(requests),scope='correctness_not_performance')),flush=True)
   assert Path('/sys/kernel/sched_ext/state').read_text().strip()=='disabled'
   return result
 finally:
  if timer:timer.cancel()
  if proc and proc.poll() is None:
   os.killpg(proc.pid,signal.SIGTERM)
   try:proc.wait(timeout=15)
   except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=5)
  for sig,handler in handlers.items():signal.signal(sig,handler)
  save(folder/'cleanup.json',dict(status='PASS' if proc is None or proc.poll() is not None else 'FAIL',owned_pid=None if proc is None else proc.pid,returncode=None if proc is None else proc.returncode,temperature_after=temperatures(),scheduler_state=Path('/sys/kernel/sched_ext/state').read_text().strip()))

def main():
 protocol=read(D/'protocol-and-identity.json');fixtures=read(D/'evidence/fixtures.json');summary=[]
 guard();os.sched_setaffinity(0,{11})
 for p in Path('/proc').iterdir():
  if p.name.isdigit():
   try:assert (p/'comm').read_text().strip() not in ['llama-server','llama-bench','cc1plus','cmake','ninja'],('Competing process',p.name)
   except OSError:pass
 with (W/'new-a-runs/.measurement.lock').open('r') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  for fixture in fixtures:
   seen={'B0':0,'B1':0};previous={}
   for arm in ['B0','B1','B1','B0']:
    seen[arm]+=1;folder=D/'runs'/f'reproduce-{fixture["id"]}-{arm}-r{seen[arm]}'
    result=visit(protocol['cases'][arm],fixture,folder)
    original=read(D/'evidence'/f'original-{fixture["id"]}-{arm}.json');oracle=[r['response']['tokens'] for r in original]
    item=dict(run=folder.name,cohort=fixture['id'],arm=arm,repeat=seen[arm],within_server_equal=result['warmup']==result['measured'],equals_original=result['measured']==oracle,equals_prior_fresh=None if arm not in previous else result['measured']==previous[arm],different_original_request_indices=[i for i,(a,b) in enumerate(zip(result['measured'],oracle)) if a!=b])
    previous[arm]=result['measured'];summary.append(item);save(D/'evidence/fresh-reproduction-summary.json',dict(status='IN_PROGRESS',visits=summary));print(json.dumps(item),flush=True)
  save(D/'evidence/fresh-reproduction-summary.json',dict(status='COMPLETE',visits=summary,scope='Limited correctness repetitions only; no throughput inference'))
  with (D/'ledger.jsonl').open('a') as log:log.write(json.dumps(dict(id='D01',hypothesis='Frozen B0/B1 outputs repeat within each runtime under original atomic cohort',change='None; only ephemeral localhost port and separate output directory',input='2 heldout cohorts x 2 runtimes x 2 fresh servers, each warmup/measured',observation=summary,next='If stable, instrument earliest differing model call; otherwise isolate grouping/arrival variability'),ensure_ascii=False)+'\n')
if __name__=='__main__':main()
