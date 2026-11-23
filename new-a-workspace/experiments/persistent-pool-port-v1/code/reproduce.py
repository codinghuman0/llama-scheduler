from pathlib import Path
import argparse,datetime,hashlib,json,os,signal,subprocess,sys
D=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description='Review package: verify or model-free tests only. No model/BPF/sudo path.')
p.add_argument('--workspace',type=Path,default=D.parents[1])
sub=p.add_subparsers(dest='mode',required=True)
sub.add_parser('verify');sub.add_parser('admission')
s=sub.add_parser('model-free');s.add_argument('--output',type=Path,required=True)
a=p.parse_args();W=a.workspace.resolve()
assert os.getuid()!=0,'Use an ordinary account'
if a.mode=='admission':
 print(json.dumps({'status':'WAITING_NUMERICAL_BASELINE','model_execution_enabled':False,'next_step':'Finish the separate R compatibility gate; then rebase this pool-only patch onto frozen R. This entry point never runs a model.'},indent=2));raise SystemExit(3)
def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def check():
 overlay=json.loads((D/'overlay-identity.json').read_text())
 assert sha(W/'src/llama/tools/server/server-context.cpp')==overlay['base_server_sha256']
 assert sha(D/'overlay/tools/server/server-context.cpp')==overlay['candidate_server_sha256']
 assert sha(D/'overlay/tools/server/server-threadpool.h')==overlay['donor_header_sha256']
 for name,digest in overlay['unchanged_components'].items():assert sha(W/'src/llama'/name)==digest,name
 manifest=json.loads((W/'config/package-manifest.json').read_text())
 for name,item in manifest['files'].items():
  if name.startswith(('runtime/','scheduler/')):assert sha(W/name)==item['sha256'],name
 print('PASS frozen source/runtime and exact candidate identities',flush=True)
check()
if a.mode=='verify':raise SystemExit(0)
out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
script_env=dict(os.environ);script_env['NEWA_WORKSPACE']=str(W)
def stop(*_):raise KeyboardInterrupt
signal.signal(signal.SIGTERM,stop)
status='FAIL';codes={}
try:
 for script,label in [('run_model_free.py','owner'),('run_regressions.py','regressions')]:
  proc=subprocess.Popen([sys.executable,'-B',str(D/'code'/script),'--output',str(out/label)],env=script_env,start_new_session=True)
  try:code=proc.wait(timeout=900)
  except BaseException:
   if proc.poll() is None:
    os.killpg(proc.pid,signal.SIGTERM)
    try:proc.wait(timeout=15)
    except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
   raise
  codes[label]=code
 status='APPLICABLE_CHECKS_PASS' if all(v==0 for v in codes.values()) else 'FAIL'
finally:
 removed=[]
 for file in out.rglob('*'):
  if not file.is_file() or file.is_symlink():continue
  with file.open('rb') as f:magic=f.read(4)
  if magic==b'\x7fELF':
   removed.append({'path':str(file.relative_to(out)),'sha256':sha(file),'bytes':file.stat().st_size});file.unlink()
 (out/'cleanup.json').write_text(json.dumps({'generated_test_binaries_removed':removed,'source_commands_logs_retained':True,'model_loaded':False,'BPF_loaded':False},indent=2)+'\n')
 (out/'result.json').write_text(json.dumps({'status':status,'returncodes':codes,'scope':'model-free only; inspect regressions/result.json for inherited HINT OFF limitation','completed':datetime.datetime.now(datetime.timezone.utc).isoformat()},indent=2)+'\n')
raise SystemExit(0 if status=='APPLICABLE_CHECKS_PASS' else 1)
