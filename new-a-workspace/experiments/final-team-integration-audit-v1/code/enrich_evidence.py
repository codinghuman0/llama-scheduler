"""Create compact, model-free audit inputs from preserved records."""
import collections,difflib,hashlib,json,statistics,subprocess
from pathlib import Path
D=Path(__file__).resolve().parents[1];W=D.parents[1];X=W/'experiments'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):
 p=D/p;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
inputs={}
def record(p):inputs[str(p)]=dict(sha256=sha(p),bytes=p.stat().st_size);return p
# Git show only: historical B0, not the live checkout's HEAD.
b0='7a2db1a0cf38e5f4eb278a58c3903d295258d0ea';blobmap={}
for f in ['include/llama.h','src/llama-context.cpp','src/llama-context.h','ggml/src/ggml-cpu/ggml-cpu.c','tools/server/server-context.cpp','tools/server/CMakeLists.txt']:
 r=subprocess.run(['git','-C','/home/codinghuman/projects/llama.cpp','show',b0+':'+f],capture_output=True,check=True)
 p=D/'sources/historical-B0'/f;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(r.stdout)
for p in (D/'sources').rglob('*'):
 if p.is_file():
  b=p.read_bytes();blobmap[hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()]=p
patches=[]
for x in read(D/'evidence/local-git-lineage.json')['changes']:
 before=blobmap.get(x['parent_blob']);after=blobmap[x['blob']]
 if x['parent_blob'] and before is None:patches.append(dict(**x,patch=None,reason='Parent blob not in bounded excerpt set'));continue
 text=''.join(difflib.unified_diff(before.read_text().splitlines(True) if before else [],after.read_text().splitlines(True),fromfile=x['parent']+'/'+x['path'] if before else '/dev/null',tofile=x['commit']+'/'+x['path'],n=3))
 p=D/'sources/commit-patches'/(x['commit'][:12]+'-'+x['path'].replace('/','_')+'.patch');p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
 patches.append(dict(**x,patch=str(p.relative_to(D)),before_sha256=sha(before) if before else None,after_sha256=sha(after)))
save('evidence/commit-hunks.json',patches)
blocks=[];absolute=[];counts=[]
for label,folder,name,run in [('original','a-component-scheduler-attribution-v1','component-summary.json','attribution-v1'),('replication','a-component-scheduler-replication-v1','replication-summary.json','replication-v1')]:
 root=X/folder;a=read(record(root/name));state=read(record(root/'results'/run/'campaigns.json'));lookup={(x['condition'],x['block'],x['arm']):root/x['path'] for x in state['completed']}
 for cell in a['cells']:
  for block in cell['blocks']:
   raw={}
   for arm in ['B0_L','F6_L','A_L','A_S']:
    path=lookup[(cell['condition'],block['block'],arm)];rows=read(record(path/'http-observations.json'));o=next(x for x in rows if x['role']=='measured');tps=1024/((o['end_ns']-o['start_ns'])/1e9)
    assert abs(tps-block['arms'][arm]['tokens_per_second'])<1e-10
    raw[arm]=dict(tokens=1024,start_ns=o['start_ns'],end_ns=o['end_ns'],tps=tps,source=str((path/'http-observations.json').relative_to(W)),source_sha256=sha(path/'http-observations.json'))
   blocks.append(dict(campaign=label,condition=cell['condition'],block=block['block'],cohort=block['cohort'],arms=raw))
  for arm in ['B0_L','F6_L','A_L','A_S']:
   values=[b['arms'][arm] for b in blocks if b['campaign']==label and b['condition']==cell['condition']]
   absolute.append(dict(campaign=label,condition=cell['condition'],arm=arm,n=len(values),mean_tps=statistics.mean(v['tps'] for v in values),cohort_wall_mean_s=statistics.mean((v['end_ns']-v['start_ns'])/1e9 for v in values)))
 counts.append(dict(campaign=label,counts=a['counts'],actual_cpu25_cores_range=a['actual_cpu25_cores_range'],protocol=str((root/'protocol.json').relative_to(W)),protocol_sha256=sha(record(root/'protocol.json'))))
