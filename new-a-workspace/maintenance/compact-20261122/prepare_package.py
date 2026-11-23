from pathlib import Path
import os,json,shutil,hashlib,ast,difflib
W=Path('/home/codinghuman/projects/new-a-workspace');D=Path(__file__).resolve().parent
L=W/'new-a-lab';S=W/'new-a-performance/phase-scheduling-study-v1';R=W/'new-a-llm-scheduler/tools/sched_ext'
for name in ['src/llama','runtime','scheduler/include','tools','config','evidence','state']:(W/name).mkdir(parents=True,exist_ok=True)
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
provenance={}
def copy(src,dst):
 dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);provenance[str(dst.relative_to(W))]={'source':str(src.relative_to(W)),'sha256':sha(dst)}
base=L/'llama-phase-barrier';target=W/'src/llama'
exclude={'.git','.github','docs','media','models','results','benches','ci','skills','conversion','gguf-py'}
for p in base.iterdir():
 if p.name in exclude:continue
 if p.is_dir():shutil.copytree(p,target/p.name,dirs_exist_ok=True)
 elif p.is_file():copy(p,target/p.name)
# Reconstitute the selected runtime components in one standalone source tree.
b1=json.loads((S/'identity/B1.json').read_text())
for component in b1['components']:
 source=L/Path(component['source']).name
 for rel,digest in component['source_hashes'].items():
  selected=(component==b1['components'][0] and rel.startswith('ggml/')) or (component==b1['components'][1] and rel.startswith('src/')) or (component==b1['components'][2] and rel.startswith('tools/'))
  if selected:
   assert sha(source/rel)==digest;copy(source/rel,target/rel)
E=S/'artifacts/runtime-prefill-pressure-v2'
for name in ['server-context.cpp','newa-prefill-pressure.h']:copy(E/'src'/name,target/'tools/server'/name)
# Retained UI assets avoid network/frontend build dependencies in later rebuilds.
for name in ['ui.cpp','ui.h']:copy(S/'artifacts/runtime-decode-cost-v1/ui'/name,target/'tools/ui'/('frozen-'+name))
old=(target/'tools/ui/CMakeLists.txt').read_text()
new='''# Retained assets from the validated runtime; no network or Node build required.\nadd_library(llama-ui STATIC frozen-ui.cpp frozen-ui.h)\nset_target_properties(llama-ui PROPERTIES POSITION_INDEPENDENT_CODE ON)\ntarget_compile_features(llama-ui PRIVATE cxx_std_17)\ntarget_include_directories(llama-ui PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})\n'''
# frozen-ui.cpp includes ui.h, so retain that header name as well.
copy(S/'artifacts/runtime-decode-cost-v1/ui/ui.h',target/'tools/ui/ui.h')
(target/'tools/ui/CMakeLists.txt').write_text(new)
(D/'offline-ui.patch').write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/tools/ui/CMakeLists.txt',tofile='b/tools/ui/CMakeLists.txt')))
copy(L/'build-phase-barrier/openmp/common/build-info.cpp',target/'common/frozen-build-info.cpp')
# Runtime files stay byte-identical. Equal files share inodes, not external symlinks.
seen={};runtime_proof={}
for arm,oldbin in [('B0',S/'artifacts/B0/bin'),('B1',S/'artifacts/B1/bin'),('NEW_A',E/'runtime/bin')]:
 out=W/'runtime'/arm;out.mkdir()
 for p in oldbin.iterdir():
  if not p.is_file():continue
  digest=sha(p);q=out/p.name;key=(digest,p.stat().st_mode&0o777)
  if key in seen:os.link(seen[key],q)
  else:os.link(p.resolve(),q);seen[key]=q
  runtime_proof[str(q.relative_to(W))]={'sha256':digest,'original':str(p.relative_to(W))}
# Guarded selected-child scheduler, unchanged BPF policy and lifecycle sources.
obs=L/'build-idle-handoff-v1/observe'
for p in obs.iterdir():
 if p.name=='loader':continue
 if p.is_file():copy(p,W/'scheduler'/p.name)
for p in (R/'include').iterdir():
 if p.is_file():copy(p,W/'scheduler/include'/p.name)
