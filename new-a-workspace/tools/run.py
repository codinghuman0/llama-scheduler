#!/usr/bin/env python3
"""Launch the retained CPU runtime with bounded, selected-child cleanup."""
from pathlib import Path
import argparse,datetime,fcntl,hashlib,json,os,signal,socket,struct,subprocess,sys,time
from session import Session,active_experiments,check_privileges
ROOT=Path(__file__).resolve().parents[1]

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--runtime',choices=['NEW_A','B1','B0'],default='NEW_A')
 p.add_argument('--scheduler',choices=['linux','observe'],default='linux')
 p.add_argument('--policy',choices=['phase','fixed6'],default='phase')
 p.add_argument('--model',type=Path,default=ROOT/'models/model.gguf')
 p.add_argument('--port',type=int,default=51337)
 p.add_argument('--cpus',help='Six distinct physical cores as comma-separated logical CPU IDs; default retains measured mask.')
 p.add_argument('--timeout',type=int,default=600)
 p.add_argument('--describe',action='store_true',help='Print configuration without launching anything.')
 a=p.parse_args();assert os.getuid()!=0,'Run as ordinary user'
 assert 1<=a.port<=65535 and 1<=a.timeout<=86400
 assert a.scheduler=='linux' or a.runtime=='NEW_A','Guarded scheduler entry supports the selected NEW_A runtime only'
 arm=('C-off' if a.policy=='fixed6' else 'C') if a.runtime=='NEW_A' else a.runtime
 c=json.loads((ROOT/'config/arms.json').read_text())[arm]
 cpus=sorted(map(int,a.cpus.split(','))) if a.cpus else c['cpus'];assert len(cpus)==len(set(cpus))==6
 assert set(cpus)<=os.sched_getaffinity(0),'CPU mask unavailable on this machine'
 groups=[]
 for cpu in cpus:
  t=Path(f'/sys/devices/system/cpu/cpu{cpu}/topology')
  groups.append(((t/'physical_package_id').read_text(),(t/'core_id').read_text()))
 assert len(set(groups))==6,'Use one logical CPU per physical core'
 house=sorted(os.sched_getaffinity(0)-set(cpus));assert house
 model=a.model.expanduser().resolve()
 args=[str(ROOT/'runtime'/a.runtime/'llama-server'),*[str(model) if x=='@MODEL@' else x for x in c['argv']]]
 args[args.index('--port')+1]=str(a.port)
 env={k:v.replace('@ROOT@',str(ROOT)) for k,v in c['env'].items()}
 # Preserve explicitly selected environment; omit unrelated external affinity overrides.
 config={'runtime':a.runtime,'scheduler':a.scheduler,'resource_policy':env.get('NEWA_DECODE_RESOURCE'),'argv':args,'env':env,'cpus':cpus,'housekeeping':house,'timeout_s':a.timeout}
 if a.describe:print(json.dumps(config,indent=2));return
 assert model.is_file(),'Model missing; pass --model'
 assert Path('/sys/kernel/sched_ext/state').read_text().strip()=='disabled'
 assert not active_experiments(),'Another experiment is active'
 state=ROOT/'state';state.mkdir(exist_ok=True)
 with (state/'.measurement.lock').open('rb') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  with socket.socket() as sock:sock.bind(('127.0.0.1',a.port))
  if a.scheduler=='observe':
   check_privileges()
   ident=json.loads((ROOT/'config/scheduler.json').read_text())
   assert os.uname().release==ident['kernel'],'Kernel changed; revalidate BPF before loading'
   assert hashlib.sha256(Path('/sys/kernel/btf/vmlinux').read_bytes()).hexdigest()==ident['btf_sha256'],'BTF changed'
   for name,digest in ident['files'].items():assert hashlib.sha256((ROOT/'scheduler'/name).read_bytes()).hexdigest()==digest,name
  folder=state/(datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+str(os.getpid()));folder.mkdir()
  (folder/'configuration.json').write_text(json.dumps(config,indent=2)+'\n')
  topology=folder/'topology.bin'
  topology.write_bytes(struct.pack('<'+'I'*(5+3*1024),0x4e455741,1,len(cpus),0,0,*cpus,*([0]*(3*1024-len(cpus)))))
  stop=False
  def stopping(*_):
   nonlocal stop
   stop=True
  previous={s:signal.signal(s,stopping) for s in [signal.SIGINT,signal.SIGTERM]}
  os.chdir(ROOT)
  session=Session(folder,args,cpus,house,policy='C' if a.scheduler=='linux' else 'E',topology=topology,env=env,diagnostics=a.scheduler=='observe',marker=ROOT/'runtime'/a.runtime/'libllama-server-impl.so',loader_binary=ROOT/'scheduler/loader',child_binary=ROOT/'scheduler/llama_scx_child')
  try:
   with session:
    print(f'Serving http://127.0.0.1:{a.port}; logs: {folder}',flush=True)
    deadline=time.monotonic()+a.timeout
    while not stop and time.monotonic()<deadline:
     if session.process.poll() is not None:
      session.natural=True;break
     if session.loader:assert session.loader.poll() is None and Path('/sys/kernel/sched_ext/state').read_text().strip()=='enabled','Unexpected scheduler detach'
     for task in Path(f"/proc/{session.server['pid']}/task").iterdir():
      try:
       assert os.sched_getscheduler(int(task.name))==(7 if session.loader else 0)
       assert os.sched_getaffinity(int(task.name))==set(cpus),'Worker affinity changed'
      except ProcessLookupError:pass
     time.sleep(0.5)
  finally:
   for s,handler in previous.items():signal.signal(s,handler)
if __name__=='__main__':main()
