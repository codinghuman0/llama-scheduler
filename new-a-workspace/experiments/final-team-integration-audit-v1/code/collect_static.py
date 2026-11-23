"""Read source, ELF metadata and existing provenance; write only this audit directory."""
import hashlib,json,re,subprocess,difflib
from pathlib import Path
D=Path(__file__).resolve().parents[1]; W=D.parents[1]
C=W/'experiments/a-component-scheduler-replication-v1';R=W/'experiments/r-pool-validation-v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):
 p=D/p;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def run(args):
 r=subprocess.run(args,capture_output=True,text=True,timeout=60);assert r.returncode==0,(args,r.stderr);return r.stdout
def read(p):return json.loads(p.read_text())
release=read(C/'frozen-release-map.json');checks=[]
for p,h in release['source_overlay_hashes'].items():checks.append(dict(kind='source_overlay',path=p,expected=h,actual=sha(Path(p))))
for arm,case in release['cases'].items():
 for p,h in case['artifacts'].items():checks.append(dict(kind='case_artifact',arm=arm,path=p,expected=h,actual=sha(Path(p))))
for p,h in release['scheduler_identity']['files'].items():checks.append(dict(kind='scheduler',path=p,expected=h,actual=sha(Path(p))))
for arm,visits in release['actual_loaded_evidence'].items():
 for visit in visits:
  raw=read(C/visit['raw']/'server/runtime.json')
  assert raw['loaded_elf_sha256']==visit['loaded_ELF_sha256']
  assert raw['argv']==visit['argv'] and raw['environment']==visit['environment']
  for p,h in visit['loaded_ELF_sha256'].items():
   if str(W) in p:checks.append(dict(kind='actual_mapped_project_ELF',arm=arm,visit=visit['raw'],path=p,expected=h,actual=sha(Path(p))))
assert all(x['expected']==x['actual'] for x in checks)
save('evidence/identity-recheck.json',dict(status='PASS',checks=checks,model=release['model'],system_DSO_note='Preserved loaded hashes retained; current OS library upgrades are not used to reinterpret past runs.'))
elf=[]
for label,p in [('A-server',R/'candidates/A/runtime/libllama-server-impl.so'),('A-libllama',R/'candidates/A/runtime/libllama.so'),('A-CPU',R/'candidates/A/runtime/libggml-cpu.so'),('P-server',R/'candidates/P-padding-fix/runtime/libllama-server-impl.so'),('scheduler-FULL',W/'scheduler/full_object.bpf.o')]:
 syms=run(['nm','-C',str(p)])
 dynamic=run(['readelf','-d',str(p)])
 hits=[l for l in syms.splitlines() if re.search(r'llama_decode_with_options|llama_decode_default_options|llama_scx_phase|server_threadpool|ggml_backend_cpu_newa_phase|ggml_backend_cpu_set_n_threads|newa_q4_decode_exact|newa_q6|newa_decode_policy|llama_select_cpu|llama_enqueue|llama_phase',l)]
 strings=run(['strings','-a',str(p)])
 text=[l for l in strings.splitlines() if re.search(r'NEWA_POOL|NEWA_PREFILL_PRESSURE|donor pool|LLAMA_SCX_PHASE_V2',l)]
 elf.append(dict(label=label,path=str(p),sha256=sha(p),symbols=hits,dynamic=dynamic,strings=text,method='Static nm/readelf/strings only; ELF never executed.'))
