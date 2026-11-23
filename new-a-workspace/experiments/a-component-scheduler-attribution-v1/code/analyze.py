"""Recompute every paired component contrast from frozen raw records."""
import argparse,math,random,statistics,re
from pathlib import Path
from common import *
import prefill_pressure_evidence as pressure
import scheduler_evidence as se

def scheduler_checks(folder):
 se.audit_stats(folder)
 b,a=read(folder/'sched-ext-active.json'),read(folder/'sched-ext-after-http.json')
 for k in ['enable_seq','nr_rejected','switch_all','state','root/ops']:assert b['/sys/kernel/sched_ext/'+k]==a['/sys/kernel/sched_ext/'+k]
 assert b['/sys/kernel/sched_ext/root/ops']=='llama_new_a' and b['/sys/kernel/sched_ext/switch_all']=='0'
 def events(s):return {line.split()[0]:int(line.split()[1]) for line in s.splitlines()}
 be,ae=events(b['/sys/kernel/sched_ext/root/events']),events(a['/sys/kernel/sched_ext/root/events'])
 for k in ['SCX_EV_BYPASS_ACTIVATE','SCX_EV_BYPASS_DURATION','SCX_EV_BYPASS_DISPATCH']:assert ae[k]==be[k],'Unexpected bypass'
 procs=read(folder/'scheduler-processes.json');assert procs['loader']['uid']==0 and procs['loader']['policy']==0 and procs['launcher']['policy']==0 and procs['selected']['policy']==7
 assert procs['loader']['affinity']==procs['launcher']['affinity']==[11]
 assert procs['selected']['affinity']==CPUS and procs['selected']['uid']==os.getuid()
 links=json.loads(read(folder/'bpf-link.json')['stdout']);progs=json.loads(read(folder/'bpf-prog.json')['stdout']);maps=json.loads(read(folder/'bpf-map.json')['stdout']);perf=json.loads(read(folder/'bpf-perf.json')['stdout'])
 ops=[x for x in maps if x['name']=='llama_ops'];assert len(ops)==1 and ops[0]['type']=='struct_ops'
 assert any(x.get('map_id')==ops[0]['id'] and x['type']=='struct_ops' for x in links)
 phase=[x for x in progs if x['name']=='llama_phase'];assert len(phase)==1
 assert phase[0]['btf_id']==ops[0]['btf_id']
 assert any(x['type']=='perf_event' and x['prog_id']==phase[0]['id'] and x['offset']==1596224 and not x['retprobe'] for x in links)
 assert any(x['pid']==procs['loader']['pid'] and x['prog_id']==phase[0]['id'] and x['fd_type']=='uprobe' for x in perf)
 log=(folder/'loader.log').read_text();assert 'registered tgid='+str(procs['selected']['pid'])+' uid='+str(os.getuid()) in log
 assert 'FULL_GUARD_MONITOR_FAILED' not in log
 assert str(Path(read(folder/'runtime.json')['argv'][0]).parent/'libllama-server-impl.so') in read(folder/'loader-fds.json')['stdout']
 tags={x['name']:x['tag'] for x in progs if x.get('btf_id')==ops[0]['btf_id']}
 if (D/'evidence/scheduler-program-tags.json').exists():assert tags==read(D/'evidence/scheduler-program-tags.json')
 return tags

