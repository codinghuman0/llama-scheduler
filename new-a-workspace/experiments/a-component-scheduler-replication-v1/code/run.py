"""One preregistered replication campaign; stop on any invalid visit."""
import argparse,copy,fcntl,json,os,re,sys,time
from contextlib import nullcontext
from pathlib import Path
sys.dont_write_bytecode=True
from common import *
import visit,contention,prefill_pressure_evidence as pressure

def check_body(body,fixture,oracle):
 assert isinstance(body,list) and len(body)==8 and sorted(x['index'] for x in body)==list(range(8))
 rows=sorted(body,key=lambda x:x['index'])
 for v,r,t in zip(rows,fixture['requests'],oracle):
  assert v['tokens']==t and len(v['tokens'])==v['tokens_predicted']==128,'Output mismatch'
  assert v['tokens_evaluated']==v['timings']['prompt_n']==len(r['prompt']) and v['timings']['cache_n']==0,'Prompt/cache mismatch'
  assert v['generation_settings']['temperature']==0 and v['generation_settings']['seed']==424242
 return rows

def execute(spec,folder,cases,fixture,performance):
 folder.mkdir();no_model_process();save(folder/'environment-before.json',guard())
 case=copy.deepcopy(cases[spec['arm']]);case['arm']=spec['arm']
 oracle=read(D/f'inputs/oracle-{fixture["id"]}.json')['measured'];samples=[]
 ctx=contention.ControlledLoad(folder/'controlled-load',10) if spec['condition']=='cpu25' else nullcontext(None)
 server=folder/'server'
 with ctx as load:
  if load:time.sleep(.5)
  def observed(port,payload,role,pid,ext):
   env_before=guard(scheduler=ext);workers_before=visit.workers(pid,ext)
   before=contention.read_process(pid);lb=load.snapshot() if load else None
   start=time.monotonic_ns();body=visit.http_json(port,'/completion',payload);end=time.monotonic_ns()
   after=contention.read_process(pid);la=load.snapshot() if load else None
   env_after=environment();workers_after=visit.workers(pid,ext)
   save(folder/(role+'-http-raw.json'),body)
   wall=(end-start)/1e9;cpu=(after['cpu_ticks']-before['cpu_ticks'])/before['tick_hz']
   sample=dict(role=role,start_ns=start,end_ns=end,cohort_http_wall_s=wall,server_before=before,server_after=after,cpu_time_s=cpu,environment_before=env_before,environment_after=env_after,workers_before=workers_before,workers_after=workers_after)
   if load:sample.update(load_before=lb,load_after=la,controlled_load=contention.metrics(lb,la,wall))
   samples.append(sample);save(folder/'http-observations.json',samples)
   for k in ['pid','starttime','tick_hz','affinity','policy']:assert before[k]==after[k],k
   assert before['affinity']==CPUS and before['policy']==(7 if ext else 0)
   rows=check_body(body,fixture,oracle);tokens=sum(len(v['tokens']) for v in rows)
   sample.update(actual_generated_tokens=tokens,throughput=tokens/wall,cpu_seconds_per_token=cpu/tokens,per_request_timings=[v['timings'] for v in rows])
   save(folder/'http-observations.json',samples);guard(env_after,scheduler=ext)
   if role=='measured' and load:assert .22<=sample['controlled_load']['mean_cpu_cores']<=.28,'cpu25 outside admission range'
   return body
  outputs=visit.visit(case,fixture,server,observed)
 assert len(samples)==2 and outputs['warmup']==outputs['measured']==oracle
 assert outputs['cleanup']['returncode']==0 and outputs['cleanup']['sched_ext']=='disabled'
 log=(server/'server.stderr.log').read_text();mode=case['server_env'].get('NEWA_DECODE_RESOURCE','off')
 policy=pressure.validate(log,mode);save(folder/'policy-recomputed.json',policy)
 teams=sorted({int(x) for x in re.findall(r'NEWA_TEAM pid=\d+ team=(\d+)',log)})
 assert teams and set(teams)<={5,6},('Unexpected OpenMP team',teams)
 measured=samples[1];selected=[];decisions=None
 if mode!='off':
  selected=[e for e in policy['epochs'] if measured['start_ns']<=e['first_decode_ns']<=measured['end_ns']];assert selected,'Missing measured E epoch'
  decisions=[[sum(e['decisions_5_6'][p][j] for e in selected) for j in range(2)] for p in range(4)]
  required={5+j for j in range(2) if any(row[j] for row in decisions)};assert required<=set(teams),('Submitted vs actual teams',required,teams)
 save(folder/'environment-after.json',guard())
 result=dict(spec=spec,status='VALID',token_equality=True,performance=performance,metrics=measured,actual_OpenMP_teams=teams,measured_E_epochs=selected,measured_E_decisions_5_6=decisions,TTFT='NOT_MEASURED',counter_scope='proc snapshots bracket HTTP clock; CPU seconds is not energy')
 save(folder/'result.json',result);return result

