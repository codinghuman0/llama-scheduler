from pathlib import Path
import hashlib,json,re
D=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
state=read(D/'gate-results.json');assert state['R']==state['E-R']=='COMPATIBLE_IN_TESTED_SCOPE' and state['Pool integration']=='MODEL_VALIDATED'
assert read(D/'evidence/R-free-summary.json')['status']=='PASS'
numeric=read(D/'evidence/R-numeric-summary.json');assert numeric['status']=='PASS' and sum(len(r['logits']) for r in numeric['reports'])==8
for name in ['R-checkpoint.json','AP-functional-checkpoint.json']:
 for rel,digest in read(D/'evidence'/name)['artifacts'].items():assert sha(D/rel)==digest,rel
root=D/'results/pilot-v1';campaign=read(root/'campaign.json');assert campaign['status']=='COMPLETE' and len(campaign['completed'])==16 and campaign['extra_pairs']==0
for rel,digest in read(root/'frozen-before-first-timing.json')['inputs'].items():assert sha(D/rel)==digest,rel
teams=[]
for row in campaign['completed']:
 assert row['valid'] and row['metrics']['actual_generated_tokens']==1024
 spec=row['spec'];folder=root/f"{spec['condition']}-b{spec['block']}-{spec['arm']}"/'server'
 observed={int(x) for x in re.findall(r'NEWA_TEAM .*?team=(\d+)',(folder/'server.stderr.log').read_text())};required={5+j for phase in row['measured_decisions_5_6'] for j,count in enumerate(phase) if count}
 assert required.issubset(observed) and observed.issubset({5,6}),(spec,required,observed)
 assert read(folder/'cleanup.json')['status']=='PASS' and read(folder/'cleanup.json')['returncode']==0
 assert all(x['affinity']==[0,2,4,6,8,10] and x['policy']==0 for x in read(folder/'worker-envelope.json').values())
 teams.append(dict(spec=spec,required=sorted(required),observed=sorted(observed),status='PASS'))
for condition in ['ambient','cpu25']:
 assert len([r for r in campaign['completed'] if r['spec']['condition']==condition])==8
assert read(D/'evidence/protection-after.json')['status']=='PASS' and read(D/'cleanup.json')['status']=='PASS'
smokes=list((D/'reproductions').glob('smoke-*/result.json'));assert smokes and all(read(p)['status']=='PASS' for p in smokes)
result=dict(status='PASS',protected_checkpoints_unchanged=True,frozen_pilot_inputs_unchanged=True,measured_cohorts=16,paired_blocks=8,extra_pairs=0,all_timing_outputs_and_loads_valid=True,actual_OpenMP_teams_and_thread_envelope=teams,reproduction_smokes=[str(p.relative_to(D)) for p in smokes],no_B0_performance_claim=True,retained_failures=['results/functional-heldout-1-P','results/lifecycle-P'],final_states=state)
(D/'completion-audit.json').write_text(json.dumps(result,indent=2)+'\n');print('Completion audit PASS: numerical/model/paired/raw/protection/reproduction checks')
