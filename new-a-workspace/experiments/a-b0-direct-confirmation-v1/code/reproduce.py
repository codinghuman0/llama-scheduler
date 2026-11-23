import argparse,os,subprocess,sys
from common import *
p=argparse.ArgumentParser();p.add_argument('mode',choices=['verify','analyze','smoke','full']);p.add_argument('--name');args=p.parse_args()
assert os.getuid()!=0,'Use ordinary user; sudo is neither needed nor allowed'
if args.mode=='verify':
 verify_inputs();guard();print('PASS: sealed inputs, runtime/system DSO, model and host admission')
elif args.mode=='analyze':
 assert args.name,'Supply the recorded run namespace'
 subprocess.run([sys.executable,'-B',str(D/'code/analyze.py'),'--name',args.name],check=True)
 subprocess.run([sys.executable,'-B',str(D/'code/recalculate.py'),'--name',args.name],check=True)
else:
 assert args.name,'A new --name is required; existing directories are never overwritten'
 os.execv(sys.executable,[sys.executable,'-u','-B',str(D/'code/run.py'),args.mode,'--name',args.name])
