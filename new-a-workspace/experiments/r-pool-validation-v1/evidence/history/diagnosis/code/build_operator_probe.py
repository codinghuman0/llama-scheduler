from pathlib import Path
import json,subprocess,hashlib,shlex,fcntl,os
D=Path(__file__).resolve().parents[1];W=Path('/home/codinghuman/projects');Q=W/'new-a-lab/llama-phase-batch-q4-exact-v1'
assert os.getuid()!=0
with (W/'new-a-runs/.measurement.lock').open('r') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 flags=dict(line.split(' = ',1) for line in (D/'evidence/cpu-flags-B1.make').read_text().splitlines() if ' = ' in line)
 command=['c++',*shlex.split(flags['CXX_DEFINES']),*shlex.split(flags['CXX_INCLUDES']),*shlex.split(flags['CXX_FLAGS']),'-shared',str(D/'diagnostic/operator_probe.cpp'),'-ldl','-o',str(D/'diagnostic/operator-probe.so')]
 with (D/'diagnostic/operator-compile.log').open('w') as f:subprocess.run(command,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=120)
 identity={'command':command,'scope':'minimal diagnostic overlay, existing Q4 functions unchanged; no timing benchmark','hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [D/'diagnostic/operator-probe.so',D/'diagnostic/operator_probe.cpp',Q/'ggml/src/ggml-cpu/newa-q4-tile32.h',Q/'ggml/src/ggml-cpu/repack.h']}}
 (D/'diagnostic/operator-build.json').write_text(json.dumps(identity,indent=2)+'\n')
 print(json.dumps(identity))
