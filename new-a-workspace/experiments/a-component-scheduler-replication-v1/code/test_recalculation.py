"""Regression and missing-visit negative test using private temporary copies."""
import json,shutil,subprocess,sys,tempfile
from pathlib import Path
from common import *

def call(script,root,legacy=False):
 args=[sys.executable,'-B',str(script),'--name','attribution-v1']
 if not legacy:args+=['--root',str(root),'--summary','component-summary.json']
 r=subprocess.run(args,capture_output=True,text=True,timeout=60)
 return dict(returncode=r.returncode,stdout=json.loads(r.stdout),stderr=r.stderr)

def main():
 original=D.parent/'a-component-scheduler-attribution-v1'
 with tempfile.TemporaryDirectory(prefix='newa-completeness-',dir='/tmp') as td:
  t=Path(td);shutil.copytree(D/'reference-original',t,dirs_exist_ok=True);(t/'code').mkdir()
  shutil.copy2(original/'code/recalculate.py',t/'code/recalculate-legacy.py');shutil.copy2(D/'code/recalculate.py',t/'code/recalculate.py')
  old=call(t/'code/recalculate-legacy.py',t,True);new=call(t/'code/recalculate.py',t)
  assert old['returncode']==new['returncode']==0 and old['stdout']==new['stdout'],'Complete-data result changed'
  assert new['stdout']['raw_cohorts_checked']==128 and new['stdout']['complete_contrasts']==10
  visit=sorted(p for p in (t/'results/attribution-v1').iterdir() if p.is_dir())[0]
  omitted=visit.name;visit.rename(t/'omitted-visit')
  broken_old=call(t/'code/recalculate-legacy.py',t,True);broken_new=call(t/'code/recalculate.py',t)
  assert broken_old['returncode']==0 and broken_old['stdout']['status']=='PASS','Original incomplete-pass behavior not reproduced'
  assert broken_new['returncode']!=0 and broken_new['stdout']['status']=='INCOMPLETE_INVALID','Missing visit accepted'
  assert 'missing planned visit' in broken_new['stdout']['error']
  save(D/'evidence/recalculation-completeness-test.json',dict(status='PASS',complete_data_output_exactly_equal=True,statistics_formula_changed=False,omitted_visit=omitted,original_file_untouched=True,normal_legacy=old,normal_strict=new,missing_legacy=broken_old,missing_strict=broken_new,temporary_copy_removed_on_exit=True))
 print('PASS: unchanged complete output; removed one visit -> nonzero INCOMPLETE_INVALID')
if __name__=='__main__':main()
