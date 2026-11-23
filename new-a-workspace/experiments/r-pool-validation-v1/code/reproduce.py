from pathlib import Path
import argparse,copy,datetime,fcntl,hashlib,json,os,shutil,subprocess,sys
D=Path(__file__).resolve().parents[1];W=D.parents[1]
def read(p):return json.loads(p.read_text())
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for part in iter(lambda:f.read(1024*1024),b''):h.update(part)
 return h.hexdigest()
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def stamp():return datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
def ordinary():
 assert os.getuid()!=0,'Run as the ordinary user; do not use sudo'
 assert Path('/sys/kernel/sched_ext/state').read_text().strip()=='disabled','Default Linux required; do not detach an unrelated scheduler'
 assert shutil.disk_usage(W).free>=512*1024**2,'Insufficient free disk'
def verified():
 for name in ['R-checkpoint.json','AP-functional-checkpoint.json']:
  p=D/'evidence'/name;record=read(p)
  for rel,digest in record['artifacts'].items():assert sha(D/rel)==digest,rel
 for arm in ['A','P']:
  case=read(D/'cases-AP.json')[arm]
  for path,digest in case['artifacts'].items():assert sha(Path(path))==digest,path
 assert sha(W/'models/model.gguf')=='f3bdf9cf31dee4b57ae4e455a1cb0d01b5c2c1b50d72d3112141c195506c2840'
 return dict(status='PASS',R=read(D/'gate-results.json')['R'],E_R=read(D/'gate-results.json')['E-R'],pool=read(D/'gate-results.json')['Pool integration'],model_and_runtime_hashes_checked=True,sudo_used=False)
def smoke():
 import run_r_gate as r
 r.preflight();cases=read(D/'cases-AP.json');fixture=next(f for f in read(D/'fixtures.json') if f['id']=='h1-request3-singleton');oracle=read(D/'results/free-h1-request3-singleton-B0-r1/result.json')['measured']
 out=D/'reproductions'/('smoke-'+stamp());out.mkdir(parents=True);results=[]
 with (W/'state/.measurement.lock').open('r') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);verified()
  for arm in ['A','P']:
   case=copy.deepcopy(cases[arm]);case['scope']='REPRODUCTION_SMOKE_NOT_PERFORMANCE';value=r.visit(case,fixture,out/arm)
   equal=value['warmup']==value['measured']==oracle;results.append(dict(arm=arm,token_equality=equal));save(out/'result.json',dict(status='IN_PROGRESS',arms=results));assert equal
  save(out/'result.json',dict(status='PASS',arms=results,fresh_servers=2,completed_HTTP_generations=4,scope='Separate post-pilot script smoke; not additional statistical pairs'))
 print(out)
def build(which):
 ordinary();verified();new=D.parent/(f'r-pool-rebuild-{which}-'+stamp());new.mkdir();(new/'code').mkdir();(new/'evidence/history').mkdir(parents=True);(new/'patches').mkdir();(new/'candidates').mkdir();(new/'results').mkdir()
 for name in ['build_r.py','build_p.py','fix_p_padding.py','override-padding-check.cpp']:
  shutil.copy2(D/'code'/name,new/'code'/name)
 (new/'GOAL_STATE.md').write_text('Independent rebuild only. No new model/performance validation is implied.\n')
 if which=='R':
  shutil.copytree(D/'evidence/history/cpu-build',new/'evidence/history/cpu-build')
  subprocess.run([sys.executable,'-B',str(new/'code/build_r.py')],check=True)
 else:
  shutil.copytree(D/'evidence/history/server-build',new/'evidence/history/server-build',copy_function=os.link)
  # Reuse byte-verified R/A DSOs; only the minimal server target is rebuilt.
  for arm in ['R','A']:
   target=new/'candidates'/arm;target.mkdir();shutil.copytree(D/'candidates'/arm/'runtime',target/'runtime',copy_function=os.link)
  cases=copy.deepcopy(read(D/'cases-AP.json'));cases={k:v for k,v in cases.items() if k=='A'}
  for case in cases.values():
   case['server_argv']=[v.replace(str(D),str(new)) for v in case['server_argv']]
   case['server_env']={k:v.replace(str(D),str(new)) for k,v in case['server_env'].items()}
   case['artifacts']={k.replace(str(D),str(new)):v for k,v in case['artifacts'].items()}
  save(new/'cases-AP.json',cases);save(new/'gate-results.json',dict(R='COMPATIBLE_IN_TESTED_SCOPE',**{'E-R':'COMPATIBLE_IN_TESTED_SCOPE'},basis='Exact existing R/A binary hashes reused; no new validation claimed'))
  subprocess.run([sys.executable,'-B',str(new/'code/build_p.py')],check=True)
  subprocess.run([sys.executable,'-B',str(new/'code/fix_p_padding.py')],check=True)
  identity=read(new/'candidates/P-padding-fix/identity.json');identity['initial_functional_failure']=str(D/'results/functional-heldout-1-P');identity['status']='REBUILT_NOT_NEW_MODEL_VALIDATED';save(new/'candidates/P-padding-fix/identity.json',identity)
 print('Rebuild retained:',new,'; new model validation is required before adoption')
def main():
 parser=argparse.ArgumentParser(description='Ordinary-user reproduction; no sudo/BPF, no changes to frozen baseline files.')
 parser.add_argument('mode',choices=['verify','smoke','pilot','build-r','build-p']);parser.add_argument('--campaign');args=parser.parse_args();ordinary()
 if args.mode=='verify':
  with (W/'state/.measurement.lock').open('r') as lock:
   fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);print(json.dumps(verified(),indent=2))
 elif args.mode=='smoke':smoke()
 elif args.mode.startswith('build-'):build(args.mode[-1].upper())
 else:
  campaign=args.campaign or 'pilot-reproduction-'+stamp()
  subprocess.run([sys.executable,'-B',str(D/'code/run_pilot.py'),'--campaign',campaign],check=True)
  subprocess.run([sys.executable,'-B',str(D/'code/analyze_pilot.py'),'--campaign',campaign],check=True)
  print('Independent pilot output:',D/'results'/campaign,'; original pilot-v1 raw remains unchanged')
if __name__=='__main__':main()