save('evidence/performance-blocks.json',dict(blocks=blocks,absolute=absolute,campaign_counts=counts,token_count_proof='Each 1024 was independently checked against actual token arrays by collect_usage.py invoking the preserved read-only recalculate.py; 8 requests are not 8 independent paired blocks.'))
usage=read(D/'observed-usage.json');sched=[]
for key in sorted({(x['campaign'],x['stage'],x['condition']) for x in usage['scheduler_visits']}):
 rows=[x for x in usage['scheduler_visits'] if (x['campaign'],x['stage'],x['condition'])==key]
 sched.append(dict(campaign=key[0],stage=key[1],condition=key[2],visits=len(rows),select_tiers=[sum(x['selected_tier_counts'][i] for x in rows) for i in range(4)],handoff_attempts=[sum(x['handoff']['attempts'][i] for x in rows) for i in range(4)],handoff_moved=[sum(x['handoff']['moved'][i] for x in rows) for i in range(4)],phase_presence_bitmaps=sorted({x['phase_seen_bits'] for x in rows}),scope='WHOLE_VISIT counters; timed visit grouping does not make counters measured-window-only'))
save('evidence/scheduler-aggregate.json',sched)
# Save only small named provenance records, never runtimes, old packages or trees.
copy=[
 'a-component-scheduler-replication-v1/cases.json','a-component-scheduler-replication-v1/protocol.json','a-component-scheduler-replication-v1/frozen-release-map.json','a-component-scheduler-replication-v1/scheduler-identity.json','a-component-scheduler-replication-v1/inputs/compile.log',
 'r-pool-validation-v1/identity-map.json','r-pool-validation-v1/evidence/R-checkpoint.json','r-pool-validation-v1/evidence/R-numeric-summary.json','r-pool-validation-v1/evidence/AP-functional-checkpoint.json','r-pool-validation-v1/evidence/AP-lifecycle-summary.json','r-pool-validation-v1/evidence/history/server-build/pressure/identity.json','r-pool-validation-v1/build-cpu/commands.json','r-pool-validation-v1/evidence/cpu-compilation-inputs.json','r-pool-validation-v1/evidence/cpu-header-inputs.json','r-pool-validation-v1/build-server/parent-relink.json','r-pool-validation-v1/candidates/P-padding-fix/validation.json','r-pool-validation-v1/patches/R-prefill-reference.patch','r-pool-validation-v1/patches/P-padding-compatibility.patch','persistent-pool-port-v1/source-pin.json','persistent-pool-port-v1/method.patch']
copied=[]
for f in copy:
 p=X/f
 if not p.exists():copied.append(dict(path=f,status='NOT_FOUND'));continue
 assert p.stat().st_size<2_000_000
 out=D/'evidence/preserved'/f;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(record(p).read_bytes());copied.append(dict(source=str(p),output=str(out.relative_to(D)),sha256=sha(p)))
save('evidence/preserved-records.json',copied)
save('evidence/additional-inputs.json',inputs)
# Keep the documented default role separate from the untouched command-line entry point.
config=read(record(W/'config/arms.json'));release=read(X/'a-component-scheduler-replication-v1/frozen-release-map.json')
save('evidence/entrypoint-scope.json',dict(role=release['roles'],actual_entry=str(W/'run.sh'),runner=str(W/'tools/run.py'),runner_sha256=sha(record(W/'tools/run.py')),default_runtime='runtime/NEW_A',default_scheduler='linux',default_policy='phase',default_CPU_sha256=sha(W/'runtime/NEW_A/libggml-cpu.so'),A_CPU_sha256=sha(X/'r-pool-validation-v1/candidates/A/runtime/libggml-cpu.so'),config=config,verdict='A_L is the frozen research default role. The workspace entry point still selects pre-R NEW_A; it was not repointed, and is not a shortcut command for final A_L.'))
print(json.dumps(dict(status='PASS',paired_blocks=len(blocks),absolute_cells=len(absolute),commit_patches=sum(x['patch'] is not None for x in patches),unavailable_parent_hunks=[x['path'] for x in patches if x['patch'] is None],missing_records=[x['path'] for x in copied if 'status' in x])))