for name in ['new_a.h','mask_dump.h']:copy(R/'new_a'/name,W/'scheduler/include'/name)
for name in ['llama_scx_child.c']:copy(R/name,W/'scheduler'/name)
copy(R/'new_a_portable/cpu_probe.c',W/'scheduler/cpu_probe.c')
for old,newname in [('llama_scx_child','llama_scx_child'),('cpu-probe','cpu-probe')]:copy(W/'new-a-runs/amd12-validation/build'/old,W/'scheduler'/newname)
copy(W/'new-a-runs/amd12-validation/build/include/vmlinux.h',W/'scheduler/include/vmlinux.h')
# Object lookup follows /proc/self/exe rather than a retired absolute directory.
p=W/'scheduler/neutral_lifecycle.c';old=p.read_text();anchor='object = bpf_object__open_file(BPF_OBJECT_PATH, NULL);'
assert old.count(anchor)==1
replacement='''char object_path[PATH_MAX];
\tssize_t object_length = readlink("/proc/self/exe", object_path, sizeof(object_path) - 1);
\tif (object_length <= 0 || object_length >= (ssize_t)sizeof(object_path) - 1) return 1;
\tobject_path[object_length] = 0;
\tchar *object_slash = strrchr(object_path, '/');
\tif (!object_slash || (size_t)(object_slash - object_path) + sizeof("/full_object.bpf.o") > sizeof(object_path)) return 1;
\tstrcpy(object_slash, "/full_object.bpf.o");
\tobject = bpf_object__open_file(object_path, NULL);'''
new=old.replace(anchor,replacement);p.write_text(new)
(D/'loader-path.patch').write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/neutral_lifecycle.c',tofile='b/neutral_lifecycle.c')))
# Keep existing identity-bound cleanup and selected-child Session implementation.
text=(R/'new_a/session.py').read_text().replace("sys.path.insert(0, str(HERE.parent / 'bench'))",'sys.path.insert(0, str(HERE))').replace("CHILD = HERE.parent / 'build/bin/llama_scx_child'","CHILD = HERE.parent / 'scheduler/llama_scx_child'")
(W/'tools/session.py').write_text(text)
common=(R/'bench/common.py').read_text();tree=ast.parse(common)
wanted={'require','identity','same_process','signal_exact','state','write_json'}
parts=['# SPDX-License-Identifier: GPL-2.0\n# Existing process identity and cleanup helpers; extracted without policy changes.\nimport os,re,signal,json\nfrom pathlib import Path\n']
parts.extend(ast.get_source_segment(common,n)+'\n' for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in wanted)
(W/'tools/common.py').write_text('\n'.join(parts))
# Separate runtime/scheduler configuration, portable package-relative paths.
cases=json.loads((S/'selection-freeze.json').read_text())['cases'];settings={}
for arm,c in cases.items():
 name='NEW_A' if arm in ['C','C-off'] else arm
 argv=c['server_argv'][1:];argv[argv.index('-m')+1]='@MODEL@'
 env=dict(c['server_env']);env['LD_LIBRARY_PATH']='@ROOT@/runtime/'+name
 settings[arm]={'runtime':name,'scheduler':'observe' if arm in ['C','C-off'] else 'linux','argv':argv,'env':env,'cpus':b1['study_config']['cpus']}
(W/'config/arms.json').write_text(json.dumps(settings,indent=2)+'\n')
for src,name in [(S/'result-summary.md','performance-result.md'),(S/'result-summary.json','performance-result.json'),(S/'protocol.json','historical-protocol.json'),(S/'review/output-quality-scope.md','output-quality-scope.md'),(W/'new-a-performance/output-divergence-diagnosis-v1/next-step.md','NEXT_STEP.md'),(W/'new-a-performance/output-divergence-diagnosis-v1/GOAL_STATE.md','diagnosis-state.md')]:
 if src.is_file():copy(src,W/'evidence'/name)
(D/'source-provenance.json').write_text(json.dumps(provenance,indent=2)+'\n');(D/'runtime-preservation.json').write_text(json.dumps(runtime_proof,indent=2)+'\n')
print(json.dumps({'source':str(target),'runtime_files':len(runtime_proof),'runtime_unique_files':len(seen),'component_files':len(provenance)}))