def validate_raw(folder,spec):
 case=read(D/'cases.json')[spec['arm']];ext=spec['arm']=='A_S';fixtures={x['id']:x for x in read(D/'fixtures.json')};fixture=fixtures[spec['cohort']]
 oracle=read(D/f'inputs/oracle-{spec["cohort"]}.json')['measured'];samples=read(folder/'http-observations.json');assert len(samples)==2
 payload=dict(fixture['requests'][0],prompt=[r['prompt'] for r in fixture['requests']]);payload.pop('id_slot')
 assert read(folder/'server/atomic-payload.json')==payload
 runtime=read(folder/'server/runtime.json');assert runtime['environment']==case['server_env'];verify_loaded(case,runtime['loaded_elf_sha256'])
 argv=case['server_argv'][:];argv[argv.index('--port')+1]=runtime['argv'][runtime['argv'].index('--port')+1];assert argv==runtime['argv']
 assert runtime['affinity']==CPUS and runtime['scheduler_state']==('enabled' if ext else 'disabled')
 assert read(folder/'server/cleanup.json')['status']=='PASS' and read(folder/'server/result.json')['cleanup']['returncode']==0
 policy=pressure.validate((folder/'server/server.stderr.log').read_text(),case['server_env'].get('NEWA_DECODE_RESOURCE','off'))
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
  assert b['affinity']==CPUS and b['policy']==(7 if ext else 0)
  for rows in [s['workers_before'],s['workers_after']]:assert rows and all(x['affinity']==CPUS and x['policy']==(7 if ext else 0) for x in rows.values())
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
  for e in [s['environment_before'],s['environment_after']]:guard(e,scheduler=ext)
  recomputed.append(dict(role=role,tokens=tokens,wall_s=wall,tokens_per_second=tokens/wall,cpu_s=cpu,cpu_seconds_per_token=cpu/tokens,background_cores=bg,start_ns=s['start_ns'],end_ns=s['end_ns']))
 measured=recomputed[1]
 epochs=[e for e in policy.get('epochs',[]) if measured['start_ns']<=e['first_decode_ns']<=measured['end_ns']]
 if spec['arm']!='B0_L':assert epochs
 if ext:scheduler_checks(folder/'server')
 watch=read(folder/'server/watchdog.json');assert watch and all(x['status']=='PASS' for x in watch)
 teams=sorted({int(x) for x in re.findall(r'NEWA_TEAM pid=\d+ team=(\d+)',(folder/'server/server.stderr.log').read_text())});assert teams and set(teams)<={5,6}
 if epochs:
  required={5+j for j in range(2) if any(e['decisions_5_6'][p][j] for e in epochs for p in range(4))};assert required<=set(teams)
 return dict(spec=spec,raw=str(folder.relative_to(D)),warmup=recomputed[0],measured=measured,token_equality=True,E_epochs=epochs)

def quantile(values,p):
 v=sorted(values);i=(len(v)-1)*p;l=int(i);return v[l]+(v[min(l+1,len(v)-1)]-v[l])*(i-l)

