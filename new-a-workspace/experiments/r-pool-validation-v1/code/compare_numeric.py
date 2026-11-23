#!/usr/bin/env python3
from pathlib import Path
import argparse,array,hashlib,json,math,sys
D=Path(__file__).resolve().parents[1]
def rows(p):return [json.loads(l) for l in p.read_text().splitlines()]
def data(p):
 if p.exists():return p.read_bytes()
 mapping=json.loads((D/'LOGIT_BLOBS.json').read_text());return (D/'logit-blobs'/mapping[str(p.relative_to(D))]).read_bytes()
def f32(p):
 assert sys.byteorder=='little'
 a=array.array('f');a.frombytes(data(p));assert a.itemsize==4;return a
def compare(a_name,b_name,output_dir=None):
 a,b=D/'results'/a_name,D/'results'/b_name;aa,bb=rows(a/'events.jsonl'),rows(b/'events.jsonl');sam_a=[r for r in aa if r['event']=='sample'];sam_b=[r for r in bb if r['event']=='sample']
 assert [(r['call'],r['request'],r['generation'],r['seq'],r['pos']) for r in sam_a]==[(r['call'],r['request'],r['generation'],r['seq'],r['pos']) for r in sam_b],'Sampling schedule differs'
 first=next(((x,y) for x,y in zip(sam_a,sam_b) if x['sampler_token']!=y['sampler_token']),None)
 equality=[]
 for call in range(1,min(max(r['call'] for r in aa),max(r['call'] for r in bb))+1):
  da=[x for x in aa if x['event']=='decode_begin' and x['call']==call];db=[x for x in bb if x['event']=='decode_begin' and x['call']==call]
  ua=[x for x in aa if x['event']=='physical_ubatch' and x['call']==call];ub=[x for x in bb if x['event']=='physical_ubatch' and x['call']==call]
  ga=[x for x in aa if x['event']=='graph_profile' and x['call']==call];gb=[x for x in bb if x['event']=='graph_profile' and x['call']==call]
  for collection in [ua,ub]:
   for row in collection:row.pop('profile',None)
  equality.append(dict(call=call,batch_and_all_sequence_history_equal=bool(da and db) and all(da[0][k]==db[0][k] for k in ['tokens','logical_token_history','kv_before']),physical_ubatches_equal=ua==ub,graph_worker_profile_equal=ga==gb))
 logits=[]
 for x,y in zip(sam_a,sam_b):
  if 'raw_logits_file' not in x or 'raw_logits_file' not in y:continue
  through=[r for r in equality if r['call']<=x['call']]
  same_inputs=all(all(r[k] for k in ['batch_and_all_sequence_history_equal','physical_ubatches_equal','graph_worker_profile_equal']) for r in through)
  if not same_inputs:
   logits.append(dict(call=x['call'],request=x['request'],generation=x['generation'],status='NOT_COMPARED_DIFFERENT_ALL_SEQUENCE_HISTORY',same_computation_inputs_through_call=False))
   continue
  av,bv=f32(a/x['raw_logits_file']),f32(b/y['raw_logits_file']);assert len(av)==len(bv)
  finite=all(math.isfinite(t) for t in av) and all(math.isfinite(t) for t in bv)
  delta=[abs(u-v) for u,v in zip(av,bv)];floor=.001
  maxidx=max(range(len(delta)),key=delta.__getitem__)
  ra=sorted(range(len(av)),key=av.__getitem__,reverse=True)[:10];rb=sorted(range(len(bv)),key=bv.__getitem__,reverse=True)[:10];union=sorted(set(ra)|set(rb))
  through=[r for r in equality if r['call']<=x['call']]
  processors_a=[r for r in aa if r['event']=='processor' and r['request']==x['request'] and r['generation']==x['generation']]
  processors_b=[r for r in bb if r['event']=='processor' and r['request']==y['request'] and r['generation']==y['generation']]
  rng_a=[(r.get('seed'),r.get('seed_current'),r.get('rng_before'),r.get('rng_after')) for r in processors_a if r['name']=='dist'];rng_b=[(r.get('seed'),r.get('seed_current'),r.get('rng_before'),r.get('rng_after')) for r in processors_b if r['name']=='dist']
  logits.append(dict(call=x['call'],request=x['request'],generation=x['generation'],seq=x['seq'],pos=x['pos'],same_computation_inputs_through_call=all(all(r[k] for k in ['batch_and_all_sequence_history_equal','physical_ubatches_equal','graph_worker_profile_equal']) for r in through),vocab_size=len(av),all_finite=finite,max_absolute_difference=max(delta),max_abs_token=maxidx,max_abs_values=[av[maxidx],bv[maxidx]],mean_absolute_difference=sum(delta)/len(delta),rms_difference=math.sqrt(sum(v*v for v in delta)/len(delta)),max_symmetric_relative_difference=max(d/max(abs(u),abs(v),floor) for d,u,v in zip(delta,av,bv)),relative_denominator_rule='max(abs(a),abs(b),0.001); relative maxima near zero need absolute-error context',argmax=[ra[0],rb[0]],top1_top2_margin=[av[ra[0]]-av[ra[1]],bv[rb[0]]-bv[rb[1]]],sampler_tokens=[x['sampler_token'],y['sampler_token']],rng_states_equal=rng_a==rng_b and bool(rng_a),processor_sequence_equal=[r['name'] for r in processors_a]==[r['name'] for r in processors_b],top_candidates=[dict(token=i,a=av[i],b=bv[i],difference=bv[i]-av[i]) for i in union],a_file=str(a/x['raw_logits_file']),b_file=str(b/y['raw_logits_file']),a_sha256=hashlib.sha256(data(a/x['raw_logits_file'])).hexdigest(),b_sha256=hashlib.sha256(data(b/y['raw_logits_file'])).hexdigest()))
 out=dict(a=a_name,b=b_name,sampling_schedule_equal=True,first_sample_token_difference=None if first is None else dict(call=first[0]['call'],request=first[0]['request'],generation=first[0]['generation'],seq=first[0]['seq'],pos=first[0]['pos'],tokens=[first[0]['sampler_token'],first[1]['sampler_token']]),call_comparison=equality,logits=logits,limitation='Same logical KV history and bounds, not assertion that numeric K/V values remain equal after differing arithmetic.')
 
 for row in logits:
  if 'a_sha256' in row:row['byte_equal']=row['a_sha256']==row['b_sha256']
 path=(output_dir or D/'evidence')/f'compare-{a_name}--{b_name}.json';path.write_text(json.dumps(out,indent=2)+'\n');return out
if __name__=='__main__':
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
 (D/'evidence/R-numeric-summary.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(dict(status=result['status'],cohorts=[dict(cohort=r['cohort'],status=r['status'],maxabs=[x.get('max_absolute_difference') for x in r['logits']],byte_equal=[x.get('byte_equal') for x in r['logits']]) for r in reports]),indent=2))
