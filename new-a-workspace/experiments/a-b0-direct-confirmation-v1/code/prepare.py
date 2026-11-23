"""Freeze the protocol and verify prior evidence without changing runtimes."""
import fcntl,json,os,subprocess,sys
from pathlib import Path
from common import *
sys.dont_write_bytecode=True
assert not (D/'seal.json').exists()
with (W/'state/.measurement.lock').open('r') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);no_model_process();guard()
 assert set(CPUS+[11])<=os.sched_getaffinity(0)
 topo=topology();assert len({(topo[str(c)]['physical_package_id'],topo[str(c)]['core_id']) for c in CPUS})==6
 assert all(topo[str(c)]['thread_siblings_list']==f'{c}-{c+1}' for c in CPUS),topo
 # Read and validate the migration manifest, then snapshot all protected payloads.
 migration=read(W/'config/package-manifest.json');cache={};protected={}
 for p in W.rglob('*'):
  if D in p.parents or not p.is_file() or W/'state' in p.parents:continue
  st=p.stat();key=(st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns)
  if key not in cache:cache[key]=sha(p)
  protected[str(p.relative_to(W))]=dict(sha256=cache[key],mode=st.st_mode&0o777,symlink=os.readlink(p) if p.is_symlink() else None)
 for rel,row in migration['files'].items():
  assert protected[rel]['sha256']==row['sha256'] and protected[rel]['mode']==row['mode'],rel
 assert sha(W/migration['archive_path'])==migration['archive_sha256']
 assert sha(W/migration['model_path'])==migration['model_sha256']
 save(D/'evidence/protection-before.json',dict(time=now(),files=protected,migration_manifest_sha256=sha(W/'config/package-manifest.json'),model_inode=(W/'models/model.gguf').stat().st_ino))
 proofs={}
 for arm in ['R','A']:
  val=read(O/f'candidates/{arm}/validation.json');assert val['validation_status']=='COMPATIBLE_IN_TESTED_SCOPE'
  assert sha(O/val['proof'])==val['proof_sha256']
  cp=read(O/val['proof'])
  for rel,digest in cp['artifacts'].items():assert sha(O/rel)==digest,rel
  proofs[arm]=dict(validation=val,verified_artifacts=cp['artifacts'])
 save(D/'evidence/previous-validation-verified.json',dict(status='PASS',proofs=proofs))
 cases=read(D/'cases.json');identity={}
 for arm,case in cases.items():
  identity[arm]={'meaning':'historical source frozen rebuild, not lost original binary' if arm=='B0' else 'validated R arithmetic plus unchanged E, pool off','source_revision':'7a2db1a0cf38e5f4eb278a58c3903d295258d0ea' if arm=='B0' else '59abec45fe0919de20550ce7cdcf363d9f7bbe5a plus preserved overlays','files':{}}
  for p,digest in {**case['artifacts'],**case['system_libraries']}.items():
   assert sha(p)==digest,p
   identity[arm]['files'][p]=dict(realpath=str(Path(p).resolve()),sha256=digest,size=Path(p).stat().st_size,inode=Path(p).stat().st_ino)
  assert 'LD_PRELOAD' not in case['server_env']
  result=subprocess.run([case['server_argv'][0],'--help'],env=case['server_env'],capture_output=True,text=True,timeout=30)
  assert result.returncode==0
  (D/f'evidence/{arm}-help.txt').write_text(result.stdout+result.stderr)
  for flag in [x for x in case['server_argv'][1:] if x.startswith('--')]:assert flag in result.stdout+result.stderr,flag
 save(D/'identity.json',identity)
 oscpu=Path('/proc/cpuinfo').read_text();host=dict(time=now(),environment=guard(),topology=topo,allowed_cpus=sorted(os.sched_getaffinity(0)),cpuinfo=oscpu,uname=list(os.uname()),btf_sha256=sha('/sys/kernel/btf/vmlinux'),lock_inode=os.fstat(lock.fileno()).st_ino,python=sys.version,clock=time.get_clock_info('monotonic').__dict__,scope='No governor/boost/SMT/system changes')
 save(D/'evidence/host-before.json',host)
 order=[]
 for campaign in [1,2]:
  for condition in (['ambient','cpu25'] if campaign==1 else ['cpu25','ambient']):
   for block in range(1,9):
    cohort='heldout-1' if block%2 else 'heldout-2'
    arms=['B0','A'] if block%4 in [1,0] else ['A','B0']
    if campaign==2:arms.reverse()
    for arm in arms:order.append(dict(ordinal=len(order)+1,campaign=campaign,condition=condition,block=block,cohort=cohort,arm=arm,arm_order=arms))
 for c in [1,2]:
  for condition in ['ambient','cpu25']:
   for fid in ['heldout-1','heldout-2']:
    first=[x['arm_order'][0] for x in order if x['campaign']==c and x['condition']==condition and x['cohort']==fid and x['arm']==x['arm_order'][0]]
    assert first.count('A')==first.count('B0')==2
 save(D/'order.json',order)
 protocol=dict(schema=1,created_utc=now(),contrast='A/B0',scheduler='default Linux; no sudo/BPF',runtime_changes='NONE: all B0/R/A binaries and source are immutable; only new harness/documents',fixtures=['heldout-1','heldout-2'],fixture_meaning='Historical labels, not unseen heldout data',primary='actual generated tokens / full cohort HTTP wall seconds',clock='time.monotonic_ns around unchanged HTTPConnection request/read/JSON decode',tokens_per_request=128,requests_per_cohort=8,tokens_per_cohort=1024,arrival='single atomic prompt-array /completion',warmup='one identical excluded cohort on each fresh server',include=['queueing','prefill','decode','policy cost','response complete'],exclude=['model loading','one warmup','identity/proc/environment inspections outside HTTP clock'],campaigns=2,conditions=['ambient','cpu25'],pairs_per_condition=8,planned_visits=64,order='order.json',bootstrap=dict(unit='paired block',stratified_by='cohort',weights=[.5,.5],samples_per_stratum=4,replicates=10000,seed=20261122,quantile='linear interpolation at (n-1)*p, p=.025/.975; random.Random choices within each of h1,h2, reset seed for each campaign-condition'),success=dict(mean_paired_gain_min_pct=5,ci_lower_strictly_gt=0,faster_pairs_min=6,strong_evidence='CI lower>=5',all_four_cells_required=True),other_verdicts=dict(POSITIVE_BELOW_TARGET='all four lower>0 but at least one target gate fails',REGRESSION='all four means negative and all four upper<0',SCOPED_OR_MIXED_RESULT='at least one target pass or positive/negative confirmed cell, not all-four categories above',NO_CONFIRMED_GAIN='otherwise',INCOMPLETE_INVALID='any planned visit missing or invalid'),cpu_envelope=CPUS,controller_cpu=11,cpu25=dict(cpu=10,period_s=.05,cpu_budget_s=.0125,measured_core_range=[.22,.28],normal_priority=True,lifecycle='same start before fresh server, READY then explicit 0.5s stabilization; same warmup; stop after server cleanup; <=180s generator'),bounds=dict(ready_timeout_s=90,http_timeout_s=180,server_lifetime_s=480,min_disk_bytes=1024**3,min_mem_available_kib=3000000,max_cpu_temperature_c=85,thermal_checks='pre/post request, outside primary clock'),diagnostics=dict(perf='on both',log_verbosity=4,OMP_DISPLAY_AFFINITY='TRUE both, bounded team changes',LD_PRELOAD='absent',TRACE='off',A_pressure='required bounded shutdown evidence, real cost included',no_separate_overhead_correction=True),model_sha256=migration['model_sha256'],environment_allowlist='cases.json server_env replaces parent environment; no parent LLAMA_ARG/LD_PRELOAD/OMP/GOMP/KMP inheritance',invalid_rules=['timeout','output mismatch against frozen same-fixture B0 oracle','wrong loaded DSO/model/affinity/policy','cleanup failure','sensor read failure','measured cpu25 outside .22..28','stable environment change','pre/post thermal or resource gate failure'],failure_policy='Stop on any invalid visit; preserve incomplete/invalid campaign/condition and all planned NOT_RUN visits; no replacement pairs or runner edits during timing. A normal pressure fallback is valid if raw audit passes.',smoke='four fresh servers: each arm x each cohort; one warmup and one check, all excluded from timing',auxiliary=['process CPU seconds and seconds/token (not energy)','raw E pressure/actual team choices','background CPU','temperature/frequency/environment brackets','response-defined per-request prompt_n/prompt_ms/predicted_n/predicted_ms; never summed as aggregate throughput'],TTFT='NOT_MEASURED (nonstream)',limitations=['same AMD host and two previously observed cohorts','no A-fixed6 ablation or isolated E/kernel scheduler attribution','no Intel or other model/ISA/chat/quality/energy claim'])
 save(D/'protocol.json',protocol)
 # All executable paths and analysis are sealed together, before smoke and timing.
 seal_files=[p for p in (D/'code').glob('*.py')]+[D/n for n in ['protocol.json','cases.json','fixtures.json','order.json','reproduce.sh']]+list((D/'inputs').rglob('*'))
 seal=dict(time=now(),first_timing_started=False,files={str(p.relative_to(D)):sha(p) for p in seal_files if p.is_file()})
 save(D/'seal.json',seal);event('preregistered',seal_sha256=sha(D/'seal.json'),planned_visits=64)
 print(json.dumps(dict(status='PRE_REGISTERED',protected_files=len(protected),planned_visits=64,seal_sha256=sha(D/'seal.json'))))
