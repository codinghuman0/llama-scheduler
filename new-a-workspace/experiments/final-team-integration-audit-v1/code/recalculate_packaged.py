"""Recalculate packaged observation extracts. No inference, imports from runtime, or writes."""
import json,math,random,statistics
from pathlib import Path
D=Path(__file__).resolve().parents[1]
def read(p):return json.loads((D/p).read_text())
def q(x,p):
 s=sorted(x);i=(len(s)-1)*p;a=math.floor(i);b=math.ceil(i);return s[a] if a==b else s[a]*(b-i)+s[b]*(i-a)
data=read('evidence/performance-blocks.json');expected=read('evidence/performance-recalculation.json');results=[]
contrasts=['A_L/B0_L','F6_L/B0_L','A_L/F6_L','A_S/A_L','A_S/B0_L']
for campaign in ['original','replication']:
 for cond in ['ambient','cpu25']:
  blocks=[b for b in data['blocks'] if b['campaign']==campaign and b['condition']==cond]
  assert len(blocks)==8 and {b['block'] for b in blocks}==set(range(1,9))
  for b in blocks:
   assert set(b['arms'])=={'B0_L','F6_L','A_L','A_S'}
   for v in b['arms'].values():assert v['tokens']==1024 and abs(v['tps']-v['tokens']/((v['end_ns']-v['start_ns'])/1e9))<1e-10
  strata=[[b for b in blocks if b['cohort']==cohort] for cohort in ['heldout-1','heldout-2']];assert [len(s) for s in strata]==[4,4]
  rng=random.Random(20261122);draws=[[b for s in strata for b in rng.choices(s,k=4)] for _ in range(10000)]
  target=next(c['result']['contrasts'] for c in expected['component_campaigns'] if c['campaign']==campaign)
  for label in contrasts:
   c,a=label.split('/')
   def gain(b):return 100*(b['arms'][c]['tps']/b['arms'][a]['tps']-1)
   gains=[gain(b) for b in blocks];boot=[sum(map(gain,draw))/8 for draw in draws];result=dict(campaign=campaign,condition=cond,contrast=label,mean=statistics.mean(gains),ci=[q(boot,.025),q(boot,.975)],faster=sum(g>0 for g in gains))
   e=next(x for x in target if x['condition']==cond and x['contrast']==label)
   assert abs(e['mean']-result['mean'])<1e-9 and all(abs(a-b)<1e-9 for a,b in zip(e['ci'],result['ci'])) and e['faster']==result['faster'];results.append(result)
for cell in expected['pool_pilot']:
 gains=[100*(x['P']/x['A']-1) for x in cell['raw_tps']];rng=random.Random(20261122);boot=[statistics.mean(rng.choices(gains,k=4)) for _ in range(10000)];assert abs(statistics.mean(gains)-cell['mean'])<1e-9 and all(abs(a-b)<1e-9 for a,b in zip([q(boot,.025),q(boot,.975)],cell['ci']))
print(json.dumps(dict(status='PASS',component_comparisons=len(results),pool_conditions=2,new_model_calls=0,scope='Packaged timestamp/token-count extracts. Original token-array/affinity/load checks are recorded in performance-recalculation.json; this small ZIP does not contain every original raw response.',results=results),ensure_ascii=False,indent=2))