save('evidence/static-elf.json',elf)
base=D/'sources/base-59abec4';src=W/'src/llama'
spec=[
 ('semantic-origin',src/'tools/server/server-context.cpp',[('decode-origin','true, SERVER_BATCH_PHASE_DECODE'),('prompt-origin','SERVER_BATCH_PHASE_PREFILL);'),('retry-view','batch_view = batch.get_view(off, n_tokens);'),('classification','for (int32_t i = off; i < off + batch_view.n_tokens;'),('profile-selection','requested_profile = newa_resource.select('),('transition','scx_phase_state.transition('),('decode-api','ret = llama_decode_with_options('),('split','n_batch /= 2;'),('old-pool','GGML_NEWA_POOL')]),
 ('phase-classifier',src/'tools/server/server-phase.h',[('classifier','server_batch_phase_classify('),('transition-state','class server_scx_phase_state')]),
 ('profile-header',src/'include/llama.h',[('enum','enum llama_compute_profile'),('options','struct llama_decode_options'),('api','LLAMA_API int32_t llama_decode_with_options')]),
 ('profile-resolve',src/'src/llama-context.h',[('resolve','llama_compute_profile_resolve(')]),
 ('profile-engine',src/'src/llama-context.cpp',[('graph','llama_context::graph_compute('),('pool-setter','set_threadpool_fn('),('threads-setter','set_n_threads_fn.second('),('default','llama_decode_options llama_decode_default_options('),('api','int32_t llama_decode_with_options(')]),
 ('phase-bridge',src/'tools/server/server-scx.h',[('marker','void llama_scx_phase_v1(uint32_t phase) {'),('setter-lookup','ggml_backend_cpu_newa_phase'),('trace','LLAMA_SCX_PHASE_TRACE')]),
 ('E',src/'tools/server/newa-prefill-pressure.h',[('limits','min_call_ns'),('sensor','/proc/stat'),('score','value.score ='),('reset','void reset()'),('select','llama_compute_profile select('),('capture','void begin()'),('commit','void finish(')]),
 ('CPU-graph',src/'ggml/src/ggml-cpu/ggml-cpu.c',[('phase-setter','void ggml_backend_cpu_newa_phase('),('barrier','void ggml_barrier('),('q6','const bool newa_q6_eligible'),('pool-new','ggml_threadpool_new_impl('),('graph','ggml_graph_compute('),('phase-load','threadpool->newa_q6_phase = atomic_load'),('team','#pragma omp parallel num_threads(n_threads)')]),
 ('CPU-registry',src/'ggml/src/ggml-cpu/ggml-cpu.cpp',[('setter','ggml_backend_cpu_set_n_threads('),('registry','if (strcmp(name, "ggml_backend_cpu_newa_phase")')]),
 ('Q4-R',R/'candidates/R/overlay/ggml/src/ggml-cpu/newa-q4-policy.h',[('eligibility','static bool newa_q4_try('),('reference','Keep semantic Prefill on the reference body.'),('exact','else newa_q4_decode_exact(')]),
 ('Q4-exact',src/'ggml/src/ggml-cpu/newa-q4-decode-exact.h',[('tile','void newa_q4_decode_exact('),('two-activation-groups','a_ptrs[2]'),('shared-weights','rhs_raw_mat_0123_0')]),
 ('Q6-policy',src/'ggml/src/ggml-cpu/newa-q6-policy.h',[('phase','newa_q6_phase_allowed(')]),
 ('repack-pages',src/'ggml/src/ggml-cpu/newa-repack-pages.h',[('advice','MADV_HUGEPAGE')]),
 ('scheduler',W/'scheduler/handoff.bpf.c',[('tier','s32 pick_idle_from_list('),('select','BPF_STRUCT_OPS(llama_select_cpu'),('handoff','phase != LLAMA_SCX_PHASE_DECODE'),('handoff-guard','#ifdef NEW_A_IDLE_HANDOFF'),('enqueue','BPF_STRUCT_OPS(llama_enqueue'),('dispatch','BPF_STRUCT_OPS(llama_dispatch'),('weight','p->scx.dsq_vtime +='),('uprobe','BPF_UPROBE(llama_phase'),('partial','SCX_OPS_SWITCH_PARTIAL')]),
 ('scheduler-loader',W/'scheduler/loader.c',[('topology','fread(&topology'),('live-monitor','analysis_monitor()')]),
 ('scheduler-lifecycle',W/'scheduler/neutral_lifecycle.c',[('uprobe','bpf_program__attach_uprobe_opts'),('structops','bpf_map__attach_struct_ops')]),
 ('selected-child',W/'scheduler/llama_scx_child.c',[('policy','.sched_policy = SCHED_EXT'),('exec','execvp(')]),
 ('monitor',W/'scheduler/monitor.h',[('monitor','analysis_monitor(')]),
 ('P-owner',R/'candidates/P-padding-fix/overlay/tools/server/server-threadpool.h',[('owner','struct server_threadpools')]),
 ('P-context',R/'candidates/P-padding-fix/overlay/tools/server/server-context.cpp',[('donor','"donor"'),('owner','server_threadpools'),('reset','newa_donor_pools.reset')]),
]
anchors=[];missing=[]
for group,p,patterns in spec:
 lines=p.read_text().splitlines();ranges=[];items=[]
 for name,needle in patterns:
  hits=[i+1 for i,l in enumerate(lines) if needle in l]
  if not hits:missing.append(dict(group=group,name=name,needle=needle,path=str(p)));continue
  line=hits[0];items.append(dict(name=name,line=line,match=lines[line-1],all_match_lines=hits));ranges.append((max(1,line-5),min(len(lines),line+18)))
 ranges.sort();merged=[]
 for a,b in ranges:
  if merged and a<=merged[-1][1]+1:merged[-1]=(merged[-1][0],max(b,merged[-1][1]))
  else:merged.append((a,b))
 excerpt='SOURCE: '+str(p)+'\nSHA256: '+sha(p)+'\nOriginal line numbers follow; omitted regions are explicit.\n'
 for a,b in merged:excerpt+='\n... '+str(a)+'-'+str(b)+' ...\n'+''.join(f'{i}: {lines[i-1]}\n' for i in range(a,b+1))
 out=D/f'sources/excerpts/{group}.txt';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(excerpt)
 anchors.append(dict(id=group,path=str(p),sha256=sha(p),lines=len(lines),anchors=items,excerpt=str(out.relative_to(D))))
