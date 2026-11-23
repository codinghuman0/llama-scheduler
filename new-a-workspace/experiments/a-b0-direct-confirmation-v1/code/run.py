"""Serial B0/A admission and fixed confirmation. Never mutate runtime inputs."""
import argparse,copy,fcntl,json,os,re,sys,time
from contextlib import nullcontext
from pathlib import Path
sys.dont_write_bytecode=True
import base_visit as base
import contention
import prefill_pressure_evidence as pressure
from common import *
base.sha=sha
base.guard=guard

def worker_snapshot(pid):
 rows={}
 for p in Path(f'/proc/{pid}/task').iterdir():
  try:rows[p.name]=dict(affinity=sorted(os.sched_getaffinity(int(p.name))),policy=os.sched_getscheduler(int(p.name)))
  except ProcessLookupError:continue
 assert rows and all(r['affinity']==CPUS and r['policy']==0 for r in rows.values()),'Worker envelope'
 return rows

def check_body(body,fixture,oracle):
 rows=body if isinstance(body,list) else [body]
 assert len(rows)==8 and sorted(x['index'] for x in rows)==list(range(8))
 rows=sorted(rows,key=lambda x:x['index'])
 for v,r,t in zip(rows,fixture['requests'],oracle):
  assert v['tokens']==t and len(v['tokens'])==v['tokens_predicted']==128,'Output mismatch'
  assert v['tokens_evaluated']==v['timings']['prompt_n']==len(r['prompt']) and v['timings']['cache_n']==0,'Prompt/cache mismatch'
  assert v['generation_settings']['temperature']==0 and v['generation_settings']['seed']==424242
 return rows

def execute(spec,folder,cases,fixture,performance):
 folder.mkdir();no_model_process();before_visit=guard();save(folder/'environment-before.json',before_visit)
 case=copy.deepcopy(cases[spec['arm']]);case['scope']='A/B0_CONFIRMATION' if performance else 'SMOKE_NOT_PERFORMANCE'
 oracle=read(D/f'inputs/oracle-{fixture["id"]}.json')['measured'];samples=[]
 ctx=contention.ControlledLoad(folder/'controlled-load',10) if spec['condition']=='cpu25' else nullcontext(None)
 server=folder/'server';original_http=base.http_json
 try:
  with ctx as load:
   if load:time.sleep(.5)
   def observed(port,path,payload=None,timeout=180):
    if path!='/completion':return original_http(port,path,payload,timeout)
    role='warmup' if not samples else 'measured';pid=read(server/'process.json')['pid']
    runtime=read(server/'runtime.json');expected={**case['artifacts'],**case['system_libraries']}
    aliases=verify_loaded(case,runtime['loaded_elf_sha256'])
    save(folder/'loaded-ELF-aliases.json',aliases)
    env_before=guard();workers_before=worker_snapshot(pid)
    before=contention.read_process(pid);lb=load.snapshot() if load else None
    start=time.monotonic_ns();body=original_http(port,path,payload,timeout);end=time.monotonic_ns()
    after=contention.read_process(pid);la=load.snapshot() if load else None
    env_after=environment();workers_after=worker_snapshot(pid)
    save(folder/(role+'-http-raw.json'),body)
    wall=(end-start)/1e9;cpu=(after['cpu_ticks']-before['cpu_ticks'])/before['tick_hz']
    sample=dict(role=role,start_ns=start,end_ns=end,cohort_http_wall_s=wall,server_before=before,server_after=after,cpu_time_s=cpu,environment_before=env_before,environment_after=env_after,workers_before=workers_before,workers_after=workers_after)
    if load:sample.update(load_before=lb,load_after=la,controlled_load=contention.metrics(lb,la,wall))
    samples.append(sample);save(folder/'http-observations.json',samples)
    for k in ['pid','starttime','tick_hz','affinity','policy']:assert before[k]==after[k],k
    assert before['affinity']==CPUS and before['policy']==0
    rows=check_body(body,fixture,oracle);tokens=sum(len(v['tokens']) for v in rows)
    sample.update(actual_generated_tokens=tokens,throughput=tokens/wall,cpu_seconds_per_token=cpu/tokens,per_request_timings=[v['timings'] for v in rows])
    save(folder/'http-observations.json',samples);guard(env_after)
    if role=='measured' and load:assert .22<=sample['controlled_load']['mean_cpu_cores']<=.28,'cpu25 outside admission range'
    return body
   base.http_json=observed
   outputs=base.visit(case,fixture,server)
  assert len(samples)==2 and outputs['warmup']==outputs['measured']==oracle
  assert read(server/'cleanup.json')['status']=='PASS' and read(server/'cleanup.json')['returncode']==0,'Server cleanup'
  log=(server/'server.stderr.log').read_text();policy=pressure.validate(log,'pressure' if spec['arm']=='A' else 'off');save(folder/'policy-recomputed.json',policy)
  teams=sorted({int(x) for x in re.findall(r'NEWA_TEAM pid=\d+ team=(\d+)',log)})
  assert teams and set(teams)<={5,6},('Unexpected OpenMP team',teams)
  measured=samples[1];selected=[];decisions=None
  if spec['arm']=='A':
   selected=[e for e in policy['epochs'] if measured['start_ns']<=e['first_decode_ns']<=measured['end_ns']]
   assert selected,'Missing measured E epoch'
   decisions=[[sum(e['decisions_5_6'][p][j] for e in selected) for j in range(2)] for p in range(4)]
   required={5+j for j in range(2) if any(row[j] for row in decisions)}
   assert required<=set(teams),('Submitted vs actual teams',required,teams)
  after_visit=guard();save(folder/'environment-after.json',after_visit)
  result=dict(spec=spec,status='VALID',token_equality=True,performance=performance,metrics=measured,actual_OpenMP_teams=teams,measured_E_epochs=selected,measured_E_decisions_5_6=decisions,TTFT='NOT_MEASURED',counter_scope='proc snapshots bracket HTTP clock; CPU seconds is not energy')
  save(folder/'result.json',result);return result
 finally:base.http_json=original_http

