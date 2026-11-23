"""Recalculate historical pairs or analyze a future predeclared pilot; never run a model."""
from pathlib import Path
import argparse,json,random,statistics
D=Path(__file__).resolve().parents[1]
def paired(values,seed=20261122):
 assert values
 rng=random.Random(seed);n=len(values);samples=sorted(statistics.mean(rng.choices(values,k=n)) for _ in range(10000))
 return {'n_pairs':n,'mean_paired_gain_pct':statistics.mean(values),'paired_bootstrap_95_pct':[samples[249],samples[9749]],'faster_pair_fraction':sum(x>0 for x in values)/n,'pair_gains_pct':values}
def analyze(rows):
 result={}
 for condition in ['ambient','cpu25']:
  data=[x for x in rows if x.get('condition')==condition]
  if not data:result[condition]={'status':'NOT_RUN','pairs':0};continue
  if len(data)!=4 or {x['block'] for x in data}!={1,2,3,4} or any(x.get('status')!='COMPLETE' or not x.get('functional_gate_pass') or not x.get('load_valid') for x in data):
   result[condition]={'status':'INCOMPLETE_OR_INVALID','recorded_blocks':len(data),'claims_allowed':False};continue
  gains=[]
  for row in sorted(data,key=lambda x:x['block']):
   b=row['baseline'];c=row['candidate']
   assert b['generated_tokens']==c['generated_tokens']>0 and min(b['cohort_wall_s'],c['cohort_wall_s'])>0
   gains.append(100*((c['generated_tokens']/c['cohort_wall_s'])/(b['generated_tokens']/b['cohort_wall_s'])-1))
  result[condition]={'status':'PILOT_ONLY',**paired(gains)}
 return result
p=argparse.ArgumentParser();p.add_argument('--pilot',type=Path);p.add_argument('--historical',action='store_true');p.add_argument('--self-test',action='store_true');a=p.parse_args()
if a.self_test:
 rows=[{'condition':cond,'block':i,'status':'COMPLETE','functional_gate_pass':True,'load_valid':True,'baseline':{'generated_tokens':1024,'cohort_wall_s':11},'candidate':{'generated_tokens':1024,'cohort_wall_s':10}} for cond in ['ambient','cpu25'] for i in range(1,5)]
 r=analyze(rows);assert all(abs(x['mean_paired_gain_pct']-10)<1e-10 and x['faster_pair_fraction']==1 for x in r.values());assert analyze([])['ambient']['status']=='NOT_RUN';assert analyze(rows[:-1])['cpu25']['status']=='INCOMPLETE_OR_INVALID'
 print('PASS synthetic analyzer checks; these are not measurements')
elif a.historical:
 source=D/'evidence/archive/new-a-performance/persistent-pool/linux-pilot-v1/summary.json';x=json.loads(source.read_text());pairs={}
 for row in x['visits']:
  if row['kind']=='measured':pairs.setdefault(row['block'],{})[row['arm']]=row['metrics']
 assert len(pairs)==4 and all(set(x)=={'LINUX_BASE','LINUX_POOL'} for x in pairs.values())
 out={}
 for metric in ['prefill_tps','decode_tps','http_ms','cpu_time_s']:
  gains=[100*(x['LINUX_POOL'][metric]/x['LINUX_BASE'][metric]-1) for x in pairs.values()];out[metric]={'mean_paired_change_pct':statistics.mean(gains),'changes':gains}
 print(json.dumps({'status':'HISTORICAL_CONFOUNDED_OPENMP_VS_NATIVE','new_candidate_measurement':False,'metrics':out},indent=2))
else:
 path=a.pilot or D/'results/pilot-raw.jsonl';rows=[json.loads(x) for x in path.read_text().splitlines() if x.strip()]
 print(json.dumps({'status':'NOT_RUN_WAITING_NUMERICAL_BASELINE' if not rows else 'PILOT_ANALYSIS','observations':len(rows),'conditions':analyze(rows)},indent=2))
