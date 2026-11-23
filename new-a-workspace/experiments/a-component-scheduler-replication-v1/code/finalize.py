"""Finish one isolated replication and freeze a scoped submission reference."""
import argparse,hashlib,os,subprocess,tempfile,zipfile
from pathlib import Path
from common import *
from analyze import analyze,validate_raw
from recalculate import recalculate
from check import protection
from compare import compare
from reports import write_reports

def live_same(v):
 try:
  s=Path(f'/proc/{v["pid"]}/stat').read_text();return s.rsplit(')',1)[1].split()[19]==str(v['starttime'])
 except (FileNotFoundError,ProcessLookupError):return False

def calls_and_cleanup(names):
 counts=dict(fresh_server_starts=0,completion_HTTP_calls=0,individual_generations=0,actual_generated_tokens=0,warmup_cohorts=0,excluded_functional_check_cohorts=0,primary_measured_cohorts=0,new_full_logits_diagnostic_calls=0)
 owned=[];smokes=[]
 for mode,name in names.items():
  root=D/'results'/name;state=read(root/'campaigns.json')
  for folder in sorted(p for p in root.iterdir() if p.is_dir()):
   server=folder/'server'
   if (server/'process.json').exists():counts['fresh_server_starts']+=1
   for filename in ['processes.json','scheduler-processes.json']:
    if not (server/filename).exists():continue
    for kind,v in read(server/filename).items():
     if isinstance(v,dict) and 'starttime' in v:
      assert not live_same(v),('Owned process still alive',kind,v);owned.append(dict(source=str((server/filename).relative_to(D)),kind=kind,**v,alive=False))
   if (folder/'controlled-load/identity.json').exists():
    v=read(folder/'controlled-load/identity.json');assert not live_same(v);owned.append(dict(kind='load',**v,alive=False))
   for role in ['warmup','measured']:
    f=folder/(role+'-http-raw.json')
    if not f.exists():continue
    body=read(f);counts['completion_HTTP_calls']+=1;counts['individual_generations']+=len(body);counts['actual_generated_tokens']+=sum(len(v['tokens']) for v in body)
    key='warmup_cohorts' if role=='warmup' else 'primary_measured_cohorts' if mode=='full' else 'excluded_functional_check_cohorts';counts[key]+=1
  if mode!='full':
   assert state['status']=='COMPLETE'
   for r in state['completed']:
    spec={k:v for k,v in r.items() if k not in ['path','status']};validate_raw(D/r['path'],spec);smokes.append(r)
 counts['warmup_individual_generations']=counts['warmup_cohorts']*8
 counts['functional_check_individual_generations']=counts['excluded_functional_check_cohorts']*8
 counts['primary_measured_individual_generations']=counts['primary_measured_cohorts']*8
 counts['valid_smoke_visits']=len(smokes)
 save(D/'evidence/model-call-accounting.json',counts);save(D/'evidence/owned-process-cleanup.json',dict(status='PASS',identities=owned,smokes_reaudited=smokes));return counts

def release_map(new):
 value=read(D/'release-inputs.json');value.update(release_scope='Submission research reference for supported AMD/fixtures, not production-ready',runtime_changes=False,roles=dict(A_L='default performance execution; no existing default path/tag changed',A_S='scoped observe integration/evaluation'))
 value['actual_loaded_evidence']={}
 for arm in ['A_L','A_S']:
  rows=[]
  for v in new['visits']:
   if v['spec']['arm']!=arm:continue
   folder=D/v['raw']/'server';runtime=read(folder/'runtime.json')
   rows.append(dict(raw=v['raw'],argv=runtime['argv'],environment=runtime['environment'],loaded_ELF_sha256=runtime['loaded_elf_sha256'],aliases=read(folder/'loaded-aliases.json'),model=read(folder/'model-identity.json')))
  value['actual_loaded_evidence'][arm]=rows
 value['reproduction']=dict(readme='README.md',script='reproduce.sh',new_execution_namespaces=read(D/'replication-protocol.json')['replication']['namespaces'])
 save(D/'frozen-release-map.json',value)

