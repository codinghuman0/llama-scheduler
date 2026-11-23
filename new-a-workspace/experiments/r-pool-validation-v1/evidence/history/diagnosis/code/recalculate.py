#!/usr/bin/env python3
"""Recalculate evidence into a fresh directory, without modifying sealed input."""
import argparse,json
from pathlib import Path
import compare_traces as trace
import quality_diagnostic as quality
D=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text())
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
 raw=[]
 for cohort in ['heldout-1','heldout-2']:
  a=read(D/'evidence'/f'original-{cohort}-B0.json');b=read(D/'evidence'/f'original-{cohort}-B1.json')
  for i,(x,y) in enumerate(zip(a,b)):
   xt,yt=x['response']['tokens'],y['response']['tokens'];assert len(xt)==len(yt)==128
   first=next((j for j,(u,v) in enumerate(zip(xt,yt)) if u!=v),None)
   expected=({3:2,4:7,6:10,7:7} if cohort=='heldout-1' else {3:123,4:10,6:5,7:2}).get(i);assert first==expected
   raw.append(dict(cohort=cohort,index=i,first_difference=first))
 protocol=read(D/'protocol-and-identity.json');repeats=[]
 for visit in read(D/'evidence/fresh-reproduction-summary.json')['visits']:
  folder=D/'runs'/visit['run'];arm=visit['arm'];case=protocol['cases'][arm];original=read(D/'evidence'/f'original-{visit["cohort"]}-{arm}.json');oracle=[v['response']['tokens'] for v in original]
  runtime=read(folder/'runtime.json');expected=list(case['server_argv']);actual=list(runtime['argv']);actual[actual.index('--port')+1]=expected[expected.index('--port')+1]
  assert actual==expected and runtime['environment']==case['server_env']
  assert runtime['loaded_elf_sha256']==dict(case['artifacts'],**case['system_libraries'])
  assert runtime['affinity']==protocol['cpus'] and runtime['scheduler_state']=='disabled'
  for role in ['warmup','measured']:
   values=read(folder/(role+'-responses.json'));assert [v['tokens'] for v in values]==oracle
   assert [v['generation_settings'] for v in values]==[v['response']['generation_settings'] for v in original]
  repeats.append(dict(run=visit['run'],exact_outputs_and_identity=True))
 comparisons=[]
 for file in sorted((D/'evidence').glob('compare-*.json')):
  old=read(file);new=trace.compare(old['a'],old['b'],out)
  for key in ['first_sample_token_difference','call_comparison']:assert new[key]==old[key],(file,key)
  for x,y in zip(new['logits'],old['logits']):assert {k:v for k,v in x.items() if k not in ['a_file','b_file']}=={k:v for k,v in y.items() if k not in ['a_file','b_file']}
  comparisons.append(file.name)
 q=read(D/'quality-v2/summary.json');assert q['status']=='COMPLETE' and len(q['rows'])==20
 for row in q['rows']:
  file=D/'quality-v2'/row['arm']/(row['condition']+'-'+row['prompt']+'-response.json')
  fresh=quality.stats(read(file));assert all(row[k]==v for k,v in fresh.items())
 result=dict(status='PASS',raw32_first_differences=raw,fresh_visits=repeats,trace_comparisons_recomputed=comparisons,quality_responses_recomputed=20,scope='Correctness evidence only, no throughput calculation; aborted quality-v1 not pooled')
 (out/'recalculation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ['raw32_first_differences','fresh_visits','trace_comparisons_recomputed']}))
if __name__=='__main__':main()
