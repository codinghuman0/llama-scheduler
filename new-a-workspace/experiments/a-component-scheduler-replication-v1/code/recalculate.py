"""Independent, model-free raw arithmetic. No runner/analyzer imports."""
import argparse,json,math,random,statistics,hashlib
from pathlib import Path
D=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text())
def q(xs,p):
 s=sorted(xs);x=(len(s)-1)*p;a=math.floor(x);b=math.ceil(x);return s[a]*(b-x)+s[b]*(x-a) if a!=b else s[a]
def require_complete(value, message):
 if not value:raise ValueError('INCOMPLETE: '+message)

def recalculate(name, root=None, summary_file='replication-summary.json'):
 D=Path(root).resolve() if root is not None else Path(__file__).resolve().parents[1]
 protocol=read(D/'protocol.json');order=read(D/'order.json');summary=read(D/summary_file);fixtures={f['id']:f for f in read(D/'fixtures.json')};rows={};verified=0
 require_complete(protocol['planned_visits']==64 and protocol['pairs_per_condition']==8 and protocol['campaigns']==1, 'fixed 64-visit protocol')
 require_complete(protocol['arms']==['B0_L','F6_L','A_L','A_S'], 'four frozen arms')
 require_complete(protocol['contrasts']==[['A_L','B0_L'],['F6_L','B0_L'],['A_L','F6_L'],['A_S','A_L'],['A_S','B0_L']], 'five original contrasts')
 require_complete(len(order)==64 and [s['ordinal'] for s in order]==list(range(1,65)), '64 unique ordered visits')
 expected_keys={(cond,b,arm) for cond in ['ambient','cpu25'] for b in range(1,9) for arm in protocol['arms']}
 require_complete({(s['condition'],s['block'],s['arm']) for s in order}==expected_keys, 'complete four-arm block plan')
 state=read(D/'results'/name/'campaigns.json')
 require_complete(state['status']=='COMPLETE' and state['failed'] is None and not state['not_run'], 'campaign must be terminal COMPLETE without failures/NOT_RUN')
 require_complete(state['planned_visits']==64 and state['extra_pairs']==0 and len(state['completed'])==64, 'completed visit accounting')
 require_complete([x['ordinal'] for x in state['completed']]==list(range(1,65)) and all(x['status']=='VALID' for x in state['completed']), 'all 64 visits valid in order')
 require_complete(read(D/'results'/name/'plan.json')==order, 'executed plan equals registered order')
 require_complete(len(summary['cells'])==2 and {c['condition'] for c in summary['cells']}=={'ambient','cpu25'}, 'both analysis conditions')
 require_complete(not summary['invalid_or_missing'] and summary['counts']['valid_visits']==64, 'summary completeness')
 for spec in order:
  folder=D/'results'/name/f'{spec["ordinal"]:03}-{spec["condition"]}-b{spec["block"]:02}-{spec["arm"]}'
  require_complete((folder/'result.json').is_file(), 'missing planned visit '+str(spec['ordinal']))
  recorded=read(folder/'result.json')
  require_complete(recorded['status']=='VALID' and recorded['performance'] is True and recorded['spec']==spec, 'visit identity/status '+str(spec['ordinal']))
  obs=read(folder/'http-observations.json');oracle=read(D/'inputs'/f'oracle-{spec["cohort"]}.json')['measured']
  assert len(obs)==2
  for role,o in zip(['warmup','measured'],obs):
   body=sorted(read(folder/f'{role}-http-raw.json'),key=lambda v:v['index']);assert [v['index'] for v in body]==list(range(8))
   assert [v['tokens'] for v in body]==oracle
   for v,req in zip(body,fixtures[spec['cohort']]['requests']):
    assert len(v['tokens'])==v['tokens_predicted']==128 and v['timings']['cache_n']==0
    assert v['tokens_evaluated']==v['timings']['prompt_n']==len(req['prompt'])
    assert v['generation_settings']['temperature']==0 and v['generation_settings']['seed']==424242
   seconds=(o['end_ns']-o['start_ns'])/10**9;ntokens=sum(map(lambda v:len(v['tokens']),body));assert seconds>0 and ntokens==1024
   cpu=(o['server_after']['cpu_ticks']-o['server_before']['cpu_ticks'])/o['server_before']['tick_hz'];assert cpu>=0
   expected_policy=7 if spec['arm']=='A_S' else 0
   for k in ['workers_before','workers_after']:assert all(w['policy']==expected_policy and w['affinity']==[0,2,4,6,8,10] for w in o[k].values())
   if role=='measured':
    if spec['condition']=='cpu25':
     b,a=o['load_before'],o['load_after'];load=(a['cpu_ticks']-b['cpu_ticks'])/b['tick_hz']/seconds
     assert b['pid']==a['pid'] and b['starttime']==a['starttime'] and b['affinity']==a['affinity']==[10] and b['policy']==a['policy']==0 and .22<=load<=.28
    rows[(spec['condition'],spec['block'],spec['arm'])]=(spec['cohort'],ntokens/seconds,seconds,cpu)
   verified+=1
 results=[]
 for cell in summary['cells']:
  cond=cell['condition'];n=protocol['pairs_per_condition'];blocks=[]
  for b in range(1,n+1):
   require_complete(all((cond,b,a) in rows for a in protocol['arms']), 'missing complete block '+cond+'/'+str(b))
   block={a:rows[cond,b,a] for a in protocol['arms']};assert len({x[0] for x in block.values()})==1;blocks.append(block)
  require_complete(len(blocks)==n==8, 'eight complete blocks in '+cond)
  st=[[b for b in blocks if next(iter(b.values()))[0]==cohort] for cohort in ['heldout-1','heldout-2']];require_complete([len(x) for x in st]==[4,4], 'four blocks per cohort');rng=random.Random(20261122)
  draws=[[x for stratum in st for x in rng.choices(stratum,k=n//2)] for _ in range(10000)]
  for candidate,baseline in protocol['contrasts']:
   label=candidate+'/'+baseline
   def gain(b):return 100*(b[candidate][1]/b[baseline][1]-1)
   gains=[gain(b) for b in blocks];boot=[sum(gain(b) for b in draw)/n for draw in draws];got=dict(mean=statistics.mean(gains),ci=[q(boot,.025),q(boot,.975)],faster=sum(g>0 for g in gains))
   expected=cell['contrasts'][label];assert math.isclose(got['mean'],expected['mean_paired_gain_pct'],abs_tol=1e-9)
   assert all(math.isclose(a,b,abs_tol=1e-9) for a,b in zip(got['ci'],expected['bootstrap_95_pct'])) and got['faster']==expected['faster_blocks']
   results.append(dict(condition=cond,contrast=label,**got))
 require_complete(len(rows)==64 and verified==128 and len(results)==10, '64 visits / 128 raw cohorts / 10 contrasts')
 return dict(status='PASS',model_free=True,analyzer_imported=False,raw_cohorts_checked=verified,complete_contrasts=len(results),contrasts=results,limit='Recalculates numerical/raw-token claims; live source/DSO checks are separate evidence')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--name',default='replication-v1');p.add_argument('--root',type=Path);p.add_argument('--summary',default='replication-summary.json');p.add_argument('--output');a=p.parse_args()
 try:r=recalculate(a.name,a.root,a.summary)
 except Exception as e:
  print(json.dumps(dict(status='INCOMPLETE_INVALID',error=str(e)),indent=2));raise SystemExit(2)
 if a.output:Path(a.output).write_text(json.dumps(r,indent=2)+'\n')
 print(json.dumps(r,indent=2))