def package(name,complete):
 dest=D/'a-component-scheduler-replication-v1-review.zip';assert not dest.exists()
 excluded={dest.name,dest.name+'.sha256','review-manifest.json','review-zip.json','package-validation.json'}
 members={str(f.relative_to(D)):dict(sha256=sha(f),size=f.stat().st_size) for f in sorted(D.rglob('*')) if f.is_file() and f.name not in excluded and not f.name.endswith('.zip') and '__pycache__' not in f.parts}
 manifest=dict(schema=1,members=members,scope='Isolated replication plus essential original raw reference; no model/runtime/full build')
 save(D/'review-manifest.json',manifest)
 with zipfile.ZipFile(dest,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for rel in members:z.write(D/rel,rel)
  z.writestr('REVIEW_MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
 with zipfile.ZipFile(dest) as z:
  assert z.testzip() is None and set(z.namelist())==set(members)|{'REVIEW_MANIFEST.json'}
  for rel,row in members.items():assert hashlib.sha256(z.read(rel)).hexdigest()==row['sha256']
  with tempfile.TemporaryDirectory(prefix='newa-replication-review-',dir='/tmp') as td:
   z.extractall(td);root=Path(td);outputs={}
   for which,args in [('new',['--name',name]),('original',['--name','attribution-v1','--root',str(root/'reference-original'),'--summary','component-summary.json'])]:
    r=subprocess.run(['python3','-B',str(root/'code/recalculate.py'),*args],capture_output=True,text=True,timeout=90);value=json.loads(r.stdout)
    assert r.returncode==(0 if complete or which=='original' else 2),(which,r.stderr)
    assert value['status']==('PASS' if complete or which=='original' else 'INCOMPLETE_INVALID')
    if value['status']=='PASS':assert value['raw_cohorts_checked']==128 and value['complete_contrasts']==10
    outputs[which]=dict(returncode=r.returncode,result=value)
 digest=sha(dest);(D/(dest.name+'.sha256')).write_text(digest+'  '+dest.name+'\n')
 save(D/'review-zip.json',dict(path=dest.name,sha256=digest,bytes=dest.stat().st_size,members=len(members)+1))
 save(D/'package-validation.json',dict(status='PASS',crc='PASS',all_member_hashes='PASS',membership='PASS',offline_model_free_recalculation=outputs,sha256=digest))
 return read(D/'review-zip.json')

def main():
 p=argparse.ArgumentParser();p.add_argument('--name',default='replication-v1');args=p.parse_args();names=read(D/'replication-protocol.json')['replication']['namespaces'];assert args.name==names['full']
 guard();no_model_process();verify_inputs();new=analyze(args.name);complete=new['status']!='INCOMPLETE_INVALID'
 try:proof=recalculate(args.name)
 except Exception as e:
  assert not complete;proof=dict(status='INCOMPLETE_INVALID',error=str(e))
 save(D/'evidence/independent-recalculation.json',proof)
 old= recalculate('attribution-v1',D/'reference-original','component-summary.json');save(D/'evidence/original-independent-recalculation.json',old)
 old_report=read(D/'inputs/original-component-summary.json')
 for v in old_report['visits']:validate_raw(D/'reference-original'/v['raw'],v['spec'])
 save(D/'evidence/original-raw-reaudit.json',dict(status='PASS',visits=64,scope='Read-only essential raw mirror validated against unchanged runtime/oracle; original verdict is not rewritten'))
 counts=calls_and_cleanup(names)
 if complete:assert counts==dict(fresh_server_starts=72,completion_HTTP_calls=144,individual_generations=1152,actual_generated_tokens=147456,warmup_cohorts=72,excluded_functional_check_cohorts=8,primary_measured_cohorts=64,new_full_logits_diagnostic_calls=0,warmup_individual_generations=576,functional_check_individual_generations=64,primary_measured_individual_generations=512,valid_smoke_visits=8)
 comparison=compare(new);write_reports(new,comparison,counts,proof);release_map(new)
 original_end=max(v['measured']['end_ns'] for v in old_report['visits']);new_start=min(v['warmup']['start_ns'] for v in new['visits']) if new['visits'] else None
 same_boot=read(D/'evidence/host-contract-comparison.json')['boot_same']
 if same_boot and new_start is not None:assert new_start>original_end
 save(D/'evidence/campaign-separation.json',dict(status='PASS',same_boot=same_boot,original_last_end_ns=original_end,new_first_start_ns=new_start,not_external_replication=True))
 preserved=protection();assert preserved['status']=='PASS';save(D/'evidence/protection-after.json',preserved)
 env=guard();r=subprocess.run(['sudo','-n','bpftool','-j','link','show'],capture_output=True,text=True,timeout=15);assert r.returncode==0,r.stderr
 links=json.loads(r.stdout);own_ids=set()
 for f in (D/'results').rglob('bpf-link.json'):own_ids.update(x['id'] for x in json.loads(read(f)['stdout']))
 assert not any(x['id'] in own_ids for x in links),'Owned BPF link remained'
 save(D/'evidence/final-cleanup.json',dict(status='PASS',environment=env,owned_processes_alive=False,owned_links_remaining=False,live_BPF_links=links,original_protection=preserved['status']))
 (D/'GOAL_STATE.md').write_text('# Frozen component replication\n\nWork status: '+('COMPLETE_FIXED_SCOPE' if complete else 'STOPPED_INCOMPLETE')+'\nScientific states: '+json.dumps(comparison['states'])+'\nNew campaign: exactly one; no repeats or Linux-only fallback.\nOriginal protected files: '+str(preserved['protected_files'])+'; unchanged.\nReports: replication-summary.md, campaign-comparison.md, claim-evidence-matrix.md.\nRecalculate: ./reproduce.sh recalculate\nStop: fixed campaign and submission reference complete; no third component campaign or feature research.\nA_L default performance role; A_S evaluation role; no runtime/default-path/tag overwrite.\n')
 event('replication-scope-finished',complete=complete,states=comparison['states'],new_campaigns=1,measured_visits=counts['primary_measured_cohorts'])
 audit=dict(work_status='COMPLETE_FIXED_SCOPE' if complete else 'STOPPED_INCOMPLETE',states=comparison['states'],original_protection=preserved,counts=counts,new_campaign_count=1,component_campaign_count=2 if complete else 1,extra_pairs=0,checks=dict(fresh_admission='PASS',fresh_linux_smoke='PASS',original_order_unchanged=sha(D/'order.json')==read(D/'replication-protocol.json')['replication']['original_order_sha256'],raw_independent_recalculation=proof['status'],original_raw_reaudit='PASS',negative_missing_visit='PASS',actual_scheduler_and_cleanup='PASS'),scope='same host, temporal replication, historical fixtures; no external/general/production claim')
 save(D/'completion-audit.json',audit)
 print(json.dumps(package(args.name,complete),indent=2));print(json.dumps(comparison['states'],indent=2))
if __name__=='__main__':main()
