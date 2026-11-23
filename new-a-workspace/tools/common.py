# SPDX-License-Identifier: GPL-2.0
# Existing process identity and cleanup helpers; extracted without policy changes.
import os,re,signal,json
from pathlib import Path

def require(condition, message):
    if not condition:
        raise RuntimeError(message)

def write_json(path, value):
    path = Path(path)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')
    os.replace(temp, path)

def state():
    return Path('/sys/kernel/sched_ext/state').read_text().strip()

def identity(pid):
    text = Path(f'/proc/{pid}/stat').read_text()
    fields = text[text.rfind(')') + 2:].split()
    status = Path(f'/proc/{pid}/status').read_text()
    uids = list(map(int, re.search(r'^Uid:\s+(.+)$', status, re.M).group(1).split()))
    return dict(pid=pid, starttime=fields[19], ppid=int(fields[1]), state=fields[0],
                uid=uids[0], uids=uids, policy=os.sched_getscheduler(pid),
                affinity=sorted(os.sched_getaffinity(pid)))

def same_process(saved):
    try:
        return identity(saved['pid'])['starttime'] == saved['starttime']
    except (FileNotFoundError, ProcessLookupError):
        return False

def signal_exact(saved, sig):
    fd = os.pidfd_open(saved['pid'])
    try:
        require(same_process(saved), 'PID identity changed; refusing signal')
        signal.pidfd_send_signal(fd, sig)
    finally:
        os.close(fd)
