#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""Deliver a bounded CPU-time demand on one explicitly selected CPU."""
import argparse
import ctypes
import json
import os
import signal
import time


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cpu',type=int,required=True)
    parser.add_argument('--parent',type=int,required=True)
    parser.add_argument('--seconds',type=float,default=180)
    args=parser.parse_args()
    if not 1<=args.seconds<=600: raise ValueError('Bound the load to 1-600 seconds')
    libc=ctypes.CDLL(None,use_errno=True)
    if libc.prctl(1,signal.SIGTERM,0,0,0)!=0 or os.getppid()!=args.parent:
        raise RuntimeError('Cannot establish parent-death cleanup')
    if libc.prctl(15,ctypes.c_char_p(b'newa-load'),0,0,0)!=0:
        raise RuntimeError('Cannot set load identity')
    os.sched_setaffinity(0,{args.cpu})
    if os.sched_getscheduler(0)!=os.SCHED_OTHER: raise RuntimeError('Load must use the normal Linux policy')
    stopping=False
    def stop(signum,frame):
        nonlocal stopping
        stopping=True
    signal.signal(signal.SIGTERM,stop)
    signal.signal(signal.SIGINT,stop)
    started=time.monotonic_ns();cpu_started=time.process_time_ns()
    period_ns=50_000_000;budget_ns=12_500_000
    next_period=started;periods=late=0;value=1
    print(json.dumps(dict(status='READY',pid=os.getpid(),cpu=args.cpu,policy=0,
                          period_ns=period_ns,cpu_budget_ns=budget_ns,started_ns=started)),flush=True)
    while not stopping and time.monotonic_ns()-started<int(args.seconds*1e9):
        target=time.process_time_ns()+budget_ns
        while not stopping and time.process_time_ns()<target:
            for _ in range(256): value=(value*1664525+1013904223)&0xffffffff
        periods+=1;next_period+=period_ns
        remaining=next_period-time.monotonic_ns()
        if remaining>0: time.sleep(remaining/1e9)
        else:
            late+=1
            next_period=time.monotonic_ns()
    print(json.dumps(dict(status='STOPPED',elapsed_ns=time.monotonic_ns()-started,
                          cpu_ns=time.process_time_ns()-cpu_started,periods=periods,late_periods=late,checksum=value)),flush=True)


if __name__=='__main__':
    main()
