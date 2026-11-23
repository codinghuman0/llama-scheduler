"""Separate campaign claims and descriptive absolute/environment comparisons."""
import statistics
from common import *
ARMS=['B0_L','F6_L','A_L','A_S']

def choices(report,condition,arm):
 out={}
 for v in report['visits']:
  if v['spec']['condition']!=condition or v['spec']['arm']!=arm:continue
  eligible=[sum(e['eligible_by_size_5_6'][size][j] for e in v['E_epochs'] for size in range(2,9)) for j in range(2)]
  out[str(v['spec']['block'])]=dict(counts_5_6=eligible,chosen=[5+j for j,x in enumerate(eligible) if x],shadow=sorted({e['sample']['shadow_choice'] for e in v['E_epochs']}),locked=all(e['locked'] for e in v['E_epochs']))
 return out

def verdicts(report):
 if report['status']=='INCOMPLETE_INVALID':return dict(overall_system='INCOMPLETE_INVALID',E_cpu25='INCOMPLETE_INVALID',E_ambient='INCOMPLETE_INVALID',S_cpu25='INCOMPLETE_INVALID',S_ambient='INCOMPLETE_INVALID')
 result={'overall_system':'PASS' if all(c['contrasts']['A_S/B0_L']['target_pass'] for c in report['cells']) else 'BELOW_OR_INCONCLUSIVE_GATE','conditions':{}}
 for c in report['cells']:
  cond=c['condition'];f,a,s=[choices(report,cond,x) for x in ['F6_L','A_L','A_S']]
  differences=[int(b) for b in f if f[b]['chosen']!=a[b]['chosen']]
  mediated=[int(b) for b in a if a[b]['chosen']!=s[b]['chosen']]
  sign=c['contrasts']['A_L/F6_L']['sign']
  result['E_'+cond]=sign if differences else 'inconclusive_same_observed_choice'
  result['S_'+cond]=c['contrasts']['A_S/A_L']['sign']
  result['conditions'][cond]=dict(F6=f,A=a,AS=s,E_different_choice_blocks=differences,S_E_mediated_blocks=mediated,E_positive_and_choice_different=sign=='positive' and bool(differences),system_gate=c['contrasts']['A_S/B0_L']['target_pass'],system_lower_at_least_5=c['contrasts']['A_S/B0_L']['bootstrap_95_pct'][0]>=5)
 return result

def ranges(vals):return [min(vals),max(vals)] if vals else None

def environment_groups(report,root,campaign=None,legacy=False):
 groups={}
 for cond in ['ambient','cpu25']:
  for arm in (['B0','A'] if legacy else ARMS):
   visits=[v for v in report['visits'] if v['spec']['condition']==cond and v['spec']['arm']==arm and (campaign is None or v['spec']['campaign']==campaign)]
   if not visits:continue
   samples=[read(root/v['raw']/'http-observations.json')[1] for v in visits]
   envs=[s[k] for s in samples for k in ['environment_before','environment_after']]
   def unique(key):return [read_value for read_value in {json.dumps(e[key],sort_keys=True) for e in envs}]
   groups[cond+'/'+({'B0':'B0_L','A':'A_L'}.get(arm,arm))]=dict(samples=len(samples),CPU_temperature_c_range=ranges([e['temperature_c']['k10temp:temp1_input'] for e in envs]),selected_frequency_mean_GHz_range=ranges([statistics.mean(float(e['frequency_khz'][str(cpu)]) for cpu in CPUS)/1e6 for e in envs]),loadavg1_range=ranges([float(e['loadavg'].split()[0]) for e in envs]),actual_generator_cores_range=ranges([s['controlled_load']['mean_cpu_cores'] for s in samples if 'controlled_load' in s]),power_states_json=unique('power'),governor_states_json=unique('governors'),boost_states_json=unique('boost'),raw=[v['raw'] for v in visits],scope='instantaneous pre/post brackets, not causal profiling')
 return groups

def group_results(report):
 out={}
 for c in report['cells']:
  cond=c['condition'];out[cond]={}
  for label,v in c['contrasts'].items():
   cand,ctrl=label.split('/');groups={}
   for block in c['blocks']:
    spec=next(x['spec'] for x in report['visits'] if x['spec']['condition']==cond and x['spec']['block']==block['block'])
    order=' > '.join(spec['arm_order']);groups.setdefault(order,[]).append(block['gains'][label])
   out[cond][label]=dict(by_cohort=v['by_cohort'],by_order={k:dict(n=len(xs),mean_paired_gain_pct=statistics.mean(xs),range_pct=ranges(xs)) for k,xs in groups.items()},pair_gain_range_pct=ranges([b['gains'][label] for b in c['blocks']]))
 return out

def compare(new):
 old=read(D/'inputs/original-component-summary.json');prior=read(D/'inputs/prior-direct-comparison-summary.json')
 verdict={'original_component':verdicts(old),'replication_component':verdicts(new)}
 complete=new['status']!='INCOMPLETE_INVALID'
 system=complete and all(v['overall_system']=='PASS' for v in verdict.values())
 e=complete and all(v['conditions']['cpu25']['E_positive_and_choice_different'] for v in verdict.values())
 states=dict(overall_system='REPLICATED_SCOPED_SYSTEM_GAIN' if system else 'MIXED_OR_INCONCLUSIVE_REPLICATION' if complete else 'INCOMPLETE_INVALID',E_cpu25='E_SELECTION_REPLICATED_CPU25' if e else 'MIXED_OR_INCONCLUSIVE_REPLICATION' if complete else 'INCOMPLETE_INVALID',S_effect={name:{c:v['S_'+c] for c in ['ambient','cpu25']} for name,v in verdict.items()})
 env={'original_component':environment_groups(old,D/'reference-original'),'replication_component':environment_groups(new,D)}
 earlier=[]
 for campaign in [1,2]:
  cells=[c for c in prior['cells'] if c['campaign']==campaign]
  earlier.append(dict(campaign=campaign,scope='runtime A/B0 only, not E or S replication',cells=cells,environment=environment_groups(prior,D.parent/'a-b0-direct-confirmation-v1',campaign,True)))
 absolute_change={}
 for cond in ['ambient','cpu25']:
  a=next(c for c in old['cells'] if c['condition']==cond);b=next(c for c in new['cells'] if c['condition']==cond)
  absolute_change[cond]={arm:100*(b['absolute'][arm]['tokens_per_second']/a['absolute'][arm]['tokens_per_second']-1) for arm in ARMS} if 'absolute' in b else {}
 rows=dict(original_component=dict(status=old['status'],cells=old['cells'],counts=old['counts'],grouped=group_results(old)),replication_component=dict(status=new['status'],cells=new['cells'],counts=new['counts'],grouped=group_results(new)))
 result=dict(states=states,campaign_verdicts=verdict,component_campaign_count=2 if complete else 1,new_campaign_count=1,external_replication=False,rows=rows,prior_A_B0_reference=earlier,environment=env,between_component_campaign_absolute_mean_change_pct=absolute_change,baseline_variation_cause='CAUSE_UNDETERMINED',no_pooled_CI=True,all_slow_valid_blocks_retained=True,limitations=['same host and previously observed fixtures','not external team/device replication','no fixed5 or fixed6_S; no complete interaction or all-static superiority','E/F6 does not isolate semantic label value versus another controller','observe has no phase-dependent placement','OpenMP observed team-size sets are not continuous graph instrumentation','nonstream TTFT/p95 not measured; CPU seconds not energy'])
 save(D/'campaign-comparison.json',result);return result
