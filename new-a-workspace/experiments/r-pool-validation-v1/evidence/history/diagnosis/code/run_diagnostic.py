#!/usr/bin/env python3
import argparse,copy,fcntl,hashlib,json,os
from pathlib import Path
import reproduce_frozen as run
D=Path(__file__).resolve().parents[1];W=Path('/home/codinghuman/projects')
parser=argparse.ArgumentParser();parser.add_argument('--arm',required=True,choices=['B0','B1']);parser.add_argument('--name',required=True);parser.add_argument('--cohort',default='heldout-1');parser.add_argument('--teacher-force',action='store_true');parser.add_argument('--q6-mode',choices=['off','prefill','phase_batch']);parser.add_argument('--q4-mode',choices=['off','prefill','phase_batch']);parser.add_argument('--single-index',type=int,choices=range(8));parser.add_argument('--operator-probe',action='store_true');args=parser.parse_args()
assert '/' not in args.name and '..' not in args.name
protocol=run.read(D/'protocol-and-identity.json');fixture=next(x for x in run.read(D/'evidence/fixtures.json') if x['id']==args.cohort);case=copy.deepcopy(protocol['cases'][args.arm])
for flag,value in [('GGML_NEWA_Q6_BATCH',args.q6_mode),('GGML_NEWA_Q4_TILE32',args.q4_mode)]:
 if value is not None:assert args.arm=='B1';case['server_env'][flag]=value
oracle=run.read(D/'evidence'/f'original-{args.cohort}-B0.json');forced=[r['response']['tokens'] for r in oracle]
if args.single_index is not None:
 fixture=copy.deepcopy(fixture);fixture['items']=[fixture['items'][args.single_index]];fixture['requests']=[fixture['requests'][args.single_index]];fixture['concurrency']=1;forced=[forced[args.single_index]]
overlay=D/'diagnostic'/f'trace-{args.arm}.so';identity=run.read(D/'diagnostic/build-identity.json');h=identity['artifacts'][str(overlay)]
config=dict(prompts=[r['prompt'] for r in fixture['requests']],forced_tokens=forced,teacher_force=args.teacher_force,target_request=0 if args.single_index is not None else (3 if args.cohort=='heldout-1' else 7),max_logit_generation=3,max_trace_calls=16)
with (D/'ledger.jsonl').open('a') as f:f.write(json.dumps(dict(id=args.name,status='REGISTERED_BEFORE_RUN',hypothesis='Bounded same-input logit and sampler observation; pass-through or explicit all-request teacher forcing',arm=args.arm,cohort=args.cohort,single_index=args.single_index,teacher_force=args.teacher_force,q6_mode=args.q6_mode,q4_mode=args.q4_mode,overlay_sha256=h,config=config),ensure_ascii=False)+'\n')
diag=dict(overlay=str(overlay),overlay_sha256=h,config=config)
if args.operator_probe:
 assert args.arm=='B1'
 extra=D/'diagnostic/operator-probe.so';diag['extra_overlays']={str(extra):run.read(D/'diagnostic/operator-build.json')['hashes'][str(extra)]}
os.sched_setaffinity(0,{11})
with (W/'new-a-runs/.measurement.lock').open('r') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 result=run.visit(case,fixture,D/'runs'/args.name,diag)
reference=forced if args.teacher_force else [r['response']['tokens'] for r in run.read(D/'evidence'/f'original-{args.cohort}-{args.arm}.json')]
if args.single_index is not None and not args.teacher_force:reference=[reference[args.single_index]]
original_warmup=[r['response']['tokens'] for r in run.read(D/'evidence'/f'original-{args.cohort}-{args.arm}.json')]
if args.single_index is not None:original_warmup=[original_warmup[args.single_index]]
row=dict(run=args.name,arm=args.arm,cohort=args.cohort,single_index=args.single_index,teacher_force=args.teacher_force,measured_matches_reference=result['measured']==reference,warmup_matches_original=result['warmup']==original_warmup,different_request_indices=[i for i,(a,b) in enumerate(zip(result['measured'],reference)) if a!=b],reference_kind='B0 forced output' if args.teacher_force else 'original own-arm output')
run.save(D/'runs'/args.name/'diagnostic-result.json',row)
with (D/'ledger.jsonl').open('a') as f:f.write(json.dumps(dict(id=args.name,status='COMPLETE',observation=row,next='Inspect event coverage and exact all-sequence batch history before interpreting logit differences'),ensure_ascii=False)+'\n')
print(json.dumps(row),flush=True)