def analyze(name):
 plan=read(D/'order.json');protocol=read(D/'protocol.json');arms=protocol['arms'];n=protocol['pairs_per_condition'];contrasts=protocol['contrasts'];root=D/'results'/name;state=read(root/'campaigns.json');visits=[];errors=[]
 assert read(root/'plan.json')==plan
 for spec in plan:
  folder=root/f'{spec["ordinal"]:03}-{spec["condition"]}-b{spec["block"]:02}-{spec["arm"]}'
  if not (folder/'result.json').exists():errors.append(dict(spec=spec,status='NOT_RUN_OR_FAILED'));continue
  try:visits.append(validate_raw(folder,spec))
  except Exception as e:errors.append(dict(spec=spec,status='INVALID',error=repr(e)))
 cells=[]
 for condition in ['ambient','cpu25']:
  blocks=[]
  for block in range(1,n+1):
   rows={v['spec']['arm']:v for v in visits if v['spec']['condition']==condition and v['spec']['block']==block}
   if set(rows)!=set(arms):continue
   assert len({v['spec']['cohort'] for v in rows.values()})==1
   blocks.append(dict(block=block,cohort=rows[arms[0]]['spec']['cohort'],arms={a:rows[a]['measured'] for a in arms},gains={a+'/'+b:100*(rows[a]['measured']['tokens_per_second']/rows[b]['measured']['tokens_per_second']-1) for a,b in contrasts}))
  cell=dict(condition=condition,planned_blocks=n,completed_blocks=len(blocks),blocks=blocks,contrasts={})
  if len(blocks)==n:
   strata=[[b for b in blocks if b['cohort']==fid] for fid in ['heldout-1','heldout-2']];assert [len(s) for s in strata]==[n//2,n//2]
   rng=random.Random(20261122);boot={a+'/'+b:[] for a,b in contrasts}
   for _ in range(10000):
    draw=[r for s in strata for r in rng.choices(s,k=n//2)]
    for label in boot:boot[label].append(statistics.mean(r['gains'][label] for r in draw))
   for a,b in contrasts:
    label=a+'/'+b;gains=[r['gains'][label] for r in blocks];lo,hi=[quantile(boot[label],q) for q in [.025,.975]];mean=statistics.mean(gains);faster=sum(g>0 for g in gains)
    cell['contrasts'][label]=dict(mean_paired_gain_pct=mean,bootstrap_95_pct=[lo,hi],faster_blocks=faster,faster_fraction=faster/n,sign='positive' if lo>0 else 'negative' if hi<0 else 'inconclusive',target_pass=(mean>=5 and lo>0 and faster>=.75*n) if label=='A_S/B0_L' else None,strong_evidence=lo>=5,mean_paired_wall_reduction_pct=statistics.mean(100*(1-r['arms'][a]['wall_s']/r['arms'][b]['wall_s']) for r in blocks),by_cohort={fid:statistics.mean(r['gains'][label] for r in blocks if r['cohort']==fid) for fid in ['heldout-1','heldout-2']})
   cell['absolute']={arm:{k:statistics.mean(b['arms'][arm][k] for b in blocks) for k in ['tokens_per_second','wall_s','cpu_s','cpu_seconds_per_token']} for arm in arms}
   cell['E_selections']={arm:[dict(block=v['spec']['block'],cohort=v['spec']['cohort'],epochs=[dict(shadow=e['sample']['shadow_choice'],score=e['sample'].get('score'),eligible=e['eligible_by_size_5_6'],decisions=e['decisions_5_6'],locked=e['locked'],reason=e['reason']) for e in v['E_epochs']]) for v in visits if v['spec']['condition']==condition and v['spec']['arm']==arm] for arm in arms if arm!='B0_L'}
  cells.append(cell)
 actual=[v['spec']['ordinal'] for v in sorted(visits,key=lambda v:v['warmup']['start_ns'])];assert actual==[s['ordinal'] for s in plan if s['ordinal'] in actual], 'Actual order differs'
 if errors or state['status']!='COMPLETE' or len(visits)!=len(plan):status='INCOMPLETE_INVALID'
 elif protocol['branch']=='linux-fallback':status='BLOCKED_S_LINUX_ATTRIBUTION_COMPLETE'
 elif all(c['contrasts']['A_S/B0_L']['target_pass'] for c in cells):status='CONFIRMED_SCOPED_SYSTEM_GAIN_ONE_CAMPAIGN'
 else:status='COMPLETE_WITHOUT_FULL_SYSTEM_GATE'
 loads=[v['measured']['background_cores'] for v in visits if v['spec']['condition']=='cpu25']
 result=dict(status=status,campaigns=1,branch=protocol['branch'],cells=cells,visits=visits,invalid_or_missing=errors,actual_order=actual,actual_cpu25_cores_range=[min(loads),max(loads)] if loads else None,counts=dict(valid_visits=len(visits),measured_individual_generations=len(visits)*8,warmup_individual_generations=len(visits)*8,measured_tokens=sum(v['measured']['tokens'] for v in visits),warmup_tokens=sum(v['warmup']['tokens'] for v in visits)),seal_sha256=sha(D/'seal.json'))
 save(root/'analysis.json',result);save(D/'component-summary.json',result);return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--name',required=True);a=p.parse_args();r=analyze(a.name);print(json.dumps({k:r[k] for k in ['status','counts','actual_cpu25_cores_range']},indent=2))
