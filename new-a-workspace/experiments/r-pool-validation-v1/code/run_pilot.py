import argparse,copy,datetime,fcntl,hashlib,importlib.util,json,os,sys,time
from contextlib import nullcontext
from pathlib import Path
import run_r_gate as runner
D,W=runner.D,runner.W
read,save,sha=runner.read,runner.save,runner.sha
sys.dont_write_bytecode=True
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
contention=module('pilot_load',D/'evidence/history/server-build/study-code/contention.py')
auditor=module('pilot_pressure',D/'evidence/history/server-build/study-code/prefill_pressure_evidence.py')
def execute_visit(spec,folder,cases,fixture):
 case=copy.deepcopy(cases[spec['arm']]);case['scope']='P/A_PILOT';loadctx=contention.ControlledLoad(folder/'controlled-load',10) if spec['condition']=='cpu25' else nullcontext(None)
 # The load module creates its folder first. The server visit owns a separate child.
 folder.mkdir(exist_ok=False);visit_folder=folder/'server';samples=[];original_http=runner.http_json
 with loadctx as load:
  def observed(port,path,payload=None,timeout=180):
   if path!='/completion':return original_http(port,path,payload,timeout)
   pid=read(visit_folder/'process.json')['pid'];before=contention.read_process(pid);lb=load.snapshot() if load else None
   t0=time.monotonic_ns();body=original_http(port,path,payload,timeout);t1=time.monotonic_ns()
   after=contention.read_process(pid);la=load.snapshot() if load else None
   for k in ['pid','starttime','tick_hz','affinity','policy']:assert before[k]==after[k],k
   assert before['affinity']==[0,2,4,6,8,10] and before['policy']==0
   rows=body if isinstance(body,list) else [body];tokens=sum(len(x['tokens']) for x in rows);assert tokens==1024
   wall=(t1-t0)/1e9;row=dict(role='warmup' if not samples else 'measured',start_ns=t0,end_ns=t1,actual_generated_tokens=tokens,cohort_http_wall_s=wall,throughput=tokens/wall,cpu_time_s=(after['cpu_ticks']-before['cpu_ticks'])/before['tick_hz'],server_before=before,server_after=after)
   if load:row.update(load_before=lb,load_after=la,controlled_load=contention.metrics(lb,la,wall))
   samples.append(row);save(folder/'http-observations.json',samples);return body
  runner.http_json=observed
  try:outputs=runner.visit(case,fixture,visit_folder)
  finally:runner.http_json=original_http
 assert len(samples)==2
 oracle=read(D/'results'/f'free-{fixture["id"]}-B0-r1/result.json')['measured']
 equality=outputs['warmup']==outputs['measured']==oracle
 measured=samples[1];load_ok=spec['condition']=='ambient' or .22<=measured['controlled_load']['mean_cpu_cores']<=.28
 log=(visit_folder/'server.stderr.log').read_text();policy=None;policy_error=None
 try:policy=auditor.validate(log,'pressure')
 except Exception as exc:policy_error=str(exc)
 selected=[]
 if policy:
  selected=[e for e in policy['epochs'] if measured['start_ns']<=e['first_decode_ns']<=measured['end_ns']]
  save(folder/'E-policy-recomputed.json',policy)
 decisions=[[sum(e['decisions_5_6'][phase][j] for e in selected) for j in range(2)] for phase in range(4)]
 result=dict(spec=spec,metrics=measured,token_equality=equality,load_valid=load_ok,policy_audit_valid=policy is not None,policy_error=policy_error,measured_epochs=len(selected),measured_decisions_5_6=decisions,valid=equality and load_ok and policy is not None and bool(selected),TTFT='NOT_MEASURED: fixed nonstream HTTP protocol',scope='Limited P/A pilot, not B0 gain or confirmation')
 save(folder/'result.json',result);return result

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--campaign',default='pilot-v1');args=parser.parse_args();assert '/' not in args.campaign and args.campaign not in ['.','..']
 state=read(D/'gate-results.json');assert state['R']==state['E-R']=='COMPATIBLE_IN_TESTED_SCOPE' and state['Pool integration']=='MODEL_VALIDATED'
 protocol=read(D/'protocol-AP.json');cases=read(D/'cases-AP.json');fixtures={f['id']:f for f in read(D/'fixtures.json')};root=D/'results'/args.campaign;assert not root.exists()
 runner.preflight()
 with (W/'state/.measurement.lock').open('r') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);root.mkdir();rows=[]
  frozen={str(p.relative_to(D)):sha(p) for p in [D/'protocol-AP.json',D/'protocol-AP-padding-amendment.json',D/'cases-AP.json',D/'code/run_pilot.py',D/'code/run_r_gate.py',D/'fixtures.json',D/'code/analyze_pilot.py']}
  save(root/'frozen-before-first-timing.json',dict(time=datetime.datetime.now(datetime.timezone.utc).isoformat(),inputs=frozen,arms=cases,protocol=protocol,topology={str(cpu):{name:Path(f'/sys/devices/system/cpu/cpu{cpu}/topology/{name}').read_text().strip() for name in ['physical_package_id','core_id','thread_siblings_list']} for cpu in range(12)},clock=time.get_clock_info('monotonic').implementation))
  for condition in protocol['pilot']['conditions']:
   for block,(order,fid) in enumerate(zip(protocol['pilot']['order'],protocol['pilot']['cohorts']),1):
    for arm in order.split(','):
     spec=dict(condition=condition,block=block,arm=arm,cohort=fid);folder=root/f'{condition}-b{block}-{arm}'
     runner.event(dict(stage='pilot-visit-start',campaign=args.campaign,spec=spec))
     try:result=execute_visit(spec,folder,cases,fixtures[fid])
     except BaseException as exc:
      if folder.exists():save(folder/'failure.json',dict(type=type(exc).__name__,message=str(exc)))
      save(root/'campaign.json',dict(status='STOPPED_ON_EXECUTION_FAILURE',completed=rows,failed=spec,error=str(exc),additional_pairs=0));runner.event(dict(stage='pilot-execution-failure',spec=spec,error=str(exc)));raise
     rows.append(result);save(root/'campaign.json',dict(status='IN_PROGRESS',completed=rows))
     runner.event(dict(stage='pilot-visit-complete',campaign=args.campaign,spec=spec,valid=result['valid'],throughput=result['metrics']['throughput']))
     with (D/'GOAL_STATE.md').open('a') as f:f.write('\nPilot '+args.campaign+': '+str(spec)+', valid='+str(result['valid'])+'. Raw '+str(folder.relative_to(D))+'\n')
     print(json.dumps(dict(event='PILOT_VISIT',spec=spec,throughput=result['metrics']['throughput'],wall_s=result['metrics']['cohort_http_wall_s'],cpu_time_s=result['metrics']['cpu_time_s'],valid=result['valid'],load=result['metrics'].get('controlled_load'),decisions=result['measured_decisions_5_6'])),flush=True)
  for rel,digest in frozen.items():assert sha(D/rel)==digest,'Frozen analysis/code changed during timing'
  save(root/'campaign.json',dict(status='COMPLETE',completed=rows,planned_pairs_per_condition=4,extra_pairs=0))
if __name__=='__main__':main()
