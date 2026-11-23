import argparse,copy,fcntl,http.client,json,os,signal,socket,time
from pathlib import Path
from run_r_gate import D,W,read,save,sha,visit,preflight,http_json,event
p=argparse.ArgumentParser();p.add_argument('arm',choices=['A','P']);p.add_argument('--revision',default='');args=p.parse_args();arm=args.arm
assert read(D/'gate-results.json')['E-R']=='COMPATIBLE_IN_TESTED_SCOPE'
assert read(D/'evidence'/f'{arm}-free-summary.json')['status']=='PASS'
preflight();folder=D/'results'/(f'lifecycle-{arm}'+('-'+args.revision if args.revision else ''));assert not folder.exists()
fixture=next(f for f in read(D/'fixtures.json') if f['id']=='h1-request3-singleton')
case=copy.deepcopy(read(D/'cases-AP.json')[arm]);case['server_argv']+=['--sleep-idle-seconds','2']
probe=D/'build-server/pool-observer.so';case['server_env'].update(LD_PRELOAD=str(probe),NEWA_POOL_DIAG_OUTPUT=str(folder/'pool-events.jsonl'),NEWA_POOL_DIAG_ROLE=str(folder/'pool-role.txt'));case['artifacts'][str(probe)]=sha(probe)
oracle=read(D/'results/free-h1-request3-singleton-B0-r1/result.json')['measured'][0]
def role(value):(folder/'pool-role.txt').write_text(value+'\n')
def extended(proc,port,output):
 checks={};payload=read(folder/'atomic-payload.json')
 def normal(name):
  role(name);body=http_json(port,'/completion',payload);save(folder/(name+'-response.json'),body)
  row=body[0] if isinstance(body,list) else body
  assert row['tokens']==oracle and row['tokens_predicted']==128 and row['timings']['cache_n']==0,name
  checks[name]=True
 def idle():
  deadline=time.monotonic()+15
  while True:
   slots=http_json(port,'/slots');assert isinstance(slots,list)
   if all(not x.get('is_processing',False) for x in slots):return slots
   assert time.monotonic()<deadline,'Cancellation did not release slots';time.sleep(.05)
 role('cancel');cancel=dict(payload,prompt=fixture['requests'][0]['prompt'],stream=True)
 conn=http.client.HTTPConnection('127.0.0.1',port,timeout=30);values=[];response=None
 try:
  conn.request('POST','/completion',json.dumps(cancel).encode(),{'Content-Type':'application/json'});response=conn.getresponse();assert response.status==200
  while sum(len(x.get('tokens',[])) for x in values)<8:
   line=response.readline();assert line,'Stream ended before cancellation'
   if line.startswith(b'data: '):values.append(json.loads(line[6:]))
  if conn.sock:conn.sock.shutdown(socket.SHUT_RDWR)
 finally:
  if response:response.close()
  conn.close()
 tokens=[t for x in values for t in x.get('tokens',[])];assert len(tokens)<128 and tokens==oracle[:len(tokens)]
 save(folder/'cancellation.json',dict(received=values,received_tokens=len(tokens),closed_before_completion=True,slots_after=idle()));checks['cancelled_before_completion']=True
 normal('after-cancel')
 role('invalid-grammar');bad=dict(payload,grammar='not a valid grammar')
 conn=http.client.HTTPConnection('127.0.0.1',port,timeout=30)
 try:
  conn.request('POST','/completion',json.dumps(bad).encode(),{'Content-Type':'application/json'});response=conn.getresponse();status=response.status;body=response.read().decode()
 finally:conn.close()
 save(folder/'invalid-grammar.json',dict(status=status,body=body));assert status==400 and 'failed to parse grammar' in body.lower();checks['safe_sampler_exception']=True
 normal('after-error')
 for cycle in [1,2]:
  role(f'sleep-{cycle}');deadline=time.monotonic()+20
  while True:
   props=http_json(port,'/props')
   if props.get('is_sleeping'):break
   assert time.monotonic()<deadline,'Sleep timeout';time.sleep(.1)
  maps=Path(f'/proc/{proc.pid}/maps').read_text();assert str(W/'models/model.gguf') not in maps,'Model still mapped during sleep'
  save(folder/f'sleep-{cycle}.json',dict(props=props,model_unmapped=True,mapped_elf=[x.split()[-1] for x in maps.splitlines() if '.so' in x]))
  normal(f'resume-{cycle}')
  assert not http_json(port,'/props')['is_sleeping']
  maps=Path(f'/proc/{proc.pid}/maps').read_text();assert str(W/'models/model.gguf') in maps
  checks[f'sleep-resume-{cycle}']=True
 return dict(status='PASS',checks=checks,normal_followup_requests=4,cancelled_streams=1,expected_error_requests=1,sleep_cycles=2)
with (W/'state/.measurement.lock').open('r') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 try:
  result=visit(case,fixture,folder,hooks=dict(role=role,after=extended,cleanup=lambda:role('teardown')))
  assert result['warmup']==result['measured']==[oracle]
  save(folder/'lifecycle-summary.json',result['extension'])
  event(dict(stage=arm+'-lifecycle',status='PASS',sleep_cycles=2,scope='Real model, cancellation, caught sampler exception, subsequent requests and normal teardown; observer not timed'))
 except BaseException as exc:
  if folder.exists():save(folder/'lifecycle-failure.json',dict(type=type(exc).__name__,message=str(exc)))
  event(dict(stage=arm+'-lifecycle',status='FAIL',error=str(exc)));raise
print(arm+' real lifecycle PASS',flush=True)
