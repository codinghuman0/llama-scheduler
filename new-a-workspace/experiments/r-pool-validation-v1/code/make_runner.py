from pathlib import Path
D=Path(__file__).resolve().parents[1]
s=(D/'evidence/history/diagnosis/code/reproduce_frozen.py').read_text().split('\ndef main():')[0]
s=s.replace("W=Path('/home/codinghuman/projects')","W=D.parents[1]")
s=s.replace("loaded={p:sha(p) for p in mapped if Path(p).is_file() and ('.so' in Path(p).name or p==command[0])};assert all(loaded.get(p)==h for p,h in case['artifacts'].items())", """loaded={p:sha(p) for p in mapped if Path(p).is_file() and ('.so' in Path(p).name or p==command[0])}
   for expected,digest in case['artifacts'].items():
    assert any(Path(p).stat().st_ino==Path(expected).stat().st_ino and h==digest for p,h in loaded.items()),('Unexpected DSO',expected,loaded)
   assert str(W/'models/model.gguf') in mapped, 'Model mapping missing'
   assert sorted(os.sched_getaffinity(pid))==[0,2,4,6,8,10]
   assert os.sched_getscheduler(pid)==os.SCHED_OTHER
   save(folder/'model-identity.json',dict(path=str(W/'models/model.gguf'),sha256='f3bdf9cf31dee4b57ae4e455a1cb0d01b5c2c1b50d72d3112141c195506c2840',inode=(W/'models/model.gguf').stat().st_ino,checked_before_campaign=True))""")
s=s.replace("return result\n finally:","save(folder/'result.json',result)\n   return result\n finally:")
s+='''
def preflight():
 guard();os.sched_setaffinity(0,{11})
 assert sha(W/'models/model.gguf')=='f3bdf9cf31dee4b57ae4e455a1cb0d01b5c2c1b50d72d3112141c195506c2840'
 for p in Path('/proc').iterdir():
  if p.name.isdigit():
   try:assert (p/'comm').read_text().strip() not in ['llama-server','llama-bench','cc1plus','cc1','cmake','ninja'],('Competing process',p.name)
   except OSError:pass

def event(x):
 import datetime
 with (D/'ledger.jsonl').open('a') as f:f.write(json.dumps(dict(time=datetime.datetime.now(datetime.timezone.utc).isoformat(),**x))+'\\n')

def run_visit(name,case,fixture,diagnostic=None):
 folder=D/'results'/name
 if folder.exists():
  assert (folder/'result.json').exists() and read(folder/'cleanup.json')['status']=='PASS',('Incomplete visit retained; diagnose before retry',name)
  return read(folder/'result.json')
 event(dict(stage='R-visit-start',name=name,case=case['runtime'],diagnostic=diagnostic is not None))
 try:
  result=visit(case,fixture,folder,diagnostic)
 except BaseException as exc:
  save(folder/'failure.json',dict(type=type(exc).__name__,message=str(exc)))
  event(dict(stage='R-visit-failure',name=name,error=str(exc)));raise
 event(dict(stage='R-visit-complete',name=name,warmup_equals_measured=result['warmup']==result['measured']))
 return result

def free():
 protocol=read(D/'protocol-R.json');cases=read(D/'cases.json');fixtures=read(D/'fixtures.json');summary=[]
 assert sha(D/'cases.json')==protocol['cases_sha256'] and sha(D/'fixtures.json')==protocol['fixtures_sha256']
 for fixture in fixtures:
  seen={'B0':0,'R':0};previous={};oracle=None
  for arm in protocol['free_generation']['order']:
   seen[arm]+=1;name=f'free-{fixture["id"]}-{arm}-r{seen[arm]}'
   result=run_visit(name,cases[arm],fixture)
   if oracle is None:oracle=result['measured']
   item=dict(run=name,cohort=fixture['id'],arm=arm,repeat=seen[arm],within_server_equal=result['warmup']==result['measured'],warmup_equals_B0=result['warmup']==oracle,measured_equals_B0=result['measured']==oracle,equals_prior_fresh=None if arm not in previous else result['measured']==previous[arm],first_differences=[dict(request=i,generation=next((j for j,(u,v) in enumerate(zip(a,b)) if u!=v),None)) for i,(a,b) in enumerate(zip(result['measured'],oracle)) if a!=b])
   previous[arm]=result['measured'];summary.append(item)
   save(D/'evidence/R-free-summary.json',dict(status='IN_PROGRESS',visits=summary));print(json.dumps(item),flush=True)
 status='PASS' if all(x['within_server_equal'] and x['warmup_equals_B0'] and x['measured_equals_B0'] and x['equals_prior_fresh'] is not False for x in summary) else 'OUTPUT_MISMATCH'
 save(D/'evidence/R-free-summary.json',dict(status=status,visits=summary,scope='Free-generation exact tokens in declared fixtures, not general quality equivalence'))
 event(dict(stage='R-free-complete',status=status,fresh_servers=len(summary)))
 print('FREE GATE '+status,flush=True)

def numeric():
 protocol=read(D/'protocol-R.json');cases=read(D/'cases.json');fixtures={f['id']:f for f in read(D/'fixtures.json')}
 for fid,target in protocol['numeric']['cohorts'].items():
  fixture=fixtures[fid];oracle=read(D/'results'/f'free-{fid}-B0-r1'/'result.json')['measured']
  for arm in protocol['numeric']['arms']:
   probe=D/'evidence/history/diagnosis/diagnostic'/('trace-B0.so' if arm=='B0' else 'trace-B1.so')
   config=dict(prompts=[r['prompt'] for r in fixture['requests']],forced_tokens=oracle,teacher_force=False,target_request=target,max_logit_generation=3,max_trace_calls=16)
   result=run_visit(f'numeric-{fid}-{arm}',cases[arm],fixture,dict(overlay=str(probe),overlay_sha256=sha(probe),config=config))
   save(D/'results'/f'numeric-{fid}-{arm}'/'observer-output-check.json',dict(warmup_equals_free_oracle=result['warmup']==oracle,measured_equals_free_oracle=result['measured']==oracle,teacher_force=False))
 event(dict(stage='R-numeric-capture-complete',fresh_servers=4))

def route():
 fixture=read(D/'fixtures.json')[0]
 run_visit('route-heldout-1-R',read(D/'cases.json')['R-diagnostic'],fixture)
 event(dict(stage='R-route-model-complete',fresh_servers=1))

if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('stage',choices=['free','numeric','route']);args=p.parse_args()
 preflight()
 with (W/'state/.measurement.lock').open('r') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  globals()[args.stage]()
'''
(D/'code/run_r_gate.py').write_text(s)
