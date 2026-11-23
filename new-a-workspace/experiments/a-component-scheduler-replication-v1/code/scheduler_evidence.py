"""Read-only evidence for the existing selected-child scheduler."""
import os,subprocess
from pathlib import Path
from common import *
from session_common import identity

def command(folder,name,args):
 r=subprocess.run(args,capture_output=True,text=True,timeout=15)
 save(folder/(name+'.json'),dict(argv=args,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr))
 assert r.returncode==0,(name,r.stderr)
 return r.stdout

def sysfs():
 values={}
 for p in Path('/sys/kernel/sched_ext').rglob('*'):
  if p.is_file():
   try:values[str(p)]=p.read_text().strip()
   except OSError:pass
 return values

def capture(folder,session):
 snap=sysfs();save(folder/'sched-ext-active.json',snap)
 assert snap['/sys/kernel/sched_ext/state']=='enabled'
 assert snap.get('/sys/kernel/sched_ext/root/ops')=='llama_new_a',('Wrong ops',snap)
 assert snap.get('/sys/kernel/sched_ext/switch_all') in ['0','N','n'],('Global switch',snap)
 parent=identity(session.process.pid);assert parent['uid']==os.getuid() and parent['policy']==0 and parent['affinity']==[11]
 loaders=[]
 for d in Path('/proc').glob('[0-9]*'):
  try:
   args=(d/'cmdline').read_bytes().split(b'\0')
   if args[0]!=str(W/'scheduler/loader').encode():continue
   if session.socket.encode() not in args:continue
   v=identity(int(d.name));assert v['uid']==0 and v['policy']==0 and v['affinity']==[11];loaders.append(v)
  except (OSError,IndexError):continue
 assert len(loaders)==1,('Owned root loader not identified',loaders)
 loader=loaders[0]
 exe=command(folder,'loader-exe',['sudo','-n','readlink',f'/proc/{loader["pid"]}/exe']).strip()
 assert exe==str(W/'scheduler/loader')
 for what in ['prog','map','link','perf']:
  command(folder,'bpf-'+what,['sudo','-n','bpftool','-j',what,'show'])
 command(folder,'loader-fds',['sudo','-n','ls','-l',f'/proc/{loader["pid"]}/fd'])
 save(folder/'scheduler-processes.json',dict(loader=loader,launcher=parent,selected=identity(session.server['pid'])))
 return snap

def audit_stats(folder):
 v=read(folder/'scheduler-stats.json')
 # Recursively collect the existing per-CPU statistics independent of their wrapper name.
 def dictionaries(x):
  if isinstance(x,dict):
   yield x
   for y in x.values():yield from dictionaries(y)
  elif isinstance(x,list):
   for y in x:yield from dictionaries(y)
 rows=[x for x in dictionaries(v) if 'mask_violations' in x and 'tracking_failures' in x]
 assert len(rows)==12 and v['instrumentation_mode']=='FULL','Missing scheduler full per-CPU diagnostics'
 assert v['events_export_error']==0 and not v['events'],'Mask/event export failure'
 for r in rows:
  if r['cpu'] not in CPUS:assert r['running']==r['stopping']==r['runtime_ns']==0,'Outside CPU envelope'
 for row in rows:
  assert row['mask_violations']==row['tracking_failures']==row.get('events_dropped',0)==0
 monitor=v['live_monitor'];assert monitor['status']=='PASS' and monitor['samples']>0 and monitor['failures']==0 and monitor['kernel_opened']
 seen=[sum(bool(r['phase_seen'] & (1 << i)) for r in rows) for i in range(4)]
 assert seen[1]>0 and seen[2]>0,('No prefill/decode marker evidence',seen)
 hand=v['idle_handoff'];assert hand['mode']=='observe'
 def numbers(x):
  if isinstance(x,list):return sum(numbers(y) for y in x)
  if isinstance(x,dict):return sum(numbers(y) for y in x.values())
  return x if isinstance(x,(int,float)) else 0
 assert numbers(hand['moved'])==0,'Observe unexpectedly moved tasks'
 return dict(status='PASS',phase_seen=seen,phase_changes_placement=False,monitor=monitor,guard='fixed affinity only; dynamic-affinity failure remains unresolved',handoff=hand)
