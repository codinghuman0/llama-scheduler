# SPDX-License-Identifier: GPL-2.0
"""Checkpoints run outside requests; there is no background observer."""
import math
import os
from pathlib import Path
import re
import signal
import time

from common import BOOT_ID, HOST, UID, command, identity, require, same_process, signal_exact, topology, write_json


def snapshot():
    import host_profile
    capabilities = host_profile.capabilities()
    memory = {k: int(v) for k, v in re.findall(r'^(MemAvailable|SwapTotal|SwapFree):\s+(\d+)', Path('/proc/meminfo').read_text(), re.M)}
    return dict(kernel=os.uname().release, boot_id=BOOT_ID.read_text().strip(), topology=topology(),
                **capabilities, loadavg=list(os.getloadavg()), memory_kib=memory,
                runner_affinity=sorted(os.sched_getaffinity(0)), monotonic_ns=time.monotonic_ns())


def invariants(value):
    import host_profile
    return {key: value[key] for key in ('kernel', 'boot_id', 'topology')} | host_profile.execution_state(value)


def validate(value, baseline=None):
    sensor = value['temperature_sensor']
    require((sensor == 'unavailable' and value['temperature_c'] is None) or
            (isinstance(sensor, dict) and isinstance(value['temperature_c'], (int, float)) and math.isfinite(value['temperature_c'])), 'Temperature capability/value differs')
    if baseline:
        require(invariants(value) == invariants(baseline), 'Machine configuration changed during campaign')
    elif HOST:
        import host_profile
        require(value['kernel'] == HOST['host']['kernel'] and value['boot_id'] == HOST['host']['boot_id']
                and value['topology'] == HOST['topology']
                and host_profile.execution_state(value) == host_profile.execution_state(HOST['capabilities']), 'Machine differs from frozen host profile')


def thermal_ready(samples):
    if samples[0]['temperature_sensor'] == 'unavailable':
        return all(s['temperature_c'] is None and s['loadavg'][0] <= 1 for s in samples)
    temperatures = [s['temperature_c'] for s in samples]
    return max(temperatures) <= 55 and max(temperatures) - min(temperatures) <= 2


def counters():
    values = list(map(int, Path('/proc/stat').read_text().splitlines()[0].split()[1:9]))
    return sum(values), values[3] + values[4]


def busy(before, after):
    total = after[0] - before[0]
    require(total > 0, 'CPU counter observation invalid')
    return 100 * (1 - (after[1] - before[1]) / total)


def interactive_apps():
    rows = command(['ps', '-eo', 'pid=,comm=,pcpu=,args=']).splitlines()
    offenders = []
    for row in rows:
        fields = row.strip().split(None, 3)
        if len(fields) < 4 or int(fields[0]) == os.getpid():
            continue
        comm, _cpu, argv = fields[1:]
        comm = comm.lower()
        if comm.startswith(('firefox', 'codex')) or comm in {'stress-ng', 'perf', 'cmake', 'make', 'ninja', 'cc1', 'cc1plus', 'wget', 'curl'} or (comm in {'node', 'electron'} and re.search(r'(^|[/ .-])codex([/ .-]|$)', argv, re.I)):
            offenders.append(row.strip())
    return rows, offenders


def reject_interactive_apps():
    rows, offenders = interactive_apps()
    require(not offenders, 'Close interactive/benchmark applications first: ' + '; '.join(offenders) +
            '\nClosing the Codex window can leave managed daemons running. Exit all Codex CLI/UI sessions, then run '
            './tools/sched_ext/bench/step10_phase_a_prepare.sh --stop-codex-daemons '
            'from your terminal. This command only stops verified user-owned managed daemons; it does not benchmark.')
    return rows


def managed_codex_daemon(argv):
    if not argv:
        return False
    import common
    root = common.USER_HOME / '.codex/packages/app-server-daemon/releases'
    executable = Path(argv[0])
    if (not executable.is_relative_to(root) or executable.parent.name != 'bin'
            or executable.parent.parent.parent != root or executable.parent.parent.name in {'.', '..'}):
        return False
    return ((executable.name == 'codex' and argv[1:] in
             (['app-server', '--listen', 'unix://', '--managed-daemon'], ['app-server', 'daemon', 'pid-update-loop']))
            or (executable.name == 'codex-code-mode-host' and len(argv) == 1))


def stop_codex_daemons():
    require(os.getuid() == UID and UID != 0, 'Only the selected normal user may stop their managed daemons')
    _, offenders = interactive_apps()
    targets, other = [], []
    for row in offenders:
        pid = int(row.split(None, 1)[0])
        try:
            argv = Path(f'/proc/{pid}/cmdline').read_bytes().decode().rstrip('\0').split('\0')
            saved = identity(pid)
        except (FileNotFoundError, ProcessLookupError):
            continue
        if saved['uids'] == [UID] * 4 and managed_codex_daemon(argv):
            targets.append((saved, argv))
        else:
            other.append(row)
    require(not other, 'Exit interactive applications/CLI sessions before stopping managed daemons: ' + '; '.join(other))
    # Recheck the complete set before signaling any process.
    for saved, argv in targets:
        require(same_process(saved) and Path(f"/proc/{saved['pid']}/cmdline").read_bytes().decode().rstrip('\0').split('\0') == argv,
                'Daemon identity changed; refusing signal')
    for saved, _ in reversed(targets):
        if same_process(saved):
            try:
                signal_exact(saved, signal.SIGTERM)
            except ProcessLookupError:
                pass
    deadline = time.monotonic() + 15
    while any(same_process(saved) for saved, _ in targets) and time.monotonic() < deadline:
        time.sleep(0.1)
    require(not any(same_process(saved) for saved, _ in targets), 'Managed daemon did not exit; no forced kill was sent')
    reject_interactive_apps()
    return [saved for saved, _ in targets]


def readiness(run, name, baseline, *, after_warmup):
    deadline = time.monotonic() + 180
    readings = []
    while time.monotonic() < deadline:
        first, sample1 = counters(), snapshot()
        validate(sample1, baseline)
        time.sleep(5)
        second, sample2 = counters(), snapshot()
        validate(sample2, baseline)
        record = dict(first=sample1, second=sample2, busy_pct=busy(first, second))
        if after_warmup:
            time.sleep(5)
            third, sample3 = counters(), snapshot()
            validate(sample3, baseline)
            record.update(third=sample3, second_busy_pct=busy(second, third))
            ready = thermal_ready((sample1, sample2, sample3)) and max(record['busy_pct'], record['second_busy_pct']) <= 5
        else:
            ready = sample2['loadavg'][0] <= 1 and record['busy_pct'] <= 5
        record['ready'] = ready
        readings.append(record)
        write_json(run / name, readings)
        if ready:
            return
    raise RuntimeError('Readiness/cooldown did not settle within 180 seconds')


def validate_readiness(readings, baseline, *, after_warmup):
    require(isinstance(readings, list) and readings and readings[-1]['ready'] is True, 'Readiness evidence missing or did not pass')
    record = readings[-1]
    names = ('first', 'second', 'third') if after_warmup else ('first', 'second')
    for name in names:
        validate(record[name], baseline)
    require(0 <= record['busy_pct'] <= 5, 'Saved readiness CPU busy exceeds protocol')
    if after_warmup:
        require(thermal_ready([record[name] for name in names])
                and 0 <= record['second_busy_pct'] <= 5, 'Saved cooldown exceeds protocol')
    else:
        require(record['second']['loadavg'][0] <= 1, 'Saved block load exceeds protocol')
