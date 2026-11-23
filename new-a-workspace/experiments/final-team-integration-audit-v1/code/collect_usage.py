"""Reaggregate existing raw records only. No model, build or privileged calls."""
import collections,hashlib,importlib.util,json,math,random,re,statistics,struct,subprocess,sys
from pathlib import Path
D=Path(__file__).resolve().parents[1];W=D.parents[1]
def read(p):return json.loads(p.read_text())
def save(name,x):(D/name).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
inputs={}
def record(p):
 p=p.resolve();inputs[str(p)]=dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size);return p
E=W/'experiments/a-component-scheduler-replication-v1/code/prefill_pressure_evidence.py';record(E)
spec=importlib.util.spec_from_file_location('audit_pressure',E);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
groups={};visits=[];scheduler=[];performance=[]
for campaign,label,full,summary in [('original','a-component-scheduler-attribution-v1','attribution-v1','component-summary.json'),('replication','a-component-scheduler-replication-v1','replication-v1','replication-summary.json')]:
 root=W/'experiments'/label;cases=read(record(root/'cases.json'))
 tool=W/'experiments/a-component-scheduler-replication-v1/code/recalculate.py';record(tool)
 argv=[sys.executable,'-B',str(tool),'--name',full,'--root',str(root),'--summary',summary]
 r=subprocess.run(argv,capture_output=True,text=True,timeout=90);assert r.returncode==0,r.stderr
 check=json.loads(r.stdout);assert check['status']=='PASS';performance.append(dict(campaign=campaign,argv=argv,result=check))
 for run in sorted((root/'results').iterdir()):
  if not run.is_dir() or not (run/'campaigns.json').exists():continue
  state=read(record(run/'campaigns.json'));assert state['status']=='COMPLETE';kind='performance' if run.name==full else 'functional'
  for item in state['completed']:
   folder=root/item['path'];arm=item['arm'];cond=item['condition'];raw=read(record(folder/'http-observations.json'))
   log=record(folder/'server/server.stderr.log').read_text();mode=cases[arm]['server_env'].get('NEWA_DECODE_RESOURCE','off');policy=mod.validate(log,mode)
   runtime=read(record(folder/'server/runtime.json'));assert runtime['environment']==cases[arm]['server_env']
   pool_lines=re.findall(r'^NEWA_POOL.*$',log,re.M);teams=sorted({int(x) for x in re.findall(r'NEWA_TEAM pid=\d+ team=(\d+)',log)})
   v=dict(campaign=campaign,run=run.name,stage=kind,condition=cond,arm=arm,block=item['block'],cohort=item['cohort'],path=str(folder.relative_to(W)),team_size_set=teams,team_scope='lifetime OpenMP affinity reports; not continuous graph instrumentation',pool_lines=pool_lines,epochs_total=len(policy.get('epochs',[])))
   visits.append(v);mapped=0
   for sample in raw:
    role=sample['role'];window='warmup' if role=='warmup' else 'measured' if kind=='performance' else 'functional_check'
    key='|'.join([campaign,kind,cond,arm,window]);g=groups.setdefault(key,dict(campaign=campaign,stage=kind,condition=cond,arm=arm,window=window,cohorts=0,epochs=0,calls=0,decisions_by_phase_5_6=[[0,0] for _ in range(4)],eligible_by_size_5_6=[[0,0] for _ in range(9)],locked_epochs=0,invalidated_epochs=0,shadow_choices=collections.Counter(),samples=[]))
    g['cohorts']+=1;epochs=[e for e in policy.get('epochs',[]) if sample['start_ns']<=e['first_decode_ns']<=sample['end_ns']];mapped+=len(epochs)
    for e in epochs:
     g['epochs']+=1;g['calls']+=e['calls'];g['locked_epochs']+=e['locked'];g['invalidated_epochs']+=e['invalidated'];g['shadow_choices'][e['sample']['shadow_choice']]+=1
     for p in range(4):
      for j in range(2):g['decisions_by_phase_5_6'][p][j]+=e['decisions_5_6'][p][j]
     for size in range(9):
      for j in range(2):g['eligible_by_size_5_6'][size][j]+=e['eligible_by_size_5_6'][size][j]
    g['samples'].append(dict(path=str((folder/'http-observations.json').relative_to(W)),start_ns=sample['start_ns'],end_ns=sample['end_ns'],epoch_count=len(epochs)))
   v['epochs_not_window_assigned']=len(policy.get('epochs',[]))-mapped;assert v['epochs_not_window_assigned']==0
   if arm=='A_S':
    stats=read(record(folder/'server/scheduler-stats.json'));audit=read(record(folder/'server/scheduler-audit.json'));procs=read(record(folder/'server/scheduler-processes.json'))
    cpus=stats['cpus'];phase_bits=0
    for row in cpus:phase_bits|=row['phase_seen']
    totals={k:sum(x[k] for x in cpus) for k in ['running','stopping','runtime_ns','migrations','mask_violations','tracking_failures','events_attempted','events_dropped']}
    selected=[sum(x['selected'][j] for x in cpus) for j in range(4)];assert not any(totals[k] for k in ['mask_violations','tracking_failures','events_dropped'])
    assert stats['events_export_error']==0 and stats['instrumentation_mode']=='FULL' and not any(stats['idle_handoff']['moved'])
    assert procs['selected']['policy']==7 and procs['selected']['uid']==1000 and procs['loader']['policy']==procs['launcher']['policy']==0
    loaderlog=record(folder/'server/loader.log').read_text();tiers=re.findall(r'enabled=(\d+) tiers=(\d+)/(\d+)/(\d+)',loaderlog);assert tiers==[('1','6','0','0')]
    scheduler.append(dict(campaign=campaign,stage=kind,condition=cond,path=str(folder.relative_to(W)),selected_tier_counts=selected,selection_callbacks=sum(selected),phase_seen_bits=phase_bits,phase_event_count=None,phase_event_count_reason='phase_seen is a presence bitmap; transition count is not exported',handoff=stats['idle_handoff'],totals=totals,topology_tier_counts=[6,0,0],monitor=stats['live_monitor'],scope='whole selected-child visit lifecycle, including startup/warmup/measured/teardown; no measured-only counter delta'))