def progress(root,plan,completed,status,failed=None):
 done={x['ordinal'] for x in completed};remaining=[dict(spec=s,status='NOT_RUN') for s in plan if s['ordinal'] not in done and (failed is None or s['ordinal']!=failed['spec']['ordinal'])]
 save(root/'campaigns.json',dict(status=status,completed=completed,failed=failed,not_run=remaining,planned_visits=len(plan),extra_pairs=0,seal_sha256=sha(D/'seal.json')))
 (D/'GOAL_STATE.md').write_text('# A/B0 direct confirmation\n\nStatus: '+status+'\n\nRun: '+root.name+'; completed visits '+str(len(completed))+'/'+str(len(plan))+'.\nLast completed: '+(str(completed[-1]) if completed else 'none')+'\nNext planned: '+(str(remaining[0]) if remaining else 'none')+'\nSeal SHA256: '+sha(D/'seal.json')+'\nResume: inspect process.json and active handle; do not restart or replace a partial visit. If terminal failure, analyze preserved raw and report INCOMPLETE_INVALID; a new campaign requires new registration.\n')

def main():
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['smoke','full']);p.add_argument('--name',required=True);args=p.parse_args()
 assert re.fullmatch(r'[A-Za-z0-9_-]+',args.name)
 root=D/'results'/args.name;assert not root.exists(),'New namespace required'
 with (W/'state/.measurement.lock').open('r') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);no_model_process();guard();verify_inputs();os.sched_setaffinity(0,{11})
  if args.mode=='full':assert read(D/'evidence/smoke-admission.json')['status']=='PASS'
  root.mkdir();save(root/'process.json',dict(pid=os.getpid(),starttime=contention.read_process(os.getpid())['starttime'],mode=args.mode,seal_sha256=sha(D/'seal.json'),started=now()))
  cases=read(D/'cases.json');fixtures={f['id']:f for f in read(D/'fixtures.json')}
  plan=read(D/'order.json') if args.mode=='full' else [dict(ordinal=i+1,campaign=0,condition='ambient',block=i//2+1,cohort=fid,arm=arm,arm_order=['B0','A']) for i,(fid,arm) in enumerate((f,a) for f in ['heldout-1','heldout-2'] for a in ['B0','A'])]
  save(root/'plan.json',plan);completed=[];progress(root,plan,completed,'RUNNING')
  for spec in plan:
   campaign=root/f'campaign-{spec["campaign"]}';campaign.mkdir(exist_ok=True)
   folder=campaign/f'{spec["condition"]}-b{spec["block"]:02}-{spec["arm"]}'
   event('visit-start',run=args.name,spec=spec)
   try:result=execute(spec,folder,cases,fixtures[spec['cohort']],args.mode=='full')
   except BaseException as exc:
    failure=dict(spec=spec,type=type(exc).__name__,message=str(exc),time=now())
    if folder.exists():save(folder/'failure.json',failure)
    progress(root,plan,completed,'STOPPED_INVALID',failure);event('visit-failure',run=args.name,**failure);raise
   completed.append(dict(**spec,path=str(folder.relative_to(D)),status='VALID'));progress(root,plan,completed,'RUNNING');event('visit-complete',run=args.name,spec=spec,valid=True)
   print(json.dumps(dict(event='VISIT_COMPLETE',spec=spec,valid=True,completed=len(completed),planned=len(plan))),flush=True)
  verify_inputs();no_model_process();guard();progress(root,plan,completed,'COMPLETE')
  if args.mode=='smoke':save(D/'evidence/smoke-admission.json',dict(status='PASS',run=args.name,visits=completed,seal_sha256=sha(D/'seal.json'),scope='Not performance data'))
  event('run-complete',run=args.name,mode=args.mode,visits=len(completed));print('COMPLETE '+args.name,flush=True)
if __name__=='__main__':main()
