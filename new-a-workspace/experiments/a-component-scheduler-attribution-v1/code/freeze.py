"""Freeze full component protocol after safety admission, before any timing."""
import ast,shutil
from common import *
assert not any((D/'results').glob('attribution-*')),'Timing namespace already exists'
assert read(D/'evidence/scheduler-admission-audit.json')['status']=='PASS'
assert read(D/'evidence/smoke-admission.json')['status']=='PASS'
for f in (D/'code').glob('*.py'):ast.parse(f.read_text(),filename=str(f))
p=read(D/'protocol.json');p.update(branch='full',planned_visits=64,arms=['B0_L','F6_L','A_L','A_S'],admission=dict(scheduler='PASS two cpu25 cohorts',linux='PASS three arms x two cpu25 cohorts',evidence='evidence/scheduler-admission-audit.json'))
p['other_verdicts'].update(CONFIRMED_SCOPED_SYSTEM_GAIN_ONE_CAMPAIGN='Both A_S/B0_L condition gates pass in one campaign',COMPLETE_WITHOUT_FULL_SYSTEM_GATE='Complete valid data; full system gate not passed');save(D/'protocol.json',p)
latin=[['B0_L','F6_L','A_S','A_L'],['F6_L','A_L','B0_L','A_S'],['A_L','A_S','F6_L','B0_L'],['A_S','B0_L','A_L','F6_L']];order=[];count={'ambient':0,'cpu25':0}
for r in range(4):
 for cond in (['ambient','cpu25'] if r%2==0 else ['cpu25','ambient']):
  for fid in (['heldout-1','heldout-2'] if (r+(cond=='cpu25'))%2==0 else ['heldout-2','heldout-1']):
   count[cond]+=1;j=(r+(2 if fid=='heldout-2' else 0))%4
   if cond=='cpu25':j=3-j
   for arm in latin[j]:order.append(dict(ordinal=len(order)+1,campaign=1,condition=cond,block=count[cond],cohort=fid,arm=arm,arm_order=latin[j]))
assert len(order)==64
for cond in count:
 for fid in ['heldout-1','heldout-2']:
  for arm in p['arms']:assert sorted(s['arm_order'].index(arm) for s in order if s['condition']==cond and s['cohort']==fid and s['arm']==arm)==list(range(4))
save(D/'order.json',order)
x=D/'scheduler-selection.md';x.write_text(x.read_text().replace('Admission pending. Privilege test sudo -n true passed; actual attach required before full branch.','Admission PASS on both cohorts under cpu25. Actual selected SCHED_EXT, ordinary loader/launcher/load policy, matching loaded marker/ops/BPF identity, exact B0 output, Prefill/Decode phase bits, zero handoff moves, zero mask/tracking failure, no bypass delta and clean detach. See evidence/scheduler-admission-audit.json.'))
paths=[f for sub in ['code','inputs','sources'] for f in (D/sub).rglob('*') if f.is_file()]+[D/n for n in ['protocol.json','cases.json','fixtures.json','identity.json','scheduler-identity.json','scheduler-selection.md','order.json','experiment-plan.md','reproduce.sh','README.md']]+[D/'evidence/scheduler-program-tags.json']
save(D/'seal.json',dict(stage='final-before-timing',created=now(),files={str(f.relative_to(D)):sha(f) for f in paths}));shutil.copyfile(D/'seal.json',D/'evidence/registered-seal.json');event('protocol-frozen',branch='full',visits=64,campaigns=1,reason='All functional admission complete; no performance timing yet')
verify_inputs();print('FROZEN',sha(D/'seal.json'))
