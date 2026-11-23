#!/usr/bin/env python3
"""Build separate diagnostic overlays and run bounded correctness replay."""
from pathlib import Path
import argparse,hashlib,json,os,shutil,subprocess
D=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--mode',choices=['single','cohort','quality'],required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
assert os.getuid()!=0
out=a.output.resolve();assert not out.exists() and out!=D
out.mkdir(parents=True);(out/'code').mkdir();(out/'diagnostic').mkdir();(out/'evidence').mkdir();(out/'runs').mkdir()
for name in ['reproduce_frozen.py','run_diagnostic.py','build_diagnostic.py','build_operator_probe.py','compare_traces.py','quality_diagnostic.py']:shutil.copyfile(D/'code'/name,out/'code'/name)
for name in ['trace_interpose.cpp','sampler-layout.h','operator_probe.cpp']:shutil.copyfile(D/'diagnostic'/name,out/'diagnostic'/name)
for name in ['fixtures.json','fresh-reproduction-summary.json','cpu-flags-B0.make','cpu-flags-B1.make',*[f'original-heldout-{i}-{arm}.json' for i in [1,2] for arm in ['B0','B1']]]:shutil.copyfile(D/'evidence'/name,out/'evidence'/name)
shutil.copyfile(D/'protocol-and-identity.json',out/'protocol-and-identity.json')
identity=json.loads((D/'protocol-and-identity.json').read_text());model=Path(identity['model']['path']);h=hashlib.sha256()
with model.open('rb') as f:
 for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
assert h.hexdigest()==identity['model']['sha256']
def run(script,*args):subprocess.run(['python3','-B',str(out/'code'/script),*args],check=True)
if a.mode=='quality':run('quality_diagnostic.py')
else:
 run('build_diagnostic.py')
 if a.mode=='single':run('build_operator_probe.py')
 for arm,name,extra in [('B0','replay-B0',[]),('B1','replay-B1',[]),('B1','replay-B1-q4off',['--q4-mode','off'])]:
  args=['--arm',arm,'--name',name,*extra]
  if a.mode=='single':args+=['--single-index','3']
  elif arm=='B1':args+=['--teacher-force']
  if a.mode=='single' and name=='replay-B1':args+=['--operator-probe']
  run('run_diagnostic.py',*args)
 run('compare_traces.py','replay-B0','replay-B1');run('compare_traces.py','replay-B0','replay-B1-q4off')
print('Fresh diagnostic results:',out)
