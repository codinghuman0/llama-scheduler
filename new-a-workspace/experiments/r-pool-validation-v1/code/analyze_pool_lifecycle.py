from pathlib import Path
import collections,json
D=Path(__file__).resolve().parents[1]
reports=[]
for arm in ['A','P']:
 folder=D/'results'/f'lifecycle-{arm}-observer-v2'
 life=json.loads((folder/'lifecycle-summary.json').read_text());assert life['status']=='PASS'
 rows=[json.loads(x) for x in (folder/'pool-events.jsonl').read_text().splitlines()];live={};created=[];freed=[];graphs=[];pending=None
 for row in rows:
  event=row['event'];ptr=row['pool']
  if event=='new_api':
   assert ptr not in live and row['status']==0
   assert row['requested_threads'] in [5,6] and row['poll']==50 and row['priority']==0 and row['paused']==1 and row['masked']==0
   live[ptr]=row;created.append(row)
  elif event=='free':
   if ptr in live:freed.append(dict(created=live.pop(ptr),freed=row))
  elif event=='graph_begin':
   assert pending is None
   pending=row;attached=ptr!='(nil)'
   if attached:
    assert ptr in live and row['requested_threads']==live[ptr]['requested_threads']
   if arm=='P' and live:assert attached,'Disposable graph while persistent pools are attached'
   if arm=='A':assert not attached,'A unexpectedly attaches a pool'
   graphs.append(dict(**row,attached=attached,live_api_pools=len(live)))
  elif event=='graph_end':
   assert pending and pending['pool']==ptr and pending['requested_threads']==row['requested_threads']
   assert row['status'] in [0,1],'Unexpected graph status'
   pending=None
 assert not live and pending is None,'Pool or graph remains after process cleanup'
 steady=[g for g in graphs if g['role'] in ['warmup','measured','after-cancel','after-error']]
 assert steady and {g['requested_threads'] for g in steady}=={5,6}
 if arm=='P':
  assert len(created)==len(freed)==6
  assert all(g['attached'] for g in steady)
  assert not any(x['role'] in ['warmup','measured','after-cancel','after-error'] for x in created)
  assert len({g['pool'] for g in steady})==2
  for cycle in [1,2]:
   creation=[x for x in created if x['role']==f'resume-{cycle}'];assert sorted(x['requested_threads'] for x in creation)==[5,6]
   assert len([x for x in freed if x['freed']['role']==f'sleep-{cycle}'])==2
  assert len([x for x in freed if x['freed']['role']=='teardown'])==2
 else:assert not created
 report=dict(arm=arm,status='PASS',persistent_api_creations=len(created),persistent_api_frees=len(freed),steady_graphs=len(steady),steady_disposable_graphs=sum(not x['attached'] for x in steady),steady_requested_threads=sorted({x['requested_threads'] for x in steady}),all_roles={role:dict(graphs=len(values),attached=sum(x['attached'] for x in values),disposable=sum(not x['attached'] for x in values)) for role in sorted({x['role'] for x in graphs}) for values in [[x for x in graphs if x['role']==role]]},limitations='Graph/pool reuse and lifecycle, not a claim about native pthread wakeups; OpenMP pause/resume remains a no-op')
 (folder/'pool-reuse-summary.json').write_text(json.dumps(report,indent=2)+'\n');reports.append(report)
(D/'evidence/AP-lifecycle-summary.json').write_text(json.dumps(dict(status='PASS',arms=reports),indent=2)+'\n')
print(json.dumps(reports,indent=2))
