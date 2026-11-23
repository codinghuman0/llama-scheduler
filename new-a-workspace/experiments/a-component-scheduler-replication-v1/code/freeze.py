"""Finalize provenance and unchanged order after fresh admission, before timing."""
import ast,copy,difflib,shutil
from common import *
from analyze import validate_raw
from check import protection
P=D.parent/'a-component-scheduler-attribution-v1'
assert not (D/'results/replication-v1').exists()
protocol=read(D/'replication-protocol.json');names=protocol['replication']['namespaces'];smoke=[]
for mode,filename in [('admission','scheduler-admission.json'),('smoke','smoke-admission.json')]:
 adm=read(D/'evidence'/filename);assert adm['status']=='PASS' and adm['run']==names[mode]
 state=read(D/'results'/names[mode]/'campaigns.json');assert state['status']=='COMPLETE'
 for v in state['completed']:
  spec={k:x for k,x in v.items() if k not in ['path','status']};validate_raw(D/v['path'],spec);smoke.append(v)
assert len(smoke)==8;save(D/'evidence/all-fresh-smoke-audit.json',dict(status='PASS',visits=smoke,not_original_admission=True))
for f in (D/'code').glob('*.py'):ast.parse(f.read_text(),filename=str(f))
for n in ['cases.json','fixtures.json','order.json','identity.json','scheduler-identity.json']:assert sha(D/n)==sha(P/n)
order=read(D/'order.json');assert len(order)==64 and [s['ordinal'] for s in order]==list(range(1,65))
for cond in ['ambient','cpu25']:
 for cohort in ['heldout-1','heldout-2']:
  for arm in protocol['arms']:assert sorted(s['arm_order'].index(arm) for s in order if s['condition']==cond and s['cohort']==cohort and s['arm']==arm)==list(range(4))
protocol['admission']=dict(status='PASS_FRESH',scheduler=names['admission'],linux=names['smoke'],old_admission_reused=False)
save(D/'replication-protocol.json',protocol);shutil.copy2(D/'replication-protocol.json',D/'protocol.json')
old=read(P/'protocol.json');changes={k:dict(original=old.get(k),replication=protocol.get(k)) for k in old.keys()|protocol.keys() if old.get(k)!=protocol.get(k)}
immutable=['primary','clock','tokens_per_request','requests_per_cohort','tokens_per_cohort','arrival','warmup','include','exclude','campaigns','conditions','pairs_per_condition','planned_visits','bootstrap','success','cpu_envelope','controller_cpu','cpu25','bounds','diagnostics','model_sha256','environment_allowlist','invalid_rules','smoke','auxiliary','TTFT','power_gate','ELF_identity','arms','contrasts']
assert all(protocol[k]==old[k] for k in immutable)
save(D/'protocol-diff.json',dict(status='PASS',changed_metadata=changes,unchanged_execution_and_analysis_fields=immutable,original_order_sha256=sha(P/'order.json'),new_order_sha256=sha(D/'order.json'),new_namespaces=names,original_seal_sha256=sha(P/'seal.json'),reason='new output isolation, fresh admission, exactly one replication, no Linux fallback; no metric/workload/statistics changes'))
patch=[];filemap=[]
for f in sorted((D/'code').glob('*.py')):
 original=P/'code'/f.name;oldtext=original.read_text() if original.exists() else ''
 assert not original.exists() or f.stat().st_ino!=original.stat().st_ino
 patch.extend(difflib.unified_diff(oldtext.splitlines(True),f.read_text().splitlines(True),fromfile='original/code/'+f.name if original.exists() else '/dev/null',tofile='replication/code/'+f.name))
 filemap.append(dict(path=str(f.relative_to(D)),sha256=sha(f),original_sha256=sha(original) if original.exists() else None,hardlinked=False))
(D/'harness.patch').write_text(''.join(patch));save(D/'evidence/harness-isolation.json',dict(status='PASS',files=filemap,reason='run names/output roots, fresh admission linkage, no fallback, strict completeness negative test, separate comparisons/reports; visit/HTTP/loader/load/policy implementation unchanged'))
for name in ['visit.py','base_visit.py','contention.py','load.py','selected_session.py','session_common.py','scheduler_evidence.py','prefill_pressure_evidence.py','common.py']:assert sha(D/'code'/name)==sha(P/'code'/name)
R=D.parent/'r-pool-validation-v1';sources={}
for rel,h in read(R/'candidates/R/identity.json')['source_hashes'].items():
 f=R/'candidates/R'/rel;assert sha(f)==h;sources[str(f)]=h
for rel,h in read(R/'candidates/A/identity.json')['source_hashes'].items():
 f=W/rel;assert sha(f)==h;sources[str(f)]=h
patchfile=R/'patches/R-prefill-reference.patch';sources[str(patchfile)]=sha(patchfile);shutil.copy2(patchfile,D/'inputs/frozen-R-prefill-reference.patch')
cases=read(D/'cases.json');save(D/'release-inputs.json',dict(runtime_source_revision='59abec45fe0919de20550ce7cdcf363d9f7bbe5a with preserved E and validated R overlays',B0_source_revision='7a2db1a0cf38e5f4eb278a58c3903d295258d0ea; preserved historical rebuild',source_overlay_hashes=sources,R_build_identity=read(D/'inputs/R-identity.json'),A_build_identity=read(D/'inputs/A-identity.json'),R_validation=read(D/'inputs/R-validation.json'),A_validation=read(D/'inputs/A-validation.json'),cases=cases,scheduler_identity=read(D/'scheduler-identity.json'),model=dict(path=str(W/'models/model.gguf'),sha256=protocol['model_sha256']),roles=dict(A_L='default performance execution',A_S='scoped integration/evaluation')))
reference={}
for f in (D/'reference-original').rglob('*'):
 if f.is_file():
  rel=f.relative_to(D/'reference-original');assert sha(f)==sha(P/rel);reference[str(rel)]=dict(original=str(P/rel),sha256=sha(f))
save(D/'evidence/reference-original-provenance.json',dict(status='PASS',files=reference,original_not_modified=True))
files=[f for sub in ['code','inputs','sources','reference-original'] for f in (D/sub).rglob('*') if f.is_file()]+[D/n for n in ['protocol.json','replication-protocol.json','cases.json','fixtures.json','order.json','identity.json','scheduler-identity.json','protocol-diff.json','harness.patch','release-inputs.json','README.md','reproduce.sh']]+[D/'evidence'/n for n in ['host-before.json','host-contract-comparison.json','all-fresh-smoke-audit.json','harness-isolation.json','reference-original-provenance.json','recalculation-completeness-test.json']]
save(D/'seal.json',dict(stage='registered-before-replication-timing',created=now(),files={str(f.relative_to(D)):sha(f) for f in files}));shutil.copy2(D/'seal.json',D/'evidence/registered-seal.json')
verify_inputs();guard();p=protection();assert p['status']=='PASS';save(D/'evidence/protection-before-timing.json',p)
event('replication-protocol-frozen',order_sha256=sha(D/'order.json'),cases_unchanged=True,new_campaigns=1,planned_visits=64,old_scope_preserved=p['protected_files'])
print('FROZEN REPLICATION',sha(D/'seal.json'),'PROTECTED',p['protected_files'])
