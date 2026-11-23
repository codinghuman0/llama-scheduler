"""Primary analysis from response bodies, HTTP clocks and process counters."""
import argparse,math,random,statistics
from pathlib import Path
from common import *
import prefill_pressure_evidence as pressure

def quantile(values,p):
 v=sorted(values);i=(len(v)-1)*p;l=int(i);return v[l]+(v[min(l+1,len(v)-1)]-v[l])*(i-l)
def bootstrap(pairs):
 strata=[[p['gain_pct'] for p in pairs if p['cohort']==fid] for fid in ['heldout-1','heldout-2']]
 assert [len(s) for s in strata]==[4,4]
 rng=random.Random(20261122)
 vals=[statistics.mean([x for s in strata for x in rng.choices(s,k=4)]) for _ in range(10000)]
 return [quantile(vals,.025),quantile(vals,.975)]
def validate_raw(folder,spec):
 case=read(D/'cases.json')[spec['arm']];fixtures={x['id']:x for x in read(D/'fixtures.json')};fixture=fixtures[spec['cohort']]
 oracle=read(D/f'inputs/oracle-{spec["cohort"]}.json')['measured'];samples=read(folder/'http-observations.json');assert len(samples)==2
 payload=dict(fixture['requests'][0],prompt=[r['prompt'] for r in fixture['requests']]);payload.pop('id_slot')
 assert read(folder/'server/atomic-payload.json')==payload
 runtime=read(folder/'server/runtime.json');assert runtime['environment']==case['server_env'];assert runtime['loaded_elf_sha256']=={**case['artifacts'],**case['system_libraries']}
 argv=case['server_argv'][:];argv[argv.index('--port')+1]=runtime['argv'][runtime['argv'].index('--port')+1];assert argv==runtime['argv']
 assert runtime['affinity']==CPUS and runtime['scheduler_state']=='disabled'
 assert read(folder/'server/cleanup.json')['status']=='PASS' and read(folder/'server/cleanup.json')['returncode']==0
 policy=pressure.validate((folder/'server/server.stderr.log').read_text(),'pressure' if spec['arm']=='A' else 'off')
 recomputed=[]
 for role,s in zip(['warmup','measured'],samples):
  assert s['role']==role
  values=read(folder/(role+'-http-raw.json'));assert isinstance(values,list) and len(values)==8
  values=sorted(values,key=lambda v:v['index']);assert [v['index'] for v in values]==list(range(8))
  assert [v['tokens'] for v in values]==oracle
  for v,r in zip(values,fixture['requests']):
   assert len(v['tokens'])==v['tokens_predicted']==128
   assert v['timings']['cache_n']==0 and v['timings']['prompt_n']==len(r['prompt'])==v['tokens_evaluated']
  assert values==read(folder/f'server/{role}-responses.json')
  b,a=s['server_before'],s['server_after']
  for k in ['pid','starttime','tick_hz','affinity','policy']:assert b[k]==a[k]
  assert b['affinity']==CPUS and b['policy']==0
  for rows in [s['workers_before'],s['workers_after']]:assert rows and all(x['affinity']==CPUS and x['policy']==0 for x in rows.values())
  wall=(s['end_ns']-s['start_ns'])/1e9;tokens=sum(len(v['tokens']) for v in values);cpu=(a['cpu_ticks']-b['cpu_ticks'])/b['tick_hz']
  assert wall>0 and cpu>=0 and tokens==1024
  for field,v in [('throughput',tokens/wall),('cpu_time_s',cpu),('cohort_http_wall_s',wall)]:assert math.isclose(s[field],v,rel_tol=1e-12)
  bg=None
  if spec['condition']=='cpu25':
   lb,la=s['load_before'],s['load_after']
   for k in ['pid','starttime','tick_hz','affinity','policy']:assert lb[k]==la[k]
   assert lb['affinity']==[10] and lb['policy']==0
   bg=(la['cpu_ticks']-lb['cpu_ticks'])/lb['tick_hz']/wall
   if role=='measured':assert .22<=bg<=.28
   assert read(folder/'controlled-load/cleanup.json')['status']=='PASS'
  for e in [s['environment_before'],s['environment_after']]:guard(e)
  recomputed.append(dict(role=role,tokens=tokens,wall_s=wall,tokens_per_second=tokens/wall,cpu_s=cpu,cpu_seconds_per_token=cpu/tokens,background_cores=bg,start_ns=s['start_ns'],end_ns=s['end_ns']))
 measured=recomputed[1]
 epochs=[e for e in policy.get('epochs',[]) if measured['start_ns']<=e['first_decode_ns']<=measured['end_ns']]
 if spec['arm']=='A':assert epochs
 return dict(spec=spec,raw=str(folder.relative_to(D)),warmup=recomputed[0],measured=measured,token_equality=True,E_epochs=epochs)

