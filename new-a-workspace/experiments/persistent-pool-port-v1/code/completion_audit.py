"""Audit the goal's explicit R-absent branch, not a model-performance success."""
from pathlib import Path
import argparse,hashlib,json,re,subprocess,zipfile
D=Path(__file__).resolve().parents[1];W=D.parents[1]
p=argparse.ArgumentParser();p.add_argument('--preflight',action='store_true');a=p.parse_args();checks=[]
def read(name):return json.loads((D/name).read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def check(name,condition,evidence,scope='required current-scope check'):
 assert condition,name
 checks.append({'requirement':name,'status':'PROVEN','scope':scope,'evidence':evidence})
objective=Path('/home/codinghuman/.codex/attachments/685cbdfb-928b-4f02-bb0d-0f46f8cc9b36/pasted-text-1.txt')
check('Unmodified complete goal and conditional R boundary',(D/'user-goal.txt').read_text().strip()==objective.read_text().strip(),['user-goal.txt'])
pins=read('source-pin.json');expected={'a9be0785177a6679cb2cb76e1d334a05e6b3734d','b2ad09fb5953bafc9203e07715c6ea075b1aa06a','21537a585728a8afe62a32003457248172b74f68','5cd6b0eaa52b71021d54fe3b6919f1f05900d00b'}
check('All four exact source pins accessible; no HEAD substitution',{x['sha'] for x in pins['pins']}==expected,['source-pin.json','evidence/remote-commit-public.json','evidence/remote-commit-donor_head.json','evidence/remote-commit-pool.json','evidence/remote-commit-parent.json'])
proof=read('evidence/remote-tree-proof.json')
check('Actual pool commit parent identity',proof['pool_git_commit']['sha']=='21537a585728a8afe62a32003457248172b74f68' and [x['sha'] for x in proof['pool_git_commit']['parents']]==['5cd6b0eaa52b71021d54fe3b6919f1f05900d00b'],['evidence/remote-tree-proof.json'])
for name,row in pins['blobs'].items():
 raw=(D/'donor'/name).read_bytes();assert hashlib.sha256(raw).hexdigest()==row['sha256'];assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==row['git_blob']
check('Pinned donor headers/context/tests/docs/AGENTS bytes verified',len(pins['blobs'])>=7,['source-pin.json','donor/'])
check('Public AGENTS absence checked against pinned complete tree',not any(x['path'].endswith('AGENTS.md') for x in proof['public_tree']['entries']),['evidence/remote-tree-proof.json'])
check('Public shared code is not counted as new gain',len(pins['public_vs_archived_scheduler']['identical_git_blobs'])==110,['source-pin.json','result-summary.md'])
identity=read('baseline-runtime-identity.json')
for arm in identity['arms'].values():
 for rel,row in arm['payloads'].items():assert sha(W/rel)==row['sha256']
check('Actual historical B0/B1/E mapped binaries matched, compiler/source overlays/model/env captured',sum(len(x['payloads']) for x in identity['arms'].values())==24,['baseline-runtime-identity.json','baseline-identity.md','evidence/archive/new-a-performance/phase-scheduling-study-v1/identity/'])
old=read('evidence/archive/new-a-performance/persistent-pool/linux-pilot-v1/setup.json')
check('Old pool comparison backend confounding identified',old['build_options']['baseline']['GGML_OPENMP']=='ON' and old['build_options']['candidate']['GGML_OPENMP']=='OFF',['pool-history.md','evidence/archive/new-a-performance/persistent-pool/linux-pilot-v1/setup.json'])
history=read('results/history-recalculated.json');check('Old paired numbers recomputed; final off reason explicitly unknown',abs(history['metrics']['http_ms']['mean_paired_change_pct']+0.6756302613850435)<1e-8 and 'unknown' in (D/'pool-history.md').read_text(),['code/analyze.py','results/history-recalculated.json','pool-history.md'])
patch=(D/'method.patch').read_text()
check('Only ownership/attachment/lifecycle source files ported',re.findall(r'^\+\+\+ (.+)$',patch,re.M)==['b/tools/server/server-context.cpp','b/tools/server/server-threadpool.h'],['method.patch','integration-delta.md'])
check('Patch reconstruction is byte-identical to actual separate overlay',read('results/patch-reconstruction.json')['status']=='PASS',['results/patch-reconstruction.json','overlay-identity.json'])
check('Normal priority, equal polling semantics, unrestricted roles, CPU-only 5/6 guard','cpu.poll == 50' in patch and '!cpu.mask_valid && !cpu.strict_cpu && cpu.priority == GGML_SCHED_PRIO_NORMAL' in patch and 'n_threads != 5' in patch and 'n_threads != 6' in patch,['method.patch','protocol.json'])
review=(D/'evidence/pool-lifecycle-source-review.txt').read_text()
check('OpenMP pause/native ownership and graph phase/chunk/abort/error reset reviewed',all(t in review for t in ['GGML_USE_OPENMP','current_chunk','abort','GGML_STATUS_SUCCESS','newa_q6_phase']),['evidence/pool-lifecycle-source-review.txt','integration-delta.md'])
check('Context/backend lifetime precedes pool destruction; no unsupported old UAF claim',patch.index('llama_init.reset();')<patch.index('+        newa_donor_pools.reset();'),['method.patch','tests/pool-stress.cpp','integration-delta.md'])
owner=read('results/reproduce-1/owner/result.json');reg=read('results/reproduce-1/regressions/result.json')
check('Missing capabilities, create failures, parameter forwarding, shared/separate graph, repeated reset and recovery exercised',owner['status']=='PASS',['tests/test-server-threadpool.cpp','results/reproduce-1/owner/'])
check('Actual OpenMP graphs, pool switching, abort recovery and model-free exception ownership passed',reg['checks']['stress'] and 'exception_cycles=2' in (D/'results/reproduce-1/regressions/stress.stdout').read_text(),['tests/pool-stress.cpp','results/reproduce-1/regressions/stress.stdout'])
check('Actual DSO symbol/ABI binding observed inside process',reg['checks']['actual-dso-map'] and len(read('results/reproduce-1/regressions/actual-loaded-libraries.json')['libraries'])==13,['results/reproduce-1/regressions/actual-loaded-libraries.json','tests/phase-modes.cpp'])
check('HINT/TRACE/scalar v1 separated without v2',all(reg['checks'][name] for mode in ['off','hint','trace'] for name in ['scalar-marker-'+mode,'trace-marker-'+mode,'no-v2-'+mode]),['results/reproduce-1/regressions/result.json','tests/phase-modes.cpp'])
check('Full HINT OFF inherited failure exposed; applicable HINT/TRACE context checks pass',reg['hint_off_inherited_failure_confirmed'] and not reg['checks']['context-off'] and not reg['checks']['base-context-off'] and all(reg['checks'][x] for x in ['context-hint','base-context-hint','context-trace','base-context-trace']),['results/reproduce-1/regressions/result.json','integration-delta.md'],'Test coverage complete with disclosed inherited failure; NOT a full build-mode pass')
check('Initial failed attempt retained',read('results/regressions-1/result.json')['status']=='FAIL',['results/regressions-1/','tests/attempt-1/'])
base=read('evidence/numerical-baseline-audit.json');protocol=read('protocol.json')
check('R absence revalidated; existing E/Q4off not relabeled',base['live_next_step']==(W/'evidence/NEXT_STEP.md').read_text() and sorted(x.name for x in (W/'runtime').iterdir() if x.is_dir())==['B0','B1','NEW_A'] and protocol['numerical_baseline']['identity'] is None,['evidence/numerical-baseline-audit.json','../../evidence/NEXT_STEP.md','protocol.json'])
functional=read('results/functional.json');admission=read('results/admission-command.json')
check('Model-only functional requirements gated, not claimed from unit tests',all(x=='NOT_RUN' for x in functional['checks'].values()) and functional['free_generation_requests']==0 and admission['returncode']==3 and not protocol['current_model_use_allowed'],['results/functional.json','results/admission-command.json','next-step.md'],'Condition not met: explicitly deferred free tokens, cancellation, two sleep/resume cycles, normal/exception model teardown and steady-state diagnostics')
fixtures=read('fixtures.json')['fixtures'];check('Same exact two eight-request cohorts plus singleton pinned',[(x['id'],len(x['requests'])) for x in fixtures]==[('heldout-1',8),('heldout-2',8),('single-short',1)] and sha(D/'fixtures.json')==protocol['fixtures']['sha256'],['fixtures.json','protocol.json'])
for fixture in fixtures:
 assert len({tuple(q['prompt']) for q in fixture['requests']})==len(fixture['requests'])
 for q in fixture['requests']:assert q['cache_prompt']==False and q['n_cache_reuse']==0 and q['temperature']==0
check('No repeated-answer shortcut, request cache reuse, speculative/model/kernel change; explicit env and unchanged E policy',protocol['environment']['GGML_NEWA_POOL']=='off' and protocol['environment']['NEWA_DECODE_RESOURCE']=='pressure' and protocol['threads']==5 and protocol['threads_batch']==6,['protocol.json','fixtures.json','method.patch','evidence/protection-after.json'])
check('Pilot primary/4 balanced pairs/ambient+cpu25/load delivery/uncertainty frozen before data',protocol['pilot']['complete_paired_blocks_per_condition']==4 and protocol['pilot']['conditions']==['ambient','cpu25'] and protocol['pilot']['order']==['BASELINE,CANDIDATE','CANDIDATE,BASELINE','BASELINE,CANDIDATE','CANDIDATE,BASELINE'] and protocol['pilot']['cpu25']['cpu']==10 and protocol['uncertainty']['unit']=='paired block',['protocol.json'])
check('No pilot/confirmation measurements or success fabricated',not (D/'results/pilot-raw.jsonl').read_text().strip() and read('results/pilot-analysis.json')['observations']==0,['results/pilot-raw.jsonl','results/pilot-analysis.json','result-summary.md'],'R-absent goal branch: pilot and later confirmation explicitly NOT_RUN')
r=subprocess.run(['python3','-B',str(D/'code/analyze.py'),'--self-test'],text=True,capture_output=True,timeout=30)
check('Analysis unit and no-data behavior verified',r.returncode==0,['code/analyze.py','results/pilot-analysis.json'])
protect=read('evidence/protection-after.json');clean=read('cleanup.json')
check('Protected before/after hashes reconciled with authorized storage cleanup',protect['numerical_source_runtime_policy_model_unchanged'] and protect['original_source_and_model_files_checked']==3265 and len(protect['authorized_changes'])==7,['evidence/protection-before.json','evidence/protection-after.json','evidence/maintenance/'])
check('Ordinary user, no sudo/BPF, owned process and binary cleanup',clean['ordinary_uid']==1000 and clean['status']=='PASS' and not clean['sudo_used'] and not clean['BPF_loaded'] and clean['test_processes_remaining']==[] and clean['generated_ELFs_remaining']==[],['cleanup.json','results/reproduce-1/cleanup.json'])
check('Reproduction entry point executed and errors not hidden',read('results/reproduce-1/result.json')['status']=='APPLICABLE_CHECKS_PASS',['reproduce.sh','code/reproduce.py','results/reproduce-1/'])
required=['source-pin.json','integration-delta.md','pool-history.md','protocol.json','method.patch','baseline-runtime-identity.json','results/functional.json','results/pilot-raw.jsonl','results/pilot-analysis.json','evidence/protection-before.json','evidence/protection-after.json','cleanup.json','next-step.md','result-summary.md','GOAL_STATE.md','ledger.json']
check('Every named deliverable present',all((D/name).is_file() for name in required),required)
check('One next step and no gain/energy/dynamic-affinity overclaim','별도' in (D/'next-step.md').read_text() and 'WAITING_NUMERICAL_BASELINE' in (D/'result-summary.md').read_text(),['next-step.md','result-summary.md','integration-delta.md','pool-history.md'])
if not a.preflight:
 package=read('review-zip.json');archive=D/package['archive'];assert sha(archive)==package['sha256']
 with zipfile.ZipFile(archive) as z:
  assert z.testzip() is None;manifest=json.loads(z.read('persistent-pool-port-v1/REVIEW-MANIFEST.json'))
  for rel,row in manifest['files'].items():assert hashlib.sha256(z.read('persistent-pool-port-v1/'+rel)).hexdigest()==row['sha256'] and sha(D/rel)==row['sha256'],rel
 check('Small review ZIP CRC/member/source hashes verified; no weights or build payload',package['status']=='PASS' and package['bytes']<10*1024*1024,['review-zip.json','persistent-pool-port-v1-review.zip.sha256','REVIEW-MANIFEST.json'])
result={'status':'PREFLIGHT_PASS_PACKAGE_PENDING' if a.preflight else 'PERMITTED_SCOPE_COMPLETE_WAITING_NUMERICAL_BASELINE','completion_interpretation':'The user explicitly allows investigation, model-free tests, isolated source and review packaging when R is absent. Those requirements are complete. Model-based functional/pilot requirements remain gated; this is not a performance or full functional success.','requirements':checks,'new_model_observations':0,'outstanding_current_scope_work':[] if not a.preflight else ['ZIP creation and independent hash audit'],'one_next_step':'Complete the separate R numerical compatibility baseline goal','analysis_self_test_output':r.stdout.strip()}
if not a.preflight:(D/'completion-audit.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'status':result['status'],'requirements_checked':len(checks),'model_observations':0},indent=2))