for g in groups.values():
 g['eligible_multi_5_6']=[sum(g['eligible_by_size_5_6'][s][j] for s in range(2,9)) for j in range(2)]
 g['eligible_single_5_6']=g['eligible_by_size_5_6'][1];g['all_decode_5_6']=g['decisions_by_phase_5_6'][2]
 g['counter_availability']='NOT_INSTRUMENTED' if g['arm']=='B0_L' else 'OBSERVED_EPOCH_REPORTS'
 g['denominators']=dict(eligible_multi_calls=sum(g['eligible_multi_5_6']),all_decode_calls=sum(g['all_decode_5_6']),all_select_calls=g['calls'],all_graphs=None)
 g['unit']='successful policy select calls represented by committed epoch reports; not tokens, graphs, ubatches or worker-seconds'
pool=[];R=W/'experiments/r-pool-validation-v1'
for arm in ['A','P']:
 path=record(R/f'results/lifecycle-{arm}-observer-v2/pool-events.jsonl');rows=[json.loads(l) for l in path.read_text().splitlines()];live={};created=[];frees=[];graphs=[]
 for row in rows:
  if row['event']=='new_api':assert row['pool'] not in live;live[row['pool']]=row;created.append(row)
  elif row['event']=='free' and row['pool'] in live:frees.append(dict(new=live.pop(row['pool']),free=row))
  elif row['event']=='graph_begin':graphs.append(row)
 assert not live
 steady=[x for x in graphs if x['role'] in ['warmup','measured','after-cancel','after-error']]
 row=dict(arm=arm,raw=str(path.relative_to(W)),event_rows=len(rows),new_api=len(created),persistent_frees=len(frees),steady_graphs=len(steady),steady_attached=sum(x['pool']!='(nil)' for x in steady),steady_disposable=sum(x['pool']=='(nil)' for x in steady),by_role={role:dict(graphs=len([x for x in graphs if x['role']==role]),new_api=len([x for x in created if x['role']==role]),persistent_frees=len([x for x in frees if x['free']['role']==role])) for role in sorted({x['role'] for x in rows})})
 expected=next(x for x in read(record(R/'evidence/AP-lifecycle-summary.json'))['arms'] if x['arm']==arm)
 assert (row['new_api'],row['persistent_frees'],row['steady_graphs'],row['steady_disposable'])==(expected['persistent_api_creations'],expected['persistent_api_frees'],expected['steady_graphs'],expected['steady_disposable_graphs']);pool.append(row)
