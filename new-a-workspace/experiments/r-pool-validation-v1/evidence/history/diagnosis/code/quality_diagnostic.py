#!/usr/bin/env python3
"""Bounded format/EOS/length/sampling diagnosis; never a throughput experiment."""
import collections,contextlib,fcntl,json,os,signal,socket,subprocess,threading,time
from pathlib import Path
import reproduce_frozen as r
D=r.D;W=r.W
PLAN=dict(revision='v2-correct-BOS',template_rule='Use /apply-template then /tokenize(add_special=True,parse_special=True); verify exactly one BOS151646. Initial v1 aborted and retained separately.',scope='Separate single-request quality diagnosis; not the original eight-request performance workload',prompts=['h1-a','h1-h'],arms=['B0','B1'],conditions=[dict(id='Q0-raw',template=False,ignore_eos=True,n_predict=128,temperature=0),dict(id='Q1-template',template=True,ignore_eos=True,n_predict=128,temperature=0),dict(id='Q2-eos',template=True,ignore_eos=False,n_predict=128,temperature=0),dict(id='Q3-length',template=True,ignore_eos=False,n_predict=512,temperature=0),dict(id='Q4-temperature',template=True,ignore_eos=False,n_predict=512,temperature=.6)],seed=424242,criteria=dict(repeated_token_6gram='flag if any contiguous generated-token 6gram occurs at least3 times; report fraction of windows beyond first occurrence',completion='report stop_type, stopped_eos, stopped_limit, generated tokens and presence of </think>; EOS alone is not task success',manual='For garden: actionable water allocation/monitoring and dry-week example. For noise: aggregation that retains spikes, calibration/placement/missing/time-of-day and pre/post comparison. Record substantive answer/constraint contradiction/unanswered content without inferring general quality from two prompts.'),limits=dict(requests=20,max_generated_tokens=5632,http_timeout_s=180,per_server_watchdog_s=600),rule='Each adjacent condition changes one factor; same prompt text, no prompt/KV reuse, seed and runtime resource settings retained. Never replace original evidence.')
@contextlib.contextmanager
def server(case,folder):
 r.guard();folder.mkdir();cmd=list(case['server_argv']);env=dict(case['server_env']);proc=None;timer=None
 with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
 cmd[cmd.index('--port')+1]=str(port)
 for p,h in case['artifacts'].items():assert r.sha(p)==h
 r.save(folder/'launch.json',dict(argv=cmd,env=env,scope=PLAN['scope']))
 def interrupted(signum,frame):raise KeyboardInterrupt('diagnostic interrupted')
 handlers={s:signal.signal(s,interrupted) for s in [signal.SIGTERM,signal.SIGINT]}
 try:
  with (folder/'server.stdout.log').open('w') as out,(folder/'server.stderr.log').open('w') as err:
   proc=subprocess.Popen(['/usr/bin/taskset','-c','0,2,4,6,8,10',*cmd],env=env,stdout=out,stderr=err,start_new_session=True)
   r.save(folder/'process.json',dict(pid=proc.pid,owned_process_group=proc.pid))
   def expired():
    if proc.poll() is None:os.killpg(proc.pid,signal.SIGKILL)
   timer=threading.Timer(600,expired);timer.daemon=True;timer.start();deadline=time.monotonic()+90
   while True:
    assert proc.poll() is None
    try:r.http_json(port,'/health',timeout=1);break
    except (OSError,AssertionError):assert time.monotonic()<deadline;time.sleep(.1)
   paths={line.split()[-1] for line in Path(f'/proc/{proc.pid}/maps').read_text().splitlines() if '/' in line}
   hashes={p:r.sha(p) for p in paths if Path(p).is_file() and ('.so' in Path(p).name or p==cmd[0])}
   assert all(hashes.get(p)==h for p,h in case['artifacts'].items())
   r.save(folder/'runtime.json',dict(loaded_elf_sha256=hashes,affinity=sorted(os.sched_getaffinity(proc.pid)),scheduler_state=Path('/sys/kernel/sched_ext/state').read_text().strip()))
   yield port
 finally:
  if timer:timer.cancel()
  if proc and proc.poll() is None:
   os.killpg(proc.pid,signal.SIGTERM)
   try:proc.wait(timeout=15)
   except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=5)
  for s,h in handlers.items():signal.signal(s,h)
  r.save(folder/'cleanup.json',dict(status='PASS' if proc is None or proc.poll() is not None else 'FAIL',returncode=None if proc is None else proc.returncode,temperature_after=r.temperatures()))
