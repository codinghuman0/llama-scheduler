"""Identical HTTP workload with arm-specific Linux/selected-child admission."""
import http.client,os,signal,socket,threading,time
from pathlib import Path
from common import *
from base_visit import http_json
from selected_session import Session,check_privileges
import scheduler_evidence as se

def workers(pid,ext):
 rows={}
 for p in Path(f'/proc/{pid}/task').iterdir():
  try:rows[p.name]=dict(policy=os.sched_getscheduler(int(p.name)),affinity=sorted(os.sched_getaffinity(int(p.name))))
  except ProcessLookupError:continue
 assert rows and all(v['policy']==(7 if ext else 0) and v['affinity']==CPUS for v in rows.values()),'Wrong worker policy/envelope'
 return rows

def visit(case,fixture,folder,observed):
 guard();folder.mkdir();ext=case['scheduler']=='observe';command=list(case['server_argv']);env=dict(case['server_env'])
 if ext:check_privileges()
 with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
 command[command.index('--port')+1]=str(port)
 for p,h in {**case['artifacts'],**case['system_libraries']}.items():assert sha(p)==h
 save(folder/'launch.json',dict(argv=command,environment=env,cpus=CPUS,scheduler=case['scheduler']))
 save(folder/'request.json',fixture)
 def interrupted(signum,frame):raise TimeoutError('Signal/deadline/watchdog: '+str(signum))
 handlers={s:signal.signal(s,interrupted) for s in [signal.SIGTERM,signal.SIGINT,signal.SIGALRM]}
 signal.alarm(480);stop=threading.Event();thread=None;watch=[];result={}
 session=Session(folder,command,CPUS,[11],policy='E' if ext else 'C',topology=D/'inputs/topology.bin',env=env,diagnostics=ext,marker=Path(command[0]).parent/'libllama-server-impl.so',loader_binary=W/'scheduler/loader',child_binary=W/'scheduler/llama_scx_child')
 try:
  with session:
   pid=session.server['pid'];save(folder/'process.json',dict(pid=pid,starttime=session.server['starttime'],launcher_pid=session.process.pid))
   def monitor():
    while not stop.wait(.5):
     try:
      assert session.process.poll() is None,'Server/launcher exited'
      assert text('/sys/kernel/sched_ext/state')==('enabled' if ext else 'disabled'),'Unexpected detach/attach'
      assert os.sched_getscheduler(pid)==(7 if ext else 0),'Selected process fallback'
      if ext:
       assert session.loader.poll() is None,'Loader stopped'
       assert text('/sys/kernel/sched_ext/root/ops')=='llama_new_a','Wrong scheduler instance'
      watch.append(dict(ns=time.monotonic_ns(),status='PASS'))
     except Exception as e:
      watch.append(dict(ns=time.monotonic_ns(),status='FAIL',error=str(e)));os.kill(os.getpid(),signal.SIGALRM);return
   thread=threading.Thread(target=monitor,daemon=True);thread.start()
   try:
    deadline=time.monotonic()+90
    while True:
     assert session.process.poll() is None,'Server exited before ready'
     try:http_json(port,'/health',timeout=1);break
     except (OSError,AssertionError,http.client.HTTPException):
      assert time.monotonic()<deadline,'Ready timeout';time.sleep(.1)
    actual=Path(f'/proc/{pid}/cmdline').read_bytes().rstrip(b'\0').decode().split('\0');assert actual==command
    actual_env=dict(x.split('=',1) for x in Path(f'/proc/{pid}/environ').read_bytes().rstrip(b'\0').decode().split('\0'));assert actual_env==env
    mapped=sorted({line.split()[-1] for line in Path(f'/proc/{pid}/maps').read_text().splitlines() if '/' in line})
    loaded={p:sha(p) for p in mapped if Path(p).is_file() and ('.so' in Path(p).name or p==command[0])}
    aliases=verify_loaded(case,loaded);save(folder/'loaded-aliases.json',aliases)
    assert str(W/'models/model.gguf') in mapped
    save(folder/'runtime.json',dict(argv=actual,environment=actual_env,mapped=mapped,loaded_elf_sha256=loaded,affinity=sorted(os.sched_getaffinity(pid)),scheduler_state=text('/sys/kernel/sched_ext/state')))
    save(folder/'model-identity.json',dict(path=str(W/'models/model.gguf'),sha256=read(D/'protocol.json')['model_sha256'],inode=(W/'models/model.gguf').stat().st_ino,checked_before_campaign=True))
    save(folder/'worker-envelope.json',workers(pid,ext));guard(scheduler=ext)
    active=se.capture(folder,session) if ext else None
    save(folder/'props.json',http_json(port,'/props'))
    tok=[]
    for item,req in zip(fixture['items'],fixture['requests']):
     v=http_json(port,'/tokenize',dict(content=item['prompt'],add_special=True));assert v['tokens'][:fixture['input_token_cap']]==req['prompt'];tok.append(v)
    save(folder/'tokenization.json',tok)
    payload=dict(fixture['requests'][0],prompt=[r['prompt'] for r in fixture['requests']]);payload.pop('id_slot');save(folder/'atomic-payload.json',payload)
    for role in ['warmup','measured']:
     guard(scheduler=ext);values=observed(port,payload,role,pid,ext)
     save(folder/(role+'-http-body.json'),values);values=sorted(values,key=lambda v:v['index']);save(folder/(role+'-responses.json'),values)
     result[role]=[v['tokens'] for v in values]
     print(json.dumps(dict(event='COHORT_COMPLETE',role=role,arm=case['arm'],cohort=fixture['id'])),flush=True)
    if ext:
     final=se.sysfs();save(folder/'sched-ext-after-http.json',final)
     for k in ['/sys/kernel/sched_ext/enable_seq','/sys/kernel/sched_ext/root/ops','/sys/kernel/sched_ext/nr_rejected']:
      assert final.get(k)==active.get(k),('Scheduler instance/rejection changed',k)
    save(folder/'result.json',result)
   finally:
    stop.set()
    if thread:thread.join(2)
    save(folder/'watchdog.json',watch)
  assert session.process.returncode==0 and read(folder/'cleanup.json')['status']=='PASS'
  if ext:
   save(folder/'scheduler-audit.json',se.audit_stats(folder))
   from analyze import scheduler_checks
   scheduler_checks(folder)
  result['cleanup']=dict(returncode=session.process.returncode,sched_ext=text('/sys/kernel/sched_ext/state'))
  save(folder/'result.json',result);return result
 finally:
  stop.set();signal.alarm(0)
  for s,h in handlers.items():signal.signal(s,h)
