from pathlib import Path
import copy,datetime,fcntl,hashlib,json,shlex
D=Path(__file__).resolve().parents[1];W=D.parents[1];S=W/'src/llama';O=D.parent/'persistent-pool-port-v1';P=D/'candidates/P';R=P/'runtime';A=D/'candidates/A/runtime';BUILD=D/'build-server';H=D/'evidence/history/server-build'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
with (W/'state/.measurement.lock').open('r') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 commands=read(BUILD/'commands.json');assert commands[-1]['label']=='P-full-server-link' and all(c.get('returncode')==0 for c in commands)
 assert read(BUILD/'parent-relink.json')['byte_identical'] and sha(BUILD/'parent-relinked.so')==sha(A/'libllama-server-impl.so')
 for p in A.iterdir():
  if p.name!='libllama-server-impl.so':assert sha(p)==sha(R/p.name),p.name
 for p in (O/'overlay').rglob('*'):
  if p.is_file():assert sha(p)==sha(P/'overlay'/p.relative_to(O/'overlay'))
 frozen=read(H/'pressure/identity.json');source_hashes=frozen['source_hashes'];checks={};aliases={}
 src='/home/codinghuman/projects/new-a-lab/llama-phase-barrier'
 for dep in (BUILD/'obj').glob('*.d'):
  for token in shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1]):
   path=Path(token)
   if not path.is_absolute() or not path.exists():continue
   path=path.resolve()
   if not path.is_relative_to(S):continue
   rel=str(path.relative_to(S));key=src+'/'+rel
   if rel=='tools/server/newa-prefill-pressure.h':
    key='/home/codinghuman/projects/new-a-performance/phase-scheduling-study-v1/artifacts/runtime-prefill-pressure-v2/src/newa-prefill-pressure.h';aliases[rel]=key
   assert key in source_hashes,(key,'missing historical identity')
   assert sha(path)==source_hashes[key],key;checks[rel]=sha(path)
 save(BUILD/'unchanged-header-check.json',dict(status='PASS',headers=checks,historical_overlay_path_aliases=aliases,initial_check_failure='Missing path alias for consolidated unchanged pressure header; no content/build change needed'))
 cases=read(D/'cases-AP.json');case=copy.deepcopy(cases['A']);case['runtime']='P';case['server_argv'][0]=str(R/'llama-server');case['server_env'].update(LD_LIBRARY_PATH=str(R),GGML_NEWA_POOL='donor');case['artifacts']={str(R/Path(k).name):sha(R/Path(k).name) for k in case['artifacts']};cases['P']=case;save(D/'cases-AP.json',cases)
 save(P/'identity.json',dict(status='FULL_SERVER_LINKED_NOT_MODEL_VALIDATED',parent_relink_byte_identical=True,arithmetic_DSOs_identical_to_A=True,source='Exactly previously prepared donor pool overlay on unchanged E',source_hashes={str(p.relative_to(P)):sha(p) for p in (P/'overlay').rglob('*') if p.is_file()},runtime_hashes={p.name:sha(p) for p in R.iterdir()},case=case,commands='../../build-server/commands.json',macro_prefix_map='Non-arithmetic path mapping restores original __FILE__ spellings; unmodified E relink verified byte identity'))
 with (D/'ledger.jsonl').open('a') as f:f.write(json.dumps(dict(time=datetime.datetime.now(datetime.timezone.utc).isoformat(),stage='P-build',status='FULL_SERVER_LINKED',unchanged_E_relink_byte_identical=True,header_path_alias_corrected=True,unchanged_headers=len(checks)))+'\n')
 with (D/'GOAL_STATE.md').open('a') as f:f.write('\nP linked. Unmodified parent E re-link is byte-identical; all A/P arithmetic libraries are identical validated R. Header alias audit corrected without rebuild. Next: real R-DSO unit tests, P free generation, A/P lifecycle diagnostic, then fixed pilot if all gates pass.\n')
 print('P build identity finalized; unchanged headers',len(checks))
