import argparse,fcntl,json
from pathlib import Path
from run_r_gate import D,W,read,save,run_visit,preflight,event
p=argparse.ArgumentParser();p.add_argument('arm',choices=['A','P']);p.add_argument('--revision',default='');args=p.parse_args();arm=args.arm
state=read(D/'gate-results.json');assert state['R']=='COMPATIBLE_IN_TESTED_SCOPE'
if arm=='P':assert state['E-R']=='COMPATIBLE_IN_TESTED_SCOPE'
preflight();case=read(D/'cases-AP.json')[arm];rows=[]
with (W/'state/.measurement.lock').open('r') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 for fixture in read(D/'fixtures.json'):
  fid=fixture['id'];result=run_visit(f'functional-{fid}-{arm}'+('-'+args.revision if args.revision else ''),case,fixture)
  oracle=read(D/'results'/f'free-{fid}-B0-r1'/'result.json')['measured']
  row=dict(cohort=fid,revision=args.revision,runtime=case['runtime'],warmup_equals_B0_R=result['warmup']==oracle,measured_equals_B0_R=result['measured']==oracle,within_server_equal=result['warmup']==result['measured']);rows.append(row)
  save(D/'evidence'/f'{arm}-free-summary.json',dict(status='IN_PROGRESS',visits=rows));print(json.dumps(row),flush=True)
 passed=all(r['warmup_equals_B0_R'] and r['measured_equals_B0_R'] and r['within_server_equal'] for r in rows)
 save(D/'evidence'/f'{arm}-free-summary.json',dict(status='PASS' if passed else 'MISMATCH',visits=rows))
 if arm=='A':
  state['E-R']='COMPATIBLE_IN_TESTED_SCOPE' if passed else 'MISMATCH';state['note']='E unchanged; fresh free output tested against validated B0/R. Pool/lifecycle gates remain.';save(D/'gate-results.json',state)
 event(dict(stage=arm+'-free-gate',status='PASS' if passed else 'MISMATCH',fresh_servers=4))
 with (D/'GOAL_STATE.md').open('a') as f:f.write('\n'+arm+' free-generation stage: '+('PASS' if passed else 'MISMATCH')+'. Raw: results/functional-*; summary: evidence/'+arm+'-free-summary.json.\n')
 print(arm+' free gate '+('PASS' if passed else 'MISMATCH'),flush=True)