def progress(root,plan,completed,status,failed=None):
 done={x['ordinal'] for x in completed};remaining=[dict(spec=s,status='NOT_RUN') for s in plan if s['ordinal'] not in done and (failed is None or s['ordinal']!=failed['spec']['ordinal'])]
 save(root/'campaigns.json',dict(status=status,completed=completed,failed=failed,not_run=remaining,planned_visits=len(plan),extra_pairs=0,seal_sha256=sha(D/'seal.json')))
 (D/'GOAL_STATE.md').write_text('# Frozen A component replication\n\nStatus: '+status+'\nRun: '+root.name+'; completed '+str(len(completed))+'/'+str(len(plan))+'.\nLast: '+str(completed[-1] if completed else None)+'\nNext planned: '+str(remaining[0] if remaining else None)+'\nProtected A: ../r-pool-validation-v1/candidates/A/runtime; pool off.\nNo repeat/replacement: inspect this run and preserve partial failures. A failed S admission is BLOCKED; this goal has no three-arm fallback.\nSeal: '+sha(D/'seal.json')+'\n')

def main():
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['admission','smoke','full']);p.add_argument('--name',required=True);a=p.parse_args();assert re.fullmatch(r'[A-Za-z0-9_-]+',a.name)
 names=read(D/'replication-protocol.json')['replication']['namespaces'];assert a.name==names[a.mode], 'Only the single registered namespace is allowed'
 root=D/'results'/a.name;assert not root.exists(),'Registered run already exists; no restart/replacement'
 with (W/'state/.measurement.lock').open('r') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);no_model_process();guard();verify_inputs();os.sched_setaffinity(0,{11})
  if a.mode=='full':
   assert read(D/'evidence/smoke-admission.json')['status']=='PASS'
   assert read(D/'protocol.json')['branch']=='full'
   for stage,filename in [('admission','scheduler-admission.json'),('smoke','smoke-admission.json')]:
    adm=read(D/'evidence'/filename);assert adm['status']=='PASS' and adm['run']==names[stage]
    assert read(D/'results'/names[stage]/'campaigns.json')['status']=='COMPLETE'
   assert read(D/'evidence/recalculation-completeness-test.json')['status']=='PASS'
  root.mkdir();save(root/'process.json',dict(pid=os.getpid(),starttime=contention.read_process(os.getpid())['starttime'],mode=a.mode,seal_sha256=sha(D/'seal.json'),started=now()))
  cases=read(D/'cases.json');fixtures={f['id']:f for f in read(D/'fixtures.json')}
  if a.mode=='full':plan=read(D/'order.json')
  else:
   arms=['A_S'] if a.mode=='admission' else ['B0_L','F6_L','A_L']
   plan=[dict(ordinal=i+1,campaign=0,condition='cpu25',block=j+1,cohort=fid,arm=arm,arm_order=arms) for i,(j,fid,arm) in enumerate((j,fid,arm) for j,fid in enumerate(['heldout-1','heldout-2']) for arm in arms)]
  save(root/'plan.json',plan);completed=[];progress(root,plan,completed,'RUNNING')
  for spec in plan:
   folder=root/f'{spec["ordinal"]:03}-{spec["condition"]}-b{spec["block"]:02}-{spec["arm"]}'
   event('visit-start',run=a.name,spec=spec)
   try:execute(spec,folder,cases,fixtures[spec['cohort']],a.mode=='full')
   except BaseException as exc:
    failure=dict(spec=spec,type=type(exc).__name__,message=str(exc),time=now())
    if folder.exists():save(folder/'failure.json',failure)
    progress(root,plan,completed,'STOPPED_INVALID',failure);event('visit-failure',run=a.name,**failure);raise
   completed.append(dict(**spec,path=str(folder.relative_to(D)),status='VALID'));progress(root,plan,completed,'RUNNING');event('visit-complete',run=a.name,spec=spec)
   print(json.dumps(dict(event='VISIT_COMPLETE',spec=spec,completed=len(completed),planned=len(plan))),flush=True)
  verify_inputs();no_model_process();guard();progress(root,plan,completed,'COMPLETE')
  if a.mode in ['admission','smoke']:
   save(D/('evidence/scheduler-admission.json' if a.mode=='admission' else 'evidence/smoke-admission.json'),dict(status='PASS',run=a.name,visits=completed,seal_sha256=sha(D/'seal.json'),scope='Not performance data'))
  event('run-complete',run=a.name,mode=a.mode,visits=len(completed));print('COMPLETE '+a.name,flush=True)
if __name__=='__main__':main()