route=record(R/'results/route-heldout-1-R/server.stderr.log').read_text();route_counts={}
for key,pattern in [('actual_reference_body_by_phase',r'NEWA_R_REFERENCE_BODY calls=(\d+)/(\d+)/(\d+)/(\d+)'),('retained_exact_q4_by_phase',r'NEWA_Q4_TILE32 stats worker0_calls=(\d+)/(\d+)/(\d+)/(\d+)'),('retained_q6_by_phase',r'NEWA_Q6 stats worker0_chunks=(\d+)/(\d+)/(\d+)/(\d+)')]:
 matches=re.findall(pattern,route);assert len(matches)==1;route_counts[key]=list(map(int,matches[0]));assert route_counts[key]==read(record(R/'evidence/R-route-summary.json'))[key]
pilot=read(record(R/'results/pilot-v1/analysis.json'));pilot_recalc=[]
def q(xs,p):
 a=sorted(xs);i=(len(a)-1)*p;j=int(i);return a[j]+(a[min(j+1,len(a)-1)]-a[j])*(i-j)
for condition in ['ambient','cpu25']:
 gains=[];rawrows=[]
 for block in range(1,5):
  pair={}
  for arm in ['A','P']:
   folder=R/f'results/pilot-v1/{condition}-b{block}-{arm}';o=read(record(folder/'http-observations.json'))[1];body=read(record(folder/'server/measured-responses.json'))
   tokens=sum(len(v['tokens']) for v in body);assert tokens==1024;wall=(o['end_ns']-o['start_ns'])/1e9;assert math.isclose(tokens/wall,o['throughput'],rel_tol=1e-12);pair[arm]=tokens/wall
  gains.append(100*(pair['P']/pair['A']-1));rawrows.append(dict(block=block,**pair))
 rng=random.Random(20261122);boot=[statistics.mean(rng.choices(gains,k=4)) for _ in range(10000)];ci=[q(boot,.025),q(boot,.975)];mean=statistics.mean(gains);expected=next(x for x in pilot['conditions'] if x['condition']==condition)
 assert math.isclose(mean,expected['mean_paired_gain_pct'],abs_tol=1e-9) and all(math.isclose(a,b,abs_tol=1e-9) for a,b in zip(ci,expected['paired_bootstrap_95_pct']))
 pilot_recalc.append(dict(condition=condition,n=4,mean=mean,ci=ci,faster=sum(x>0 for x in gains),gains=gains,raw_tps=rawrows))
save('observed-usage.json',dict(status='REAGGREGATED_EXISTING_RAW',new_model_calls=0,groups=list(groups.values()),visits=visits,scheduler_visits=scheduler,pool_lifecycle=pool,R_route_diagnostic=dict(counts=route_counts,scope='separate diagnostic lifetime including warmup; worker0 Q4 function counts and Q6 chunk counts are different units; not performance or total graph denominators'),missing_denominators=['continuous graph/physical ubatch counts in final timing','scheduler marker event count','measured-only scheduler tier/attempt deltas']))
save('evidence/performance-recalculation.json',dict(component_campaigns=performance,pool_pilot=pilot_recalc,formula_unchanged=True,no_pooled_campaigns=True))
save('evidence/usage-inputs.json',inputs)
print(json.dumps(dict(status='PASS',visits=len(visits),scheduler_visits=len(scheduler),group_count=len(groups),pool=pool,R_routes=route_counts),ensure_ascii=False))
