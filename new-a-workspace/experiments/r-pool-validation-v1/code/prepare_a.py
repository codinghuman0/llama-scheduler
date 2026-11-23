from pathlib import Path
import copy,datetime,hashlib,json,os
D=Path(__file__).resolve().parents[1];W=D.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
assert read(D/'gate-results.json')['R']=='COMPATIBLE_IN_TESTED_SCOPE'
checkpoint=read(D/'evidence/R-checkpoint.json')
for rel,h in checkpoint['artifacts'].items():assert sha(D/rel)==h
R=D/'candidates/R/runtime';A=D/'candidates/A';runtime=A/'runtime';runtime.mkdir(parents=True,exist_ok=False)
for p in R.iterdir():
 source=W/'runtime/NEW_A'/p.name if p.name=='libllama-server-impl.so' else p
 os.link(source,runtime/p.name)
case=copy.deepcopy(read(D/'cases.json')['R']);case['runtime']='A';case['server_argv'][0]=str(runtime/'llama-server');case['server_argv'][case['server_argv'].index('--server-compute-profile-mode')+1]='phase';case['server_env'].update(LD_LIBRARY_PATH=str(runtime),NEWA_DECODE_RESOURCE='pressure');case['artifacts']={str(runtime/Path(k).name):sha(runtime/Path(k).name) for k in case['artifacts']}
assert sha(runtime/'libllama-server-impl.so')=='9204b0d4e45d4b5437c61417afe912d55618ce62ece6b6adf83ca7967dbe8cfc'
assert sha(runtime/'libggml-cpu.so')==checkpoint['identity']['runtime_hashes']['libggml-cpu.so']
save(D/'cases-AP.json',{'A':case})
save(A/'identity.json',dict(status='EXISTING_FULLY_LINKED_E_SERVER_WITH_VALIDATED_R_CPU',source='Unmodified frozen E server and pressure helper. New composition only; all other shared libraries are the validated R stack.',runtime_hashes={p.name:sha(p) for p in runtime.iterdir()},case=case,source_hashes={str(p.relative_to(W)):sha(p) for p in [W/'src/llama/tools/server/server-context.cpp',W/'src/llama/tools/server/newa-prefill-pressure.h',W/'src/llama/tools/server/server-scx.h']},R_checkpoint_sha256=sha(D/'evidence/R-checkpoint.json')))
with (D/'ledger.jsonl').open('a') as f:f.write(json.dumps(dict(time=datetime.datetime.now(datetime.timezone.utc).isoformat(),stage='A-compose',source_delta='none',cpu='validated R',server='byte-identical frozen E',status='PENDING_FREE_EQUALITY'))+'\n')
print('A composed: byte-identical E server plus validated R CPU, E thresholds unchanged')
