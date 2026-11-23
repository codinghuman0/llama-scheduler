from pathlib import Path
import hashlib,json
D=Path(__file__).resolve().parents[1];W=D.parents[1];A=D/'evidence/archive/new-a-performance/phase-scheduling-study-v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
locations={'B0':'runs/identity-smoke-v1/ambient/block-1/B0/runtime.json','B1':'runs/identity-smoke-v1/ambient/block-1/B1/runtime.json','E':'runs/replay-disk-recovery-v1-campaign-1/ambient/block-1/C/runtime.json'}
out={'status':'PASS_HISTORICAL_RUNTIME_MAPPING','note':'Historical loaded maps matched to current frozen payload hashes. No model process started for this identity check. E is NEW_A runtime; historical C combines this E runtime with observe scheduler.','model':{'path':'../../models/model.gguf','sha256':json.loads((W/'config/package-manifest.json').read_text())['model_sha256']},'arms':{}}
for name,rel in locations.items():
 x=json.loads((A/rel).read_text());runtime='NEW_A' if name=='E' else name;live={};system={}
 for path,digest in x['loaded_elf_sha256'].items():
  if '/projects/' in path:
   p=W/'runtime'/runtime/Path(path).name;actual=sha(p);assert actual==digest,(name,path);live[str(p.relative_to(W))]={'sha256':actual,'historical_loaded_path':path}
  else:system[path]=digest
 out['arms'][name]={'historical_runtime_record':str((A/rel).relative_to(D)),'record_sha256':sha(A/rel),'argv':x['argv'],'environment':x['environment'],'payloads':live,'historical_loaded_system_libraries':system}
b0=json.loads((A/'identity/B0/identity.json').read_text());b1=json.loads((A/'identity/B1.json').read_text());e=json.loads((A/'artifacts/runtime-prefill-pressure-v2/identity.json').read_text())
out['arms']['B0']['source']={k:b0[k] for k in ['source_revision','source_tree','overlay','source_clean','version','configure_argv']}
out['arms']['B1']['source']={'components':b1['components'],'compiler_identity':b1['compiler_identity'],'original_build':b1['original_config']['candidate_build'],'full_record':'evidence/archive/new-a-performance/phase-scheduling-study-v1/identity/B1.json'}
out['arms']['E']['source']={'changed_runtime_file':e['changed_runtime_file'],'arithmetic_kernel_dsos_byte_identical':e['arithmetic_kernel_dsos_byte_identical'],'parent_identity':e['parent_identity'],'source_hashes':e['source_hashes'],'compilation':e['compilation'],'full_record':'evidence/archive/new-a-performance/phase-scheduling-study-v1/artifacts/runtime-prefill-pressure-v2/identity.json'}
(D/'baseline-runtime-identity.json').write_text(json.dumps(out,indent=2)+'\n')
held=A/'runs/heldout-fixtures-v1/fixtures.json';single=A/'runs/regression-fixtures-v1/fixtures.json'
f={'description':'Exact historical requests, reused unchanged for future R/pool comparison; no generation was performed in this goal.','sources':{str(p.relative_to(D)):sha(p) for p in [held,single]},'fixtures':json.loads(held.read_text())['fixtures']+[json.loads(single.read_text())['fixtures'][0]]}
for row in f['fixtures']:
 assert row['concurrency']==len(row['requests']);assert len({tuple(q['prompt']) for q in row['requests']})==len(row['requests'])
 for q in row['requests']:assert q['cache_prompt']==False and q['n_cache_reuse']==0 and q['temperature']==0 and q['n_predict']==128
(D/'fixtures.json').write_text(json.dumps(f,indent=2)+'\n')
p=D/'protocol.json';protocol=json.loads(p.read_text());protocol['pilot']['cohorts']=['heldout-1','heldout-2','heldout-1','heldout-2'];protocol['fixtures']={'path':'fixtures.json','sha256':sha(D/'fixtures.json'),'functional':['heldout-1','heldout-2','single-short'],'pilot':['heldout-1','heldout-2'],'input_tokens':'already tokenized historical fixtures; verify tokenizer/model identity against approved R before any model call'};protocol['model']=out['model'];protocol['server_argv_template']=['@R_OR_CANDIDATE_RUNTIME@/llama-server',*json.loads((W/'config/arms.json').read_text())['C']['argv']];protocol['candidate_environment_delta']={'GGML_NEWA_POOL':'donor','LD_LIBRARY_PATH':'@CANDIDATE_RUNTIME@ (only server ownership DSO changes; all arithmetic DSOs must match R)'};protocol['note']='Protocol and fixtures are frozen before any model run, but admission remains closed until a separately approved R identity and functional gates exist. This review package has no model execution entry point.';p.write_text(json.dumps(protocol,indent=2)+'\n')
print('PASS: all 24 historical project ELF hashes map to B0/B1/NEW_A; exact two cohorts and singleton pinned without inference.')
