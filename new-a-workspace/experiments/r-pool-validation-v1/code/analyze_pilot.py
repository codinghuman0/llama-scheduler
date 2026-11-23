from pathlib import Path
import argparse,json,random,statistics,datetime
D=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text())
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def percentile(values,p):
 values=sorted(values);i=(len(values)-1)*p;lo=int(i);hi=min(lo+1,len(values)-1);return values[lo]+(values[hi]-values[lo])*(i-lo)
def bootstrap(values,seed,repeats):
 rng=random.Random(seed);v=[statistics.mean(rng.choices(values,k=len(values))) for _ in range(repeats)];return [percentile(v,.025),percentile(v,.975)]
def analyze(campaign):
 root=D/'results'/campaign;source=read(root/'campaign.json');protocol=read(D/'protocol-AP.json');rows=source['completed'];conditions=[]
 for condition in protocol['pilot']['conditions']:
  pairs=[]
  for block in range(1,5):
   visits={r['spec']['arm']:r for r in rows if r['spec']['condition']==condition and r['spec']['block']==block}
   if set(visits)!={'A','P'}:continue
   a,p=visits['A'],visits['P'];am,pm=a['metrics'],p['metrics'];assert a['spec']['cohort']==p['spec']['cohort']
   pair=dict(block=block,cohort=a['spec']['cohort'],valid=a['valid'] and p['valid'],A_throughput=am['throughput'],P_throughput=pm['throughput'],gain_pct=100*(pm['throughput']/am['throughput']-1),A_wall_s=am['cohort_http_wall_s'],P_wall_s=pm['cohort_http_wall_s'],A_cpu_s=am['cpu_time_s'],P_cpu_s=pm['cpu_time_s'],same_E_decisions=a['measured_decisions_5_6']==p['measured_decisions_5_6'],A_E_decisions=a['measured_decisions_5_6'],P_E_decisions=p['measured_decisions_5_6'],A_background_cores=am.get('controlled_load',{}).get('mean_cpu_cores'),P_background_cores=pm.get('controlled_load',{}).get('mean_cpu_cores'))
   pairs.append(pair)
  gains=[p['gain_pct'] for p in pairs];valid=len(pairs)==4 and all(x['valid'] for x in pairs)
  summary=dict(condition=condition,planned_pairs=4,completed_pairs=len(pairs),valid=valid,pairs=pairs)
  if gains:
   summary.update(mean_paired_gain_pct=statistics.mean(gains),paired_bootstrap_95_pct=bootstrap(gains,protocol['uncertainty']['seed'],protocol['uncertainty']['bootstrap_replicates']),faster_pair_fraction=sum(g>0 for g in gains)/len(gains),mean_absolute={k:statistics.mean(p[k] for p in pairs) for k in ['A_throughput','P_throughput','A_wall_s','P_wall_s','A_cpu_s','P_cpu_s']},different_E_decision_pairs=[p['block'] for p in pairs if not p['same_E_decisions']])
  conditions.append(summary)
 if source['status']!='COMPLETE' or not all(c['valid'] for c in conditions):status='INCONCLUSIVE'
 elif any(c['mean_paired_gain_pct']<0 and c['paired_bootstrap_95_pct'][1]<0 for c in conditions):status='REGRESSION'
 elif all(c['mean_paired_gain_pct']>0 and c['paired_bootstrap_95_pct'][0]>0 and c['faster_pair_fraction']>=.75 for c in conditions):status='PROMISING'
 else:status='INCONCLUSIVE'
 adoption={'PROMISING':'RESEARCH_CANDIDATE_ONLY','INCONCLUSIVE':'KEEP_OPTIONAL_OFF','REGRESSION':'REJECT_OR_HOLD'}[status]
 out=dict(status=status,adoption=adoption,contrast='P-padding-fix / A',conditions=conditions,bootstrap_unit='Paired block, n=4 per condition, no request-level inflation',limitations=['Exploratory pilot, not independent confirmation or equivalence proof','No B0 throughput claim; old gains do not transfer','If E choices differ, measure E+pool integration effect rather than pure allocation cost'],excluded_or_failed=[r for r in rows if not r['valid']],extra_pairs=0)
 save(root/'analysis.json',out);state=read(D/'gate-results.json');state['Pool pilot']=status;state['Adoption']=adoption;state['note']='All required functional gates completed; limited prespecified pilot analyzed, not confirmation or B0 performance proof.';save(D/'gate-results.json',state)
 with (D/'ledger.jsonl').open('a') as f:f.write(json.dumps(dict(time=datetime.datetime.now(datetime.timezone.utc).isoformat(),stage='pilot-analysis',campaign=campaign,status=status,adoption=adoption))+'\n')
 print(json.dumps(out,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--campaign',default='pilot-v1');args=p.parse_args();analyze(args.campaign)
