from pathlib import Path
import copy,datetime,hashlib,json,tarfile
D=Path(__file__).resolve().parents[1];W=D.parents[1];OLD=D.parent/'persistent-pool-port-v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def event(x):
 with (D/'ledger.jsonl').open('a') as f:f.write(json.dumps(dict(time=datetime.datetime.now(datetime.timezone.utc).isoformat(),**x))+'\n')
assert not (D/'protocol-R.json').exists()
history=D/'evidence/history/diagnosis'
fixtures=json.loads((OLD/'fixtures.json').read_text())['fixtures']
original=json.loads((history/'evidence/fixtures.json').read_text())
assert fixtures[:2]==original
single=copy.deepcopy(original[0]);single.update(id='h1-request3-singleton',concurrency=1,items=[single['items'][3]],requests=[single['requests'][3]],actual_input_lengths=[109]);single['requests'][0]['id_slot']=0
fixtures.insert(2,single);save(D/'fixtures.json',fixtures)
p=json.loads((history/'protocol-and-identity.json').read_text());cases={}
for role,base in [('B0','B0'),('R','B1'),('R-diagnostic','B1')]:
 case=copy.deepcopy(p['cases'][base]);runtime=W/'runtime/B0' if role=='B0' else D/'candidates'/role/'runtime'
 case['server_argv'][0]=str(runtime/'llama-server');case['server_argv'][2]=str(W/'models/model.gguf');case['server_env']['LD_LIBRARY_PATH']=str(runtime)
 case['artifacts']={str(runtime/Path(k).name):sha(runtime/Path(k).name) for k in case['artifacts']};case['runtime']=role
 cases[role]=case
save(D/'cases.json',cases)
protocol=dict(schema=1,created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),stage='Gate R',scope='Correctness only, no performance claims',cases_sha256=sha(D/'cases.json'),fixtures_sha256=sha(D/'fixtures.json'),original_protocol_sha256=sha(history/'protocol-and-identity.json'),spec_resolution='User authorized current goal plus preserved diagnosis; older standalone R specification was not found',free_generation=dict(cohorts=[f['id'] for f in fixtures],fresh_server_repeats_per_arm_cohort=2,order=['B0','R','R','B0'],per_server=['warmup','measured'],arrival='single atomic prompt-array /completion request, original index order',output_tokens=128,stop_on_environment_or_server_failure=True,finish_declared_R_scope_on_output_difference=True,admission='Every warmup/measured run equals the same-fixture B0 tokens exactly; internal repeatability also required'),numeric=dict(cohorts={'heldout-1':3,'h1-request3-singleton':0},generations=[0,1,2,3],fresh_servers_per_arm_cohort=1,arms=['B0','R'],teacher_force=False,gate='All checkpoints present, same full all-sequence history/batch/physical ubatch/seq/position/worker profile; all finite, equal argmax, maxabs=0 and byte equality',trace='Previously built and hashed observers, original source and ABI identities retained; R changes only CPU Q4 policy'),route=dict(model='One fresh R-diagnostic h1 visit, warmup and measured; actual original Q4 body counter plus retained exact Q4 and Q6 counters',synthetic='One separate probe exercising phase0/1/2/3 and eligible/guarded nr; not model correctness'),bounded_failure_control=dict(when='Any residual numeric or free-generation mismatch',maximum_fresh_visits=2,policy='same first affected fixture under full Q4off, B0 oracle reused; optional all-request teacher forcing only for first unresolved checkpoint',no_downstream_performance=True),cpu_envelope=p['cpus'],housekeeping=p['housekeeping'],bounds=p['bounds'],model=p['model'],normal_build='HINT ON, TRACE OFF; route/observer diagnostics explicitly separate',singleton_note='h1 request3 is diagnostic singleton (109 prompt tokens); single-short is original pool fixture (132), kept separately. Neither substitutes for atomic 8-request cohorts.')
save(D/'protocol-R.json',protocol)
# Restore only the two small preserved observers, never a full old build.
identity=json.loads((history/'diagnostic/build-identity.json').read_text());wanted={}
with tarfile.open(W/'archive/legacy.tar.xz','r|xz') as t:
 entries=json.load(t.extractfile(t.next()))['entries']
 for role in ['B0','B1']:
  key='new-a-performance/output-divergence-diagnosis-v1/diagnostic/trace-'+role+'.so';digest=entries[key]['sha256'];assert digest==identity['artifacts']['/home/codinghuman/projects/'+key];wanted[digest]=role
 for member in t:
  digest=member.name.removeprefix('blobs/')
  if digest not in wanted:continue
  data=t.extractfile(member).read();assert hashlib.sha256(data).hexdigest()==digest
  (history/'diagnostic'/('trace-'+wanted.pop(digest)+'.so')).write_bytes(data)
  if not wanted:break
 assert not wanted
save(D/'evidence/observer-reuse.json',dict(basis='Exact archived probes, matching scalar ABI and unchanged sampler/ubatch layouts; no arithmetic replacement',identities=identity['artifacts'],source_sha256=sha(history/'diagnostic/trace_interpose.cpp')))
event(dict(stage='R-protocol-freeze',protocol_sha256=sha(D/'protocol-R.json'),status='FROZEN_BEFORE_FIRST_INFERENCE',planned_free_servers=16,planned_numeric_servers=4,planned_route_model_servers=1))
(D/'GOAL_STATE.md').write_text('''# Sequential R / E / pool validation

R built and linked, not yet model validated. Separate R-route diagnostic DSO linked. Archived 15 compiler inputs and 46 headers verified.

R protocol frozen before inference: protocol-R.json. Exact fixtures: fixtures.json. Cases: cases.json. New CPU SHA: 45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6. R patch: patches/R-prefill-reference.patch.

Next: code/run_r_gate.py free, then numeric and route validation. Sixteen planned fresh free-generation servers (four fixtures, B0/R/R/B0), four numeric servers, one route model server. Warmup and measured in each. R must pass before A/P; no performance admission yet.

Prepared pool source remains ../persistent-pool-port-v1; no edits. All protected baseline files remain unchanged. User resolved missing older R specification: current goal and preserved diagnosis govern.
''')
print('R protocol FROZEN; probes restored; no model run yet')