def analyze(name,write=True):
 root=D/'results'/name;plan=read(D/'order.json');state=read(root/'campaigns.json');visits=[];errors=[]
 for spec in plan:
  folder=root/f'campaign-{spec["campaign"]}'/f'{spec["condition"]}-b{spec["block"]:02}-{spec["arm"]}'
  if not (folder/'result.json').exists():errors.append(dict(spec=spec,status='NOT_RUN_OR_FAILED'));continue
  try:visits.append(validate_raw(folder,spec))
  except Exception as exc:errors.append(dict(spec=spec,status='INVALID',error=str(exc)))
 cells=[]
 for campaign in [1,2]:
  for condition in ['ambient','cpu25']:
   pairs=[]
   for block in range(1,9):
    v={r['spec']['arm']:r for r in visits if r['spec']['campaign']==campaign and r['spec']['condition']==condition and r['spec']['block']==block}
    if set(v)!={'B0','A'}:continue
    b,a=v['B0']['measured'],v['A']['measured'];assert v['B0']['spec']['cohort']==v['A']['spec']['cohort']
    pairs.append(dict(block=block,cohort=v['A']['spec']['cohort'],arm_order=v['A']['spec']['arm_order'],gain_pct=100*(a['tokens_per_second']/b['tokens_per_second']-1),B0=b,A=a))
   cell=dict(campaign=campaign,condition=condition,planned_pairs=8,completed_pairs=len(pairs),valid=len(pairs)==8,pairs=pairs)
   if len(pairs)==8:
    gains=[p['gain_pct'] for p in pairs];lo,hi=bootstrap(pairs);gain=statistics.mean(gains);faster=sum(g>0 for g in gains)
    cell.update(mean_paired_gain_pct=gain,paired_stratified_bootstrap_95_pct=[lo,hi],faster_pairs=faster,faster_fraction=faster/8,target_pass=gain>=5 and lo>0 and faster>=6,strong_evidence=lo>=5,absolute={arm:{k:statistics.mean(p[arm][k] for p in pairs) for k in ['tokens_per_second','wall_s','cpu_s','cpu_seconds_per_token']} for arm in ['B0','A']},by_cohort={fid:dict(pairs=4,mean_gain_pct=statistics.mean(p['gain_pct'] for p in pairs if p['cohort']==fid)) for fid in ['heldout-1','heldout-2']})
   cells.append(cell)
 if errors or state['status']!='COMPLETE' or not all(c['valid'] for c in cells):status='INCOMPLETE_INVALID'
 elif all(c['target_pass'] for c in cells):status='CONFIRMED_SCOPED_A_OVER_B0'
 elif all(c['paired_stratified_bootstrap_95_pct'][0]>0 for c in cells):status='POSITIVE_BELOW_TARGET'
 elif all(c['mean_paired_gain_pct']<0 and c['paired_stratified_bootstrap_95_pct'][1]<0 for c in cells):status='REGRESSION'
 elif any(c['paired_stratified_bootstrap_95_pct'][0]>0 or c['paired_stratified_bootstrap_95_pct'][1]<0 for c in cells):status='SCOPED_OR_MIXED_RESULT'
 else:status='NO_CONFIRMED_GAIN'
 loads=[v['measured']['background_cores'] for v in visits if v['spec']['condition']=='cpu25']
 result=dict(status=status,run=name,cells=cells,visits=visits,invalid_or_missing=errors,actual_cpu25_cores_range=[min(loads),max(loads)] if loads else None,counts=dict(valid_measured_visits=len(visits),measured_cohorts=len(visits),measured_individual_generations=8*len(visits),measured_generated_tokens=sum(v['measured']['tokens'] for v in visits),warmup_cohorts=len(visits),warmup_individual_generations=8*len(visits),warmup_tokens=sum(v['warmup']['tokens'] for v in visits)),primary='mean of paired A/B0 percentage gains; not ratio of aggregate means',seal_sha256=sha(D/'seal.json'),runtime_code_changes=False,scope='Two runs on this AMD host and same previously observed distinct cohorts; runtime total system effect, not isolated E/kernel scheduler effect')
 if write:save(root/'analysis.json',result);save(D/'direct-comparison-summary.json',result)
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--name',required=True);a=p.parse_args();r=analyze(a.name);print(json.dumps({k:r[k] for k in ['status','run','actual_cpu25_cores_range','counts']},indent=2))
