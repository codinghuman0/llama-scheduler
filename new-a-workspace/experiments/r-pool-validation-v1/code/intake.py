from pathlib import Path
import hashlib,json,os,shutil,tarfile,datetime
D=Path(__file__).resolve().parents[1];W=D.parents[1];OLD=W/'experiments/persistent-pool-port-v1'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
manifest=json.loads((W/'config/package-manifest.json').read_text())
shutil.copy2(W/'config/package-manifest.json',D/'evidence/workspace-manifest-before.json')
oldfiles={str(p.relative_to(OLD)):sha(p) for p in OLD.rglob('*') if p.is_file()}
protected={'source_manifest_sha256':sha(W/'config/package-manifest.json'),'files':manifest['files'],'archive':{'path':manifest['archive_path'],'sha256':sha(W/manifest['archive_path'])},'model':{'path':'models/model.gguf','sha256':sha(W/'models/model.gguf'),'inode':(W/'models/model.gguf').stat().st_ino},'prepared_pool_files':oldfiles}
assert protected['model']['sha256']==manifest['model_sha256'] and protected['archive']['sha256']==manifest['archive_sha256']
(D/'evidence/protection-before.json').write_text(json.dumps(protected,indent=2)+'\n')
# Extract only needed historical diagnostics and exact compiler inputs.
with tarfile.open(W/manifest['archive_path'],'r|xz') as t:
 e=json.load(t.extractfile(t.next()))['entries'];selected={};prefix='new-a-performance/output-divergence-diagnosis-v1/'
 for key,row in e.items():
  if row['type']!='file':continue
  if key.startswith(prefix):
   rel=key[len(prefix):]
   if rel.startswith('code/') or rel in ['diagnosis-summary.md','protocol-and-identity.json','README.md','GOAL_STATE.md','LOGIT_BLOBS.json','ledger.jsonl','evidence/fixtures.json','evidence/fresh-reproduction-summary.json','evidence/compare-trace-pass-B0-h1--trace-forced-B1-q4off-h1.json','evidence/compare-trace-single-B0-h1r3-r2--trace-single-B1-q4off-h1r3-r2.json','diagnostic/trace_interpose.cpp','diagnostic/sampler-layout.h','diagnostic/build-commands.json','diagnostic/build-identity.json','diagnostic/plan.json']:
    selected[key]='diagnosis/'+rel
  prefix2='new-a-lab/build-phase-batch-q4-exact-v1/cpu-build/'
  if key.startswith(prefix2):
   rel=key[len(prefix2):]
   if rel in ['CMakeCache.txt','compile_commands.json','ggml/src/CMakeFiles/ggml-cpu.dir/link.txt','ggml/src/CMakeFiles/ggml-cpu.dir/flags.make']:selected[key]='cpu-build/'+rel
 need={}
 for key,rel in selected.items():need.setdefault(e[key]['sha256'],[]).append((key,rel))
 for item in t:
  digest=item.name.removeprefix('blobs/')
  if digest not in need:continue
  raw=t.extractfile(item).read();assert hashlib.sha256(raw).hexdigest()==digest
  for key,rel in need.pop(digest):
   target=D/'evidence/history'/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
  if not need:break
 assert not need
(D/'evidence/history-map.json').write_text(json.dumps({key:{'current':str(Path('evidence/history')/rel),'sha256':e[key]['sha256']} for key,rel in selected.items()},indent=2)+'\n')
state={'R':'IMPLEMENTING','E-R':'NOT_RUN','Pool integration':'NOT_RUN','Pool pilot':'NOT_RUN','Adoption':'REJECT_OR_HOLD','note':'R preparation is authorized in this goal; no wait on an external R task. Numeric gates must precede A/P.'}
(D/'gate-results.json').write_text(json.dumps(state,indent=2)+'\n')
(D/'GOAL_STATE.md').write_text('''# R and pool sequential validation

Active stage: Gate R implementation. Existing pool overlay and all protected runtimes stay unchanged.

R: B1 plus only semantic PREFILL fallback to the original Q4 body. A: validated R plus unchanged E policy. P: A plus prepared donor pools. Preserve OpenMP, threads5/6, normal priority, poll50, fixed six-core process envelope.

Current identities: ../persistent-pool-port-v1/baseline-runtime-identity.json and source-pin.json. Protection baseline: evidence/protection-before.json, latest workspace package manifest and migration archive identity.

User confirmed use of this goal and preserved diagnosis because the separate older R specification file is absent. No model run before the numeric protocol is frozen. Next: read restored diagnostic checkpoints and exact CPU compile/link commands; implement a minimal isolated Q4 policy overlay and separate route diagnostics.
''')
(D/'ledger.jsonl').write_text(json.dumps({'time':datetime.datetime.now(datetime.timezone.utc).isoformat(),'stage':'intake','result':'Existing identities/pins verified, protected snapshots recorded, minimal historical sources restored','R_spec_resolution':'User authorized current goal and preserved diagnosis','extracted_files':len(selected)})+'\n')
print(json.dumps({'intake':'PASS','history_files':len(selected),'disk_free_bytes':shutil.disk_usage(W).free,'model_sha256':protected['model']['sha256']}))
