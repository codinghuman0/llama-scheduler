from pathlib import Path
import copy,datetime,difflib,fcntl,hashlib,json,os,shutil,signal,subprocess
D=Path(__file__).resolve().parents[1];W=D.parents[1];S=W/'src/llama';P0=D/'candidates/P';P=D/'candidates/P-padding-fix';R=P/'runtime';B=D/'build-server';OUT=D/'results/pool-padding-fix'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
with (W/'state/.measurement.lock').open('r') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);OUT.mkdir(exist_ok=False);R.mkdir(parents=True);shutil.copytree(P0/'overlay',P/'overlay')
 for p in (P0/'runtime').iterdir():
  if p.name!='libllama-server-impl.so':os.link(p,R/p.name)
 file=P/'overlay/tools/server/server-context.cpp';old=file.read_text();needle='            if (params_base.n_gpu_layers != 0 || !params_base.tensor_buft_overrides.empty() ||'
 assert old.count(needle)==1
 new=old.replace(needle,'''            const bool has_tensor_overrides = std::any_of(params_base.tensor_buft_overrides.begin(), params_base.tensor_buft_overrides.end(),
                [](const llama_model_tensor_buft_override & item) { return item.pattern || item.buft; });
            if (params_base.n_gpu_layers != 0 || has_tensor_overrides ||''');file.write_text(new)
 (D/'patches/P-padding-compatibility.patch').write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/tools/server/server-context.cpp',tofile='b/tools/server/server-context.cpp')))
 commands=[]
 def run(argv,label):
  env={'PATH':'/usr/bin:/bin','LC_ALL':'C','LD_LIBRARY_PATH':str(D/'candidates/R/runtime')};rec=dict(argv=list(map(str,argv)),env=env,label=label);commands.append(rec);save(OUT/'commands.json',commands)
  with (OUT/(label+'.stdout')).open('w') as so,(OUT/(label+'.stderr')).open('w') as se:
   proc=subprocess.Popen(rec['argv'],env=env,stdout=so,stderr=se,start_new_session=True)
   try:proc.wait(timeout=240)
   except BaseException:
    if proc.poll() is None:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
    raise
  rec['returncode']=proc.returncode;save(OUT/'commands.json',commands);assert proc.returncode==0,label;print(label,'PASS',flush=True)
 includes=['-I'+str(S/p) for p in ['common','include','ggml/include','vendor']];r=D/'candidates/R/runtime'
 run(['/usr/bin/c++','-std=c++17','-O2','-UNDEBUG',*includes,D/'code/override-padding-check.cpp','-L'+str(r),'-Wl,-rpath,'+str(r),'-lllama-common','-lllama','-lggml','-lggml-base','-o',OUT/'override-padding-check'],'compile-actual-parser-check')
 args=read(D/'cases-AP.json')['P']['server_argv'][1:];run([OUT/'override-padding-check',*args],'actual-parser-padding-check')
 records=read(B/'commands.json');cmd=next(x['argv'] for x in records if x['label']=='P-context');cmd=[x.replace(str(P0/'overlay'),str(P/'overlay')) for x in cmd];obj=OUT/'7-server-context.cpp.o';cmd[cmd.index('-o')+1]=str(obj);cmd[cmd.index('-MF')+1]=str(obj)+'.d';run(cmd,'corrected-context')
 archive=OUT/'libserver-context.a';shutil.copy2(D/'evidence/history/server-build/pressure/libserver-context.a',archive);run(['/usr/bin/ar','r',archive,obj],'archive');run(['/usr/bin/ranlib',archive],'index')
 cmd=next(x['argv'] for x in records if x['label']=='P-full-server-link');cmd=[str(archive) if x==str(B/'libserver-context.a') else x for x in cmd];cmd[cmd.index('-o')+1]=str(R/'libllama-server-impl.so');run(cmd,'corrected-full-link')
 cases=read(D/'cases-AP.json');save(D/'evidence/cases-AP-before-padding-fix.json',cases);case=copy.deepcopy(cases['P']);case['runtime']='P-padding-fix';case['server_argv'][0]=str(R/'llama-server');case['server_env']['LD_LIBRARY_PATH']=str(R);case['artifacts']={str(R/Path(k).name):sha(R/Path(k).name) for k in case['artifacts']};cases['P']=case;save(D/'cases-AP.json',cases)
 identity=read(P0/'identity.json');identity.update(status='LINKED_PENDING_FRESH_FUNCTIONAL_GATE',source='Prepared P plus minimal null-padding compatibility check; original failed P retained',source_hashes={str(p.relative_to(P)):sha(p) for p in (P/'overlay').rglob('*') if p.is_file()},runtime_hashes={p.name:sha(p) for p in R.iterdir()},case=case,additional_patch='../../patches/P-padding-compatibility.patch',initial_functional_failure='../../results/functional-heldout-1-P',commands='../../results/pool-padding-fix/commands.json');save(P/'identity.json',identity)
 state=read(D/'gate-results.json');state['Pool integration']='NOT_RUN';state['Pool pilot']='NOT_RUN';state['note']='Prepared P failed effective guard due to parser null padding. Failure retained; minimally corrected P revision requires fresh full functional gate, no performance data exists.';save(D/'gate-results.json',state)
 with (D/'ledger.jsonl').open('a') as f:f.write(json.dumps(dict(time=datetime.datetime.now(datetime.timezone.utc).isoformat(),stage='P-padding-compatibility',initial_status='FUNCTIONAL_FAIL',corrected_status='LINKED_PENDING_FRESH_GATE',cause='Common parser pads override array with null entries; empty() rejects valid default. any active pattern/buft still rejected.',policy_workload_unchanged=True))+'\n')
 with (D/'GOAL_STATE.md').open('a') as f:f.write('\nPrepared P failed at real model startup: null-padded override array mistaken for active override. Failure remains results/functional-heldout-1-P. Corrected revision candidates/P-padding-fix retains model/settings/E/pool logic, uses patches/P-padding-compatibility.patch. Actual parser reproducer proves padding and active override rejection. Next: fresh P free gate with revision suffix, then lifecycle; no pilot admitted yet.\n')