def stats(value):
 tok=value['tokens'];windows=[tuple(tok[i:i+6]) for i in range(max(0,len(tok)-5))];counts=collections.Counter(windows)
 return dict(tokens=len(tok),max_6gram_occurrences=max(counts.values(),default=0),repetition_flag=max(counts.values(),default=0)>=3,repeated_6gram_window_fraction=(len(windows)-len(counts))/max(1,len(windows)),think_close_present='</think>' in value['content'],stop_type=value.get('stop_type'),stopped_eos=value.get('stopped_eos'),stopped_limit=value.get('stopped_limit'),content=value['content'])
def main():
 root=D/'quality-v2';root.mkdir(exist_ok=False);r.save(root/'protocol.json',PLAN)
 with (D/'ledger.jsonl').open('a') as f:f.write(json.dumps(dict(id='Q00v2',status='REGISTERED_BEFORE_RUN',protocol=str(root/'protocol.json'),hypothesis='Raw format/EOS suppression/short limit/greedy sampling may each limit useful answers; separate from numerical divergence'))+'\n')
 protocol=r.read(D/'protocol-and-identity.json');fixture=r.read(D/'evidence/fixtures.json')[0];result=[];tokenizations={}
 os.sched_setaffinity(0,{11})
 with (W/'new-a-runs/.measurement.lock').open('r') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  for arm in PLAN['arms']:
   folder=root/arm
   with server(protocol['cases'][arm],folder) as port:
    for condition in PLAN['conditions']:
     for idx in [0,7]:
      r.guard();item=fixture['items'][idx];name=condition['id']+'-'+item['id']
      if condition['template']:
       rendered=r.http_json(port,'/apply-template',dict(messages=[dict(role='user',content=item['prompt'])]))
       tokenized=r.http_json(port,'/tokenize',dict(content=rendered['prompt'],add_special=True,parse_special=True));tokens=tokenized['tokens'];assert tokens[0]==fixture['requests'][idx]['prompt'][0]==151646 and tokens.count(151646)==1
       r.save(folder/(name+'-template.json'),dict(rendered=rendered,tokenized=tokenized))
      else:tokens=fixture['requests'][idx]['prompt']
      key=(condition['id'],idx)
      if arm=='B0':tokenizations[key]=tokens
      else:assert tokenizations[key]==tokens
      assert len(tokens)+condition['n_predict']<1024
      payload=dict(fixture['requests'][idx],prompt=tokens,n_predict=condition['n_predict'],temperature=condition['temperature'],ignore_eos=condition['ignore_eos'],id_slot=0)
      r.save(folder/(name+'-request.json'),payload);v=r.http_json(port,'/completion',payload);r.save(folder/(name+'-response.json'),v)
      assert v['timings']['cache_n']==0 and v['tokens_evaluated']==len(tokens)
      row=dict(arm=arm,condition=condition['id'],prompt=item['id'],input_tokens=len(tokens),**stats(v));result.append(row);r.save(root/'summary.json',dict(status='IN_PROGRESS',rows=result))
      print(json.dumps({k:v for k,v in row.items() if k!='content'}),flush=True)
  r.save(root/'summary.json',dict(status='COMPLETE',rows=result,scope=PLAN['scope'],input_tokens_equal_across_arms=True))
 with (D/'ledger.jsonl').open('a') as f:f.write(json.dumps(dict(id='Q01v2',status='COMPLETE',results=str(root/'summary.json'),next='Manual evaluation using preregistered criteria; no general quality guarantee'))+'\n')
if __name__=='__main__':main()
