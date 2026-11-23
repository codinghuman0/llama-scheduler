"""Separate arithmetic path: rebuild each gain and stratified interval from raw files."""
import argparse,json,math,random
from common import *
def run(name):
 root=D/'results'/name;summary=read(root/'analysis.json');out=[]
 for cell in summary['cells']:
  strata={f:[] for f in ['heldout-1','heldout-2']}
  for block in range(1,9):
   records={}
   for arm in ['B0','A']:
    folder=root/f'campaign-{cell["campaign"]}'/f'{cell["condition"]}-b{block:02}-{arm}'
    if not (folder/'result.json').exists():continue
    obs=read(folder/'http-observations.json')[1];rows=read(folder/'measured-http-raw.json')
    records[arm]=(sum(map(lambda x:len(x['tokens']),rows))*1e9/(obs['end_ns']-obs['start_ns']))
   if len(records)!=2:continue
   gain=100*(records['A']/records['B0']-1);fid='heldout-1' if block%2 else 'heldout-2';strata[fid].append(gain)
   ref=next(p for p in cell['pairs'] if p['block']==block)
   assert abs(gain-ref['gain_pct'])<1e-10
  if not cell['valid']:out.append(dict(campaign=cell['campaign'],condition=cell['condition'],status='INCOMPLETE'));continue
  rng=random.Random(20261122);boot=[]
  for _ in range(10000):
   sampled=[]
   for values in strata.values():
    sampled.extend(rng.choices(values,k=4))
   boot.append(sum(sampled)/8)
  boot.sort();ci=[]
  for p in [.025,.975]:
   pos=9999*p;j=math.floor(pos);ci.append(boot[j]*(1-(pos-j))+boot[min(j+1,9999)]*(pos-j))
  gain=sum(sum(s) for s in strata.values())/8
  assert abs(gain-cell['mean_paired_gain_pct'])<1e-10
  assert all(abs(a-b)<1e-10 for a,b in zip(ci,cell['paired_stratified_bootstrap_95_pct']))
  out.append(dict(campaign=cell['campaign'],condition=cell['condition'],status='PASS',mean_gain_pct=gain,CI95=ci))
 result=dict(status='PASS' if all(x['status']=='PASS' for x in out) else 'INCOMPLETE',source='raw measured HTTP token arrays and monotonic brackets, separate arithmetic implementation',cells=out)
 save(root/'independent-recalculation.json',result);print(json.dumps(result,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--name',required=True);run(p.parse_args().name)