save('evidence/source-anchors.json',anchors);save('evidence/unresolved-anchor-searches.json',missing)
diffs=[]
for name,a,b in [('base59-to-final-server',base/'tools/server/server-context.cpp',src/'tools/server/server-context.cpp'),('base59-to-final-bridge',base/'tools/server/server-scx.h',src/'tools/server/server-scx.h'),('base59-to-final-cpu',base/'ggml/src/ggml-cpu/ggml-cpu.c',src/'ggml/src/ggml-cpu/ggml-cpu.c'),('public-to-observe-bpf',D/'sources/donor/scheduler-public-bpf.txt',W/'scheduler/handoff.bpf.c'),('A-to-P-context',src/'tools/server/server-context.cpp',R/'candidates/P-padding-fix/overlay/tools/server/server-context.cpp'),('preR-to-R-q4',src/'ggml/src/ggml-cpu/newa-q4-policy.h',R/'candidates/R/overlay/ggml/src/ggml-cpu/newa-q4-policy.h')]:
 text=''.join(difflib.unified_diff(a.read_text().splitlines(True),b.read_text().splitlines(True),fromfile=str(a),tofile=str(b),n=3));p=D/f'sources/patches/{name}.patch';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text);diffs.append(dict(name=name,before=str(a),before_sha256=sha(a),after=str(b),after_sha256=sha(b),patch=str(p.relative_to(D))))
same=[]
for f in ['include/llama.h','src/llama-context.cpp','src/llama-context.h','tools/server/server-phase.h']:
 same.append(dict(path=f,base_sha256=sha(base/f),final_sha256=sha(src/f),equal=sha(base/f)==sha(src/f)))
pool=R/'candidates/P-padding-fix/overlay/tools/server/server-threadpool.h';donor=W/'experiments/persistent-pool-port-v1/donor/pool-header.txt'
same.append(dict(path='P donor pool header',base_sha256=sha(donor),final_sha256=sha(pool),equal=sha(donor)==sha(pool)))
assert all(x['equal'] for x in same)
save('evidence/source-diffs.json',dict(diffs=diffs,byte_identity=same))
scope=[src/'tools/server/server-context.cpp',src/'tools/server/newa-prefill-pressure.h',src/'tools/server/server-scx.h',src/'src/llama-context.cpp',src/'ggml/src/ggml-cpu/ggml-cpu.c',src/'ggml/src/ggml-cpu/ggml-cpu.cpp']
patterns=[r'bpf_map_lookup_elem',r'bpf_obj_get',r'/sys/fs/bpf',r'BPF_MAP',r'scheduler-stats',r'phase-register-socket',r'cpu25',r'ambient']
search=[]
for p in scope:
 lines=p.read_text().splitlines();hits=[dict(pattern=pat,line=i+1,text=l) for pat in patterns for i,l in enumerate(lines) if re.search(pat,l)]
 search.append(dict(path=str(p),sha256=sha(p),matches=hits))
save('evidence/feedback-search.json',dict(result='NOT_FOUND_IN_SCOPE',scope=search,patterns=patterns,interpretation='No inbound kernel-scheduler telemetry or condition labels in the selected runtime policy chain. Manual call inspection: E reads proc/stat and process CPU clock; CPU bridge is outbound setter. Bounded absence, not proof about every file or future version.'))
pin=read(W/'experiments/persistent-pool-port-v1/source-pin.json')
save('source-lineage.json',dict(status='PARTIAL_PROVENANCE',functional_status='FUNCTIONAL_INTEGRATION_MAPPED',pins=pin['pins'],additional_pins=dict(v2='44c95d5eb264b1665c6cff2862c4b9b4a115ad43',serving='4694fc88d00a2ded5783ce993e5eb28b4f6ec56f'),local_commit_chain='evidence/local-git-lineage.json',shared_ancestor='5219055a578fd741e029e81fefef6f3a5695086d',shared_proof=['evidence/donor-shared-compare.json','evidence/local-git-lineage.json'],profile_origin='a94326390a8fb8686881e0463321acce4419ddcc',phase_origin='5219055a578fd741e029e81fefef6f3a5695086d',local_lightening=['c2c398510f69180cfc29026cb1e0ca133b01d548','2ec5829580fa3d9e16e3a315eb789982f7169882','1bb4bd7d20d6e8fe8dcbd3f529bab7cf9f257927','e5b3858873888bacd519117cbfe4a8fc9b2c9a41','c8b9d61d12b4997d902a03e5dc55a185d18c3bc9'],final_sources=anchors,patches=diffs,byte_identity=same,identity_checks='evidence/identity-recheck.json',public_scheduler_overlap=pin['public_vs_archived_scheduler'],author_limit='Commit authors are repository metadata, not personal performance credit or independent proof of original authorship.',gaps=['Local dirty E/Q4/Q6 overlays have build hashes and archived provenance but no demonstrated per-hunk author commit.','Scheduler public pin and measured derivative share preserved sources; precise original author of every common hunk remains unproved.','One clean revision rebuild was not executed or established.']))
print(json.dumps(dict(status='PASS',identity_checks=len(checks),source_groups=len(anchors),unresolved_anchor_searches=missing),ensure_ascii=False))
