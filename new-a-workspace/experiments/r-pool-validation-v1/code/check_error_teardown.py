from pathlib import Path
import copy,datetime,fcntl,json,os,signal,subprocess
from run_r_gate import D,W,read,save,event,preflight
preflight()
with (W/'state/.measurement.lock').open('r') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 for arm in ['A','P']:
  assert read(D/'results'/f'lifecycle-{arm}-observer-v2'/'lifecycle-summary.json')['status']=='PASS'
  folder=D/'results'/f'load-error-{arm}';folder.mkdir(exist_ok=False);case=copy.deepcopy(read(D/'cases-AP.json')[arm]);missing=folder/'deliberately-missing-model.gguf';assert not missing.exists()
  argv=case['server_argv'];argv[argv.index('-m')+1]=str(missing);argv[argv.index('--port')+1]='0'
  save(folder/'launch.json',dict(argv=argv,environment=case['server_env'],scope='Supported model-file-not-found error cleanup only; no alternative model and no generation'))
  with (folder/'stdout.log').open('w') as so,(folder/'stderr.log').open('w') as se:
   proc=subprocess.Popen(['/usr/bin/taskset','-c','0,2,4,6,8,10',*argv],env=case['server_env'],stdout=so,stderr=se,start_new_session=True)
   try:proc.wait(timeout=30)
   except BaseException:
    if proc.poll() is None:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
    raise
  text=(folder/'stderr.log').read_text();assert proc.returncode==1 and 'exiting due to model loading error' in text and 'cleaning up before exit' in text
  result=dict(status='PASS',returncode=proc.returncode,owned_pid=proc.pid,owned_process_gone=not Path(f'/proc/{proc.pid}').exists(),no_generation=True,limitation='Pre-model-allocation failure only; real loaded-model exception/recovery and pool destruction are covered separately by lifecycle diagnostics')
  assert result['owned_process_gone'];save(folder/'result.json',result);event(dict(stage=arm+'-load-error-cleanup',**result));print(arm,'load error cleanup PASS',flush=True)
