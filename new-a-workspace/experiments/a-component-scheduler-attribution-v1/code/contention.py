#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""Own and observe one load process without changing other applications."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent


def read_process(pid):
    fields=Path('/proc/'+str(pid)+'/stat').read_text().rsplit(')',1)[1].split()
    return dict(pid=pid,starttime=int(fields[19]),cpu_ticks=int(fields[11])+int(fields[12]),
                tick_hz=os.sysconf('SC_CLK_TCK'),affinity=sorted(os.sched_getaffinity(pid)),policy=os.sched_getscheduler(pid))


class ControlledLoad:
    def __init__(self,folder,cpu):
        self.folder,self.cpu=Path(folder),cpu
        self.process=self.stream=None
        self.start=None

    def __enter__(self):
        self.folder.mkdir(parents=True,exist_ok=True)
        self.stream=(self.folder/'events.jsonl').open('x')
        command=[sys.executable,'-u','-B',str(HERE/'load.py'),'--cpu',str(self.cpu),'--parent',str(os.getpid()),'--seconds','180']
        (self.folder/'command.json').write_text(json.dumps(command)+'\n')
        self.process=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=self.stream,stderr=subprocess.STDOUT)
        try:
            deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                if self.process.poll() is not None: raise RuntimeError('Controlled load exited during startup')
                text=(self.folder/'events.jsonl').read_text()
                lines=text.splitlines()
                if '\n' in text:
                    ready=json.loads(lines[0])
                    if ready['status']!='READY': raise RuntimeError('Controlled load readiness differs')
                    self.start=read_process(self.process.pid)
                    self.snapshot()
                    (self.folder/'identity.json').write_text(json.dumps(self.start,indent=2)+'\n')
                    return self
                time.sleep(.01)
            raise RuntimeError('Controlled load readiness timeout')
        except BaseException:
            self.close()
            raise

    def snapshot(self):
        if self.process.poll() is not None: raise RuntimeError('Controlled load stopped during request')
        value=read_process(self.process.pid)
        if value['starttime']!=self.start['starttime'] or value['affinity']!=[self.cpu] or value['policy']!=0:
            raise RuntimeError('Controlled load identity, affinity or policy changed')
        return value

    def close(self):
        if self.process and self.process.poll() is None:
            value=read_process(self.process.pid)
            if self.start is not None and value['starttime']!=self.start['starttime']:
                raise RuntimeError('Refusing to signal changed load identity')
            self.process.send_signal(signal.SIGTERM)
            try: self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill();self.process.wait(timeout=5)
                raise RuntimeError('Controlled load required forced termination')
        if self.stream: self.stream.close()
        if self.process and self.process.returncode!=0: raise RuntimeError('Controlled load failed')
        if self.process:
            (self.folder/'cleanup.json').write_text(json.dumps(dict(status='PASS',returncode=self.process.returncode))+'\n')

    def __exit__(self,*error):
        self.close()


def metrics(before,after,window_s):
    for key in ['pid','starttime','tick_hz','affinity','policy']:
        if before[key]!=after[key]: raise ValueError('Load counter identity changed')
    cpu_s=(after['cpu_ticks']-before['cpu_ticks'])/before['tick_hz']
    if cpu_s<0 or window_s<=0: raise ValueError('Invalid load counter window')
    return dict(cpu_time_s=cpu_s,mean_cpu_cores=cpu_s/window_s,cpu=before['affinity'][0],
                demand='12.5ms CPU time per 50ms period',policy=before['policy'])


def install(measure):
    original_snapshot,original_visit=measure.snapshot,measure.one_visit
    active=None
    def snapshot(pid,cpus,policy):
        result=original_snapshot(pid,cpus,policy)
        if active is not None: result['controlled_load']=active.snapshot()
        return result
    def visit(root,visit,setup,request,expected_hash,baseline_controls,args):
        nonlocal active
        cpu=setup.get('contention_cpu')
        if cpu is None: return original_visit(root,visit,setup,request,expected_hash,baseline_controls,args)
        folder=root/('functional' if visit['kind']=='functional' else 'block-'+str(visit['block']))/visit['arm']
        with ControlledLoad(folder/'controlled-load',cpu) as load:
            active=load
            try:
                result=original_visit(root,visit,setup,request,expected_hash,baseline_controls,args)
                row=result[0]
                before=json.loads((folder/'counters-before.json').read_text())
                after=json.loads((folder/'counters-after.json').read_text())
                row['controlled_load']=metrics(before['controlled_load'],after['controlled_load'],row['metrics']['counter_window_s'])
                measure.save(folder/'result.json',row)
            finally: active=None
        return result
    measure.snapshot,measure.one_visit=snapshot,visit
