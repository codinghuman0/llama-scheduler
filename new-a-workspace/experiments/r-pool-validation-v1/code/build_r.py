from pathlib import Path
import datetime,difflib,fcntl,hashlib,json,os,shlex,shutil,signal,subprocess,tarfile,time
D=Path(__file__).resolve().parents[1];W=D.parents[1];S=W/'src/llama';B=W/'runtime/B1';H=D/'evidence/history/cpu-build';BUILD=D/'build-cpu'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def diff(a,b,name):return ''.join(difflib.unified_diff(a.splitlines(True),b.splitlines(True),fromfile='a/'+name,tofile='b/'+name))
def interrupt(*_):raise KeyboardInterrupt
signal.signal(signal.SIGTERM,interrupt)
assert os.getuid()!=0 and Path('/sys/kernel/sched_ext/state').read_text().strip()=='disabled'
assert shutil.disk_usage(W).free>1024**3
with (W/'state/.measurement.lock').open('rb') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 BUILD.mkdir(exist_ok=False);(BUILD/'obj').mkdir();(BUILD/'logs').mkdir()
 rel='ggml/src/ggml-cpu/newa-q4-policy.h';old=(S/rel).read_text()
 assert 'if (nr<32) return false;' in old
 new=old.replace('if (nr<32) return false;','return false; // Keep semantic Prefill on the reference body.')
 new=new.replace('prefill_tokens=32 batch_tokens_min=4','prefill_reference=1 batch_tokens_min=4')
 arch='ggml/src/ggml-cpu/arch/x86/repack.cpp';original_arch=(S/arch).read_text()
 diag_add='''
static std::atomic<uint64_t> newa_r_reference_calls[4];
static void newa_r_reference_report() {
    std::fprintf(stderr,"NEWA_R_REFERENCE_BODY calls=%llu/%llu/%llu/%llu\\n",
        (unsigned long long)newa_r_reference_calls[0].load(),
        (unsigned long long)newa_r_reference_calls[1].load(),
        (unsigned long long)newa_r_reference_calls[2].load(),
        (unsigned long long)newa_r_reference_calls[3].load());
}
'''
 diagnostic_arch=original_arch.replace('#include "../../newa-q4-policy.h"','#include "../../newa-q4-policy.h"\n'+diag_add)
 needle='    if (newa_q4_try(n,s,bs,vx,vy,nr,nc)) return;'
 assert original_arch.count(needle)==1
 diagnostic_arch=diagnostic_arch.replace(needle,needle+'''
    static const bool registered = [] { GGML_ASSERT(std::atexit(newa_r_reference_report)==0); return true; }();
    (void) registered;
    const uint32_t route_phase = ggml_backend_cpu_newa_phase_current();
    if (omp_get_thread_num()==0) newa_r_reference_calls[route_phase<4?route_phase:0].fetch_add(1,std::memory_order_relaxed);
''')
 for label,arch_text in [('R',original_arch),('R-diagnostic',diagnostic_arch)]:
  root=D/'candidates'/label;overlay=root/'overlay';runtime=root/'runtime';runtime.mkdir(parents=True)
  for name,text in [(rel,new),(arch,arch_text)]:
   p=overlay/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
  support=overlay/'ggml/src/ggml-cpu/repack.h';shutil.copy2(S/'ggml/src/ggml-cpu/repack.h',support)
  for p in B.iterdir():
   if p.is_file() and not p.name.startswith('libggml-cpu.'):os.link(p,runtime/p.name)
 (D/'patches/R-prefill-reference.patch').write_text(diff(old,new,rel))
 (D/'patches/R-route-diagnostic-only.patch').write_text(diff(original_arch,diagnostic_arch,arch))
 rows=[r for r in json.loads((H/'compile_commands.json').read_text()) if 'ggml-cpu.dir/' in r.get('command','')]
 src_old='/home/codinghuman/projects/new-a-lab/llama-phase-batch-q4-exact-v1'
 with tarfile.open(W/'archive/legacy.tar.xz','r|xz') as t:archive_entries=json.load(t.extractfile(t.next()))['entries']
 # All original compilation units must match archived B1 input bytes.
 input_check={}
 for row in rows:
  name=str(Path(row['file']).relative_to(src_old));key='new-a-lab/llama-phase-batch-q4-exact-v1/'+name
  actual=sha(S/name);assert actual==archive_entries[key]['sha256'],name;input_check[name]=actual
 save(D/'evidence/cpu-compilation-inputs.json',input_check)
 commands=[];object_map={};repack_command=None
 def run(argv,label,timeout=300):
  item={'argv':list(map(str,argv)),'cwd':str(BUILD),'environment':{'PATH':'/usr/bin:/bin','LC_ALL':'C'},'timeout_s':timeout,'label':label};commands.append(item);save(BUILD/'commands.json',commands)
  with (BUILD/'logs'/(label+'.log')).open('w') as log:
   p=subprocess.Popen(item['argv'],cwd=BUILD,env=item['environment'],stdout=log,stderr=log,start_new_session=True)
   try:p.wait(timeout=timeout)
   except BaseException:
    if p.poll() is None:
     os.killpg(p.pid,signal.SIGTERM)
     try:p.wait(timeout=5)
     except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
    raise
  item['returncode']=p.returncode;save(BUILD/'commands.json',commands);assert p.returncode==0,label
  print(label,'PASS',flush=True)
 for i,row in enumerate(rows):
  cmd=shlex.split(row['command']);old_output=cmd[cmd.index('-o')+1];name=str(Path(row['file']).relative_to(src_old));out=BUILD/'obj'/f'{i:02d}-{Path(name).name}.o';object_map[old_output]=str(out)
  cmd=[v.replace(src_old,str(S)) for v in cmd];cmd[cmd.index('-o')+1]=str(out)
  if name==arch:cmd[cmd.index('-c')+1]=str(D/'candidates/R/overlay'/arch);repack_command=list(cmd)
  cmd+=['-MMD','-MF',str(out)+'.d'];run(cmd,f'compile-{i:02d}')
 link=shlex.split((H/'ggml/src/CMakeFiles/ggml-cpu.dir/link.txt').read_text());link=[object_map.get(v,v) for v in link]
 for i,v in enumerate(link):
  if v.startswith('-Wl,-rpath,'):link[i]='-Wl,-rpath,$ORIGIN'
  elif v=='../../bin/libggml-base.so.0.18.0':link[i]=str(B/'libggml-base.so.0.18.0')
 for label in ['R','R-diagnostic']:
  runtime=D/'candidates'/label/'runtime';cmd=list(link);cmd[cmd.index('-o')+1]=str(runtime/'libggml-cpu.so.0.18.0')
  if label=='R-diagnostic':
   diag_cmd=list(repack_command);repack_original=diag_cmd[diag_cmd.index('-o')+1];out=BUILD/'obj/repack-diagnostic.o';diag_cmd[diag_cmd.index('-o')+1]=str(out);diag_cmd[diag_cmd.index('-c')+1]=str(D/'candidates/R-diagnostic/overlay'/arch)
   run(diag_cmd,'compile-diagnostic');cmd=[str(out) if v==repack_original else v for v in cmd]
  run(cmd,'link-'+label)
  for alias in ['libggml-cpu.so.0','libggml-cpu.so']:os.link(runtime/'libggml-cpu.so.0.18.0',runtime/alias)
  save(D/'candidates'/label/'identity.json',{'status':'LINKED_NOT_MODEL_VALIDATED','role':label,'basis':'B1 frozen DSOs with newly built CPU DSO; R Prefill-only fallback; diagnostic variant has counters in the actual reference function body','OpenMP':'ON','arithmetic_options':'Exact archived compile options; path relocation and dependency-file emission only','compile_commands':'../../build-cpu/commands.json','source_hashes':{str(p.relative_to(D/'candidates'/label)):sha(p) for p in (D/'candidates'/label/'overlay').rglob('*') if p.is_file()},'runtime_hashes':{p.name:sha(p) for p in runtime.iterdir() if p.is_file()},'model_hash':json.loads((W/'config/package-manifest.json').read_text())['model_sha256']})
 # Validate actual preprocessor dependencies against original B1 source, excluding the isolated policy edit.
 deps=set()
 for p in (BUILD/'obj').glob('*.d'):
  text=p.read_text().replace('\\\n',' ');deps.update(x for x in shlex.split(text.split(':',1)[1]) if x.startswith(str(S)))
 checked={}
 for path in deps:
  local=Path(path).resolve();name=str(local.relative_to(S));key='new-a-lab/llama-phase-batch-q4-exact-v1/'+name
  assert key in archive_entries and archive_entries[key]['type']=='file',name
  actual=sha(local);assert actual==archive_entries[key]['sha256'],name;checked[name]=actual
 save(D/'evidence/cpu-header-inputs.json',{'status':'PASS','files':checked,'isolated_modified_header':rel,'unchanged_support_header_sha256':sha(S/'ggml/src/ggml-cpu/repack.h')})
 with (D/'ledger.jsonl').open('a') as f:f.write(json.dumps({'time':datetime.datetime.now(datetime.timezone.utc).isoformat(),'stage':'R-build','status':'LINKED_NOT_MODEL_VALIDATED','CPU_units':len(rows),'baseline_header_dependencies_verified':len(checked),'patch':'patches/R-prefill-reference.patch','diagnostic_patch':'patches/R-route-diagnostic-only.patch'})+'\n')
 print('R CPU variants linked; baseline compilation inputs verified.',flush=True)
