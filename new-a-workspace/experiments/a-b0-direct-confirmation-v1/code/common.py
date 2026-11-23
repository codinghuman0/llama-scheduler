"""Shared records, immutable input checks and read-only host admission."""
from pathlib import Path
import datetime,hashlib,json,os,re,shutil,subprocess,time
D=Path(__file__).resolve().parents[1]; W=D.parents[1]; O=D.parent/'r-pool-validation-v1'
CPUS=[0,2,4,6,8,10]
def read(p): return json.loads(Path(p).read_text())
def save(p,v): Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''): h.update(b)
 return h.hexdigest()
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def event(stage,**kw):
 with (D/'ledger.jsonl').open('a') as f: f.write(json.dumps(dict(**dict(kw,time=now()),stage=stage))+'\n')
def text(p):
 try:return Path(p).read_text().strip()
 except OSError:return None
def temps():
 out={}
 for d in Path('/sys/class/hwmon').glob('hwmon*'):
  for p in d.glob('temp*_input'):
   try:out[str(text(d/'name'))+':'+p.name]=int(p.read_text())/1000
   except OSError:pass
 return out
def topology():
 return {str(i):{n:text(f'/sys/devices/system/cpu/cpu{i}/topology/{n}') for n in ['physical_package_id','core_id','thread_siblings_list']} for i in range(12)}
def environment():
 return dict(time=now(),monotonic_ns=time.monotonic_ns(),uid=os.getuid(),kernel=os.uname().release,machine=os.uname().machine,online=text('/sys/devices/system/cpu/online'),sched_ext=text('/sys/kernel/sched_ext/state'),temperature_c=temps(),frequency_khz={str(i):text(f'/sys/devices/system/cpu/cpu{i}/cpufreq/scaling_cur_freq') for i in range(12)},governors={str(i):text(f'/sys/devices/system/cpu/cpu{i}/cpufreq/scaling_governor') for i in range(12)},cpufreq_drivers={str(i):text(f'/sys/devices/system/cpu/cpu{i}/cpufreq/scaling_driver') for i in range(12)},boost=text('/sys/devices/system/cpu/cpufreq/boost'),smt=text('/sys/devices/system/cpu/smt/active'),power={str(p):text(p) for d in Path('/sys/class/power_supply').glob('*') for p in [d/'type',d/'online',d/'status'] if p.exists()},mem_available_kib=int(re.search(r'MemAvailable:\s+(\d+)',Path('/proc/meminfo').read_text())[1]),disk_free_bytes=shutil.disk_usage(W).free,loadavg=text('/proc/loadavg'))
STABLE=['uid','kernel','machine','online','sched_ext','governors','cpufreq_drivers','boost','smt','power']
def guard(snapshot=None):
 v=snapshot or environment()
 assert v['uid']!=0 and v['sched_ext']=='disabled','User or sched_ext admission'
 assert v['disk_free_bytes']>=1024**3 and v['mem_available_kib']>=3000000,'Resource admission'
 assert v['temperature_c'].get('k10temp:temp1_input',100)<85,'Thermal admission'
 if (D/'evidence/host-before.json').exists():
  prior=read(D/'evidence/host-before.json')['environment']
  for k in STABLE:
   actual,expected=v[k],prior[k]
   if k=='power':
    actual={p:x for p,x in actual.items() if not p.endswith('/status')}
    expected={p:x for p,x in expected.items() if not p.endswith('/status')}
   assert actual==expected,('Environment changed',k,actual,expected)
 return v
def no_model_process():
 for p in Path('/proc').glob('[0-9]*'):
  if text(p/'comm') in ['llama-server','llama-bench']:raise RuntimeError('Other model process: '+p.name)
def verify_inputs():
 seal=read(D/'seal.json')
 for rel,digest in seal['files'].items():assert sha(D/rel)==digest,('Frozen input changed',rel)
 for case in read(D/'cases.json').values():
  for p,digest in {**case['artifacts'],**case['system_libraries']}.items():assert sha(p)==digest,('Runtime/library changed',p)
 assert sha(W/'models/model.gguf')==read(D/'protocol.json')['model_sha256']
 assert topology()==read(D/'evidence/host-before.json')['topology']
 assert set(CPUS+[11])<=os.sched_getaffinity(0) or os.sched_getaffinity(0)=={11}
 return seal

def verify_loaded(case,loaded):
 expected={**case['artifacts'],**case['system_libraries']}
 def key(p,h):
  st=Path(p).stat();return st.st_dev,st.st_ino,h
 actual_keys={key(p,h) for p,h in loaded.items()}
 expected_keys={key(p,h) for p,h in expected.items()}
 assert actual_keys==expected_keys,('Loaded ELF inode/hash set differs',actual_keys^expected_keys)
 return {p:[q for q,d in expected.items() if key(p,h)==key(q,d)] for p,h in loaded.items()}
