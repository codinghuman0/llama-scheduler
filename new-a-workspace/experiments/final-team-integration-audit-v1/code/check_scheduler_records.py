"""Inspect saved attachment records only; never run the recorded sudo/bpftool argv."""
import hashlib,json
from pathlib import Path
D=Path(__file__).resolve().parents[1];W=D.parents[1]
def read(p):return json.loads(p.read_text())
inputs={};records=[]
def record(p):
 inputs[str(p)]=dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size);return read(p)
for v in read(D/'observed-usage.json')['scheduler_visits']:
 folder=W/v['path']/'server'
 def raw(name):
  a=record(folder/name);assert a['returncode']==0;return json.loads(a['stdout'])
 progs=[p for p in raw('bpf-prog.json') if p.get('name','').startswith('llama_')]
 phase=[p for p in progs if p['name']=='llama_phase'];assert len(phase)==1
 links=raw('bpf-link.json');perf=raw('bpf-perf.json');assert any(l['type']=='struct_ops' for l in links)
 assert any(l.get('prog_id')==phase[0]['id'] and l['type']=='perf_event' for l in links)
 proc=record(folder/'scheduler-processes.json');loader=proc['loader']
 # Existing process records use pid; do not query or attach to a live process.
 attach=[x for x in perf if x.get('prog_id')==phase[0]['id']];assert len(attach)==1 and attach[0]['fd_type']=='uprobe' and attach[0]['pid']==loader['pid']
 assert attach[0]['offset']==int('185b40',16)
 states=[record(folder/n) for n in ['sched-ext-active.json','sched-ext-after-http.json']]
 for s in states:assert s['/sys/kernel/sched_ext/state']=='enabled' and s['/sys/kernel/sched_ext/root/ops']=='llama_new_a' and s['/sys/kernel/sched_ext/switch_all']=='0'
 assert states[0]['/sys/kernel/sched_ext/enable_seq']==states[1]['/sys/kernel/sched_ext/enable_seq']
 watchdog=record(folder/'watchdog.json');assert watchdog and all(x['status']=='PASS' for x in watchdog)
 cleanup=record(folder/'cleanup.json');assert cleanup['status']=='PASS' and not cleanup['errors'] and cleanup['sched_ext']=='disabled'
 command=record(folder/'loader-command.json');marker=command[command.index('--marker-elf')+1]
 assert hashlib.sha256(Path(marker).read_bytes()).hexdigest()=='9204b0d4e45d4b5437c61417afe912d55618ce62ece6b6adf83ca7967dbe8cfc'
 fd=record(folder/'loader-fds.json')
 records.append(dict(campaign=v['campaign'],stage=v['stage'],condition=v['condition'],raw=str(folder.relative_to(W)),programs=[{k:p[k] for k in ['id','name','type','tag']} for p in progs],phase_attachment=attach,links=[x for x in links if x.get('prog_id')==phase[0]['id'] or x['type']=='struct_ops'],marker_elf=marker,marker_file_offset_hex='0x185b40',marker_sha256='9204b0d4e45d4b5437c61417afe912d55618ce62ece6b6adf83ca7967dbe8cfc',enable_seq_unchanged=True,watchdog_pass_samples=len(watchdog),cleanup=cleanup,loader_fd_record_sha256=inputs[str(folder/'loader-fds.json')]['sha256']))
tags={}
for r in records:
 for p in r['programs']:tags.setdefault(p['name'],set()).add(p['tag'])
out=dict(status='PASS',recorded_visits=len(records),new_privileged_commands=0,scope='Preserved bpftool/perf/link/proc/sysfs/watchdog records; no live BPF interaction. Sampled no-detach evidence, not uninterrupted tracing.',unique_tags_by_program={k:sorted(v) for k,v in tags.items()},records=records)
(D/'evidence/scheduler-attachments.json').write_text(json.dumps(out,indent=2)+'\n')
(D/'evidence/scheduler-attachment-inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
print(json.dumps(dict(status='PASS',visits=len(records),tags=out['unique_tags_by_program'])))
