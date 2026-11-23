import datetime,hashlib,json,os,shutil,subprocess
from pathlib import Path
D=Path(__file__).resolve().parents[1];W=Path('/home/codinghuman/projects');S=W/'new-a-performance/phase-scheduling-study-v1';A=W/'new-a-performance/phase-scheduler-review-v1'
def read(p):return json.loads(p.read_text())
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
assert os.getuid()!=0 and Path('/sys/kernel/sched_ext/state').read_text().strip()=='disabled'
shutil.copyfile('/home/codinghuman/.codex/attachments/68cfc345-2e11-4ef1-b377-43065097142f/pasted-text-1.txt',D/'evidence/user-request.txt')
freeze=read(S/'selection-freeze.json');registration=read(S/'recovery/registration.json');protected={**freeze['protected'],**registration['protected']}
for x in read(A/'evidence/preservation-after.json')['files']:protected[x['path']]=x['after']
for p in A.rglob('*'):
 if p.is_file():protected[str(p)]=sha(p)
protected[str(W/'model.gguf')]='f3bdf9cf31dee4b57ae4e455a1cb0d01b5c2c1b50d72d3112141c195506c2840'
fixtures=read(S/'runs/heldout-fixtures-v1/fixtures.json')['fixtures'];comparisons=[]
for i,f in enumerate(fixtures,1):
 rows={a:read(S/f'runs/heldout-reference-v1/ambient/block-{i}/{a}/measured-responses.json') for a in ['B0','B1']}
 for a in rows:
  p=S/f'runs/heldout-reference-v1/ambient/block-{i}/{a}/measured-responses.json';protected[str(p)]=sha(p)
  shutil.copyfile(p,D/'evidence'/f'original-{f["id"]}-{a}.json')
 for j,(b0,b1) in enumerate(zip(rows['B0'],rows['B1'])):
  x,y=b0['response'],b1['response'];first=next((k for k,(a,b) in enumerate(zip(x['tokens'],y['tokens'])) if a!=b),None)
  assert len(x['tokens'])==len(y['tokens'])==128
  expected=({3:2,4:7,6:10,7:7} if i==1 else {3:123,4:10,6:5,7:2}).get(j);assert first==expected
  comparisons.append(dict(cohort=f['id'],request_index=j,prompt_id=f['items'][j]['id'],first_difference_0based=first,reference_report_match=True,input_tokens=f['requests'][j]['prompt'],input_sha256=hashlib.sha256(json.dumps(f['requests'][j]['prompt'],separators=(',',':')).encode()).hexdigest(),B0_token=None if first is None else x['tokens'][first],B1_token=None if first is None else y['tokens'][first],generation_settings_identical=x['generation_settings']==y['generation_settings'],B0_generation_settings=x['generation_settings'],B1_generation_settings=y['generation_settings'],B0_stop=x['stop_type'],B1_stop=y['stop_type'],B0_input_length=x['tokens_evaluated'],B1_input_length=y['tokens_evaluated']))
save(D/'evidence/existing-first-divergences.json',dict(status='PASS_INDEPENDENT_RAW_RECALCULATION',responses=32,comparisons=comparisons))
save(D/'evidence/fixtures.json',fixtures)
for p,h in protected.items():assert Path(p).is_file() and sha(p)==h,('Protected identity mismatch',p)
repo_rows=[]
for r in read(A/'evidence/preservation-before.json')['repositories']:
 out={'path':r['path']}
 for k,args in {'head':['rev-parse','HEAD'],'status':['status','--porcelain=v1','-uall'],'refs':['show-ref']}.items():
  q=subprocess.run(['git','-C',r['path'],*args],env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'},capture_output=True,text=True);out[k]=dict(rc=q.returncode,stdout=q.stdout,stderr=q.stderr)
 repo_rows.append(out)
save(D/'evidence/preservation-before.json',dict(created=datetime.datetime.now(datetime.timezone.utc).isoformat(),protected=protected,repositories=repo_rows))
cases={a:{k:v for k,v in freeze['cases'][a].items() if k in ['runtime','server_argv','server_env','artifacts','system_libraries','compute_profile','scheduler']} for a in ['B0','B1']}
protocol=dict(scope='CORRECTNESS_ROOT_CAUSE_DIAGNOSTIC_NOT_THROUGHPUT_BENCHMARK',cases=cases,cpus=[0,2,4,6,8,10],housekeeping=[11],model=dict(path=str(W/'model.gguf'),sha256=protected[str(W/'model.gguf')]),frozen_selection_sha256=sha(S/'selection-freeze.json'),review_zip_sha256=sha(A/'phase-scheduler-review-v1.zip'),first_reproduction=dict(cohorts=['heldout-1','heldout-2'],fresh_server_repeats_per_runtime_cohort=2,order=['B0','B1','B1','B0'],per_server=['warmup','measured'],arrival='single atomic prompt-array /completion request, original index order',payload='Exact stored token arrays/settings; id_slot removed from batched payload as original runner',sampling='record effective server generation_settings and tokenizer equality',no_throughput_claim=True),bounds=dict(server_ready_timeout_s=90,http_timeout_s=180,server_lifetime_timeout_s=480,min_free_disk_bytes=512*1024**2,min_mem_available_kib=3000000,max_cpu_temperature_c=85),subsequent_diagnostics='Freeze each minimal diagnostic hypothesis and inputs in ledger before executing. Instrumentation only; preserve original binaries and oracle.',forbidden=['benchmark campaigns','BPF load','sudo','package install','system setting changes','model replacement','scheduler activation','git commit/push','new optimizations'])
save(D/'protocol-and-identity.json',protocol)
save(D/'evidence/build-availability.json',dict(B0_objects_present=len(list((W/'new-a-lab/build-original-study-v1').rglob('*.o'))),B1_original_build_objects_present=len(list((W/'new-a-lab/build-phase-barrier/openmp').rglob('*.o'))),retained_decode_overlay_objects=len(list((S/'artifacts/runtime-decode-cost-v1/obj').glob('*.o'))),interpretation='Frozen B0/B1 runnable ELF/DSO hashes pass. Prior cache cleanup removed CMake intermediates; any rebuilt diagnostic binary will have a separate identity, never replace frozen binaries.'))
(D/'ledger.jsonl').write_text(json.dumps(dict(id='D00',hypothesis='Recalculate recorded first mismatches before any diagnostic change',change='none',inputs='32 frozen heldout responses and exact input token arrays',observation='Both cohorts match reported request indices and first token differences; effective generation settings agree',interpretation='Existing discrepancy confirmed, cause not established',next='Fresh-server within-runtime repeatability under exact cohort/settings'),ensure_ascii=False)+'\n')
(D/'GOAL_STATE.md').write_text('# Output divergence diagnosis\n\nActive. Existing 32-output discrepancy independently verified. Frozen B0/B1 binaries available; originals protected. Next: limited fresh-server repeatability, then matched-input first-divergence diagnostics. No performance benchmark or scheduler change.\n')
print(json.dumps(dict(status='INITIALIZED',protected=len(protected),raw_responses=32,first_divergences=[(x['cohort'],x['request_index'],x['first_difference_0based']) for x in comparisons if x['first_difference_0based'] is not None])))
