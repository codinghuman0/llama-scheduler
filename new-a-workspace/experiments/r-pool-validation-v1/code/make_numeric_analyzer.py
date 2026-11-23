from pathlib import Path
D=Path(__file__).resolve().parents[1]
s=(D/'evidence/history/diagnosis/code/compare_traces.py').read_text().split("if __name__=='__main__':")[0]
s=s.replace("D/'runs'/a_name,D/'runs'/b_name","D/'results'/a_name,D/'results'/b_name")
s=s.replace("path=(output_dir or D/'evidence')", "\n for row in logits:\n  if 'a_sha256' in row:row['byte_equal']=row['a_sha256']==row['b_sha256']\n path=(output_dir or D/'evidence')")
s+='''if __name__=='__main__':
 protocol=json.loads((D/'protocol-R.json').read_text());reports=[]
 for fid,target in protocol['numeric']['cohorts'].items():
  a_name=f'numeric-{fid}-B0';b_name=f'numeric-{fid}-R'
  report=compare(a_name,b_name)
  expected={(target,g) for g in protocol['numeric']['generations']}
  actual={(r['request'],r['generation']) for r in report['logits']}
  checkpoints=actual==expected and len(report['logits'])==len(expected)
  passed=checkpoints and all(r.get('same_computation_inputs_through_call') and r.get('all_finite') and r.get('max_absolute_difference')==0 and r.get('byte_equal') and r.get('argmax',[None,False])[0]==r.get('argmax',[None,False])[1] for r in report['logits'])
  reports.append(dict(cohort=fid,checkpoints_present=checkpoints,status='PASS' if passed else 'MISMATCH_OR_INCOMPARABLE',logits=report['logits']))
 result=dict(status='PASS' if all(r['status']=='PASS' for r in reports) else 'MISMATCH_OR_INCOMPARABLE',reports=reports)
 (D/'evidence/R-numeric-summary.json').write_text(json.dumps(result,indent=2)+'\\n')
 print(json.dumps(dict(status=result['status'],cohorts=[dict(cohort=r['cohort'],status=r['status'],maxabs=[x.get('max_absolute_difference') for x in r['logits']],byte_equal=[x.get('byte_equal') for x in r['logits']]) for r in reports]),indent=2))
'''
(D/'code/compare_numeric.py').write_text(s)
