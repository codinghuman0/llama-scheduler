from pathlib import Path
import fcntl,hashlib,json,os,subprocess
D=Path(__file__).resolve().parents[1];W=Path('/home/codinghuman/projects')
assert os.getuid()!=0 and Path('/sys/kernel/sched_ext/state').read_text().strip()=='disabled'
assert json.loads((D/'evidence/fresh-reproduction-summary.json').read_text())['status']=='COMPLETE'
commands=[]
with (W/'new-a-runs/.measurement.lock').open('r') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 for p in Path('/proc').iterdir():
  if p.name.isdigit():
   try:assert (p/'comm').read_text().strip()!='llama-server'
   except OSError:pass
 for arm,source in [('B0',W/'new-a-lab/llama-original-study-v1'),('B1',W/'new-a-lab/llama-prefill-attention-v2')]:
  out=D/'diagnostic'/f'trace-{arm}.so';assert not out.exists()
  argv=['/usr/bin/c++','-shared','-fPIC','-std=c++17','-O1','-Wall','-Wextra','-Werror','-I'+str(source/'include'),'-I'+str(source/'ggml/include'),'-I'+str(source/'src'),'-I'+str(W/'new-a-lab/llama-phase-barrier/vendor/nlohmann'),'-I'+str(D/'diagnostic')]
  if arm=='B1':argv+=['-DDIAG_B1']
  argv += [str(D/'diagnostic/trace_interpose.cpp'),'-ldl','-o',str(out)]
  p=subprocess.run(argv,capture_output=True,text=True,timeout=90);(D/'diagnostic'/f'compile-{arm}.log').write_text(p.stdout+p.stderr);commands.append(dict(arm=arm,argv=argv,returncode=p.returncode))
  (D/'diagnostic/build-commands.json').write_text(json.dumps(commands,indent=2)+'\n')
  assert p.returncode==0,p.stderr
  print(arm,hashlib.sha256(out.read_bytes()).hexdigest(),out.stat().st_size,flush=True)
inputs=[D/'diagnostic/trace_interpose.cpp',D/'diagnostic/sampler-layout.h']
for source in [W/'new-a-lab/llama-original-study-v1',W/'new-a-lab/llama-prefill-attention-v2']:
 inputs += [source/'include/llama.h',source/'src/llama-batch.h',source/'src/llama-cparams.h',source/'src/llama-sampler.cpp']
identity=dict(kind='Separate LD_PRELOAD observation/teacher-force overlay, not replacement B0/B1',commands=commands,inputs={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},artifacts={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (D/'diagnostic').glob('trace-*.so')},compiler=subprocess.check_output(['/usr/bin/c++','--version'],text=True),same_sampler_source=True,same_ubatch_layout=True)
(D/'diagnostic/build-identity.json').write_text(json.dumps(identity,indent=2)+'\n')
