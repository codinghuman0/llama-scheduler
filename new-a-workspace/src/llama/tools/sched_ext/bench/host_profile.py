# SPDX-License-Identifier: GPL-2.0
"""Generate a host identity once; campaigns retain and verify its exact bytes."""
import argparse
import datetime
import gzip
import json
import os
from pathlib import Path
import platform
import pwd
import re
import subprocess
import tempfile

from common import BENCH, BOOT_ID, MODEL_SHA, REPO, SCHED, require, sha, write_json

DEFAULT_PROFILE = REPO / 'benchmark-results/host-profile.json'
ARTIFACTS = ('llama_scx.bpf.o', 'bin/llama_scx', 'bin/llama_scx_child')


def read_optional(path):
    path = Path(path)
    return path.read_text().strip() if path.exists() else None


def discover_topology(allowed=None):
    with tempfile.TemporaryDirectory() as temp:
        output = Path(temp) / 'topology.json'
        result = subprocess.run([str(BENCH / 'detect_host_topology.sh'), '--json', str(output)],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                preexec_fn=(lambda: os.sched_setaffinity(0, allowed)) if allowed else None)
        require(result.returncode == 0, 'BLOCKED: topology detection failed: ' + result.stderr)
        return json.loads(output.read_text())


def allocation(topology):
    selected = topology['physical_core_representatives']
    enough = len(selected) >= 2
    server, house = (selected[:-1], selected[-1:]) if enough else ([], [])
    return dict(status='PASS' if enough else 'BLOCKED',
                reason=None if enough else 'Isolated benchmark requires at least two usable physical cores; setup/smoke may still run',
                server_cpus=server, housekeeping_cpus=house,
                compute_threads=len(server), batch_threads=len(server), http_threads=2)


def capabilities(*, cpu=Path('/sys/devices/system/cpu'), hwmon_root=Path('/sys/class/hwmon'), power_root=Path('/sys/class/power_supply')):
    fields = ('affected_cpus', 'related_cpus', 'scaling_driver', 'scaling_governor',
              'scaling_available_governors', 'scaling_min_freq', 'scaling_max_freq',
              'cpuinfo_min_freq', 'cpuinfo_max_freq', 'scaling_cur_freq', 'bios_limit',
              'energy_performance_preference')
    policies = {p.name: {k: read_optional(p / k) for k in fields} for p in sorted((cpu / 'cpufreq').glob('policy*'))}
    turbo = {str(p): p.read_text().strip() for p in
             (cpu / 'cpufreq/boost', cpu / 'intel_pstate/no_turbo', cpu / 'intel_pstate/status',
              cpu / 'intel_pstate/min_perf_pct', cpu / 'intel_pstate/max_perf_pct', cpu / 'intel_pstate/hwp_dynamic_boost') if p.exists()}
    for policy in sorted((cpu / 'cpufreq').glob('policy*')):
        if (policy / 'boost').exists():
            turbo[str(policy / 'boost')] = (policy / 'boost').read_text().strip()
    candidates = []
    for hwmon in sorted(hwmon_root.glob('hwmon*')):
        name = read_optional(hwmon / 'name')
        for label in sorted(hwmon.glob('temp*_label')):
            value = label.read_text().strip()
            if (name == 'k10temp' and value == 'Tctl') or (name == 'coretemp' and re.fullmatch(r'Package id \d+', value)):
                sensor = label.with_name(label.name.replace('_label', '_input'))
                if sensor.exists():
                    candidates.append(dict(name=name, label=value, input=str(sensor.resolve()), device=str((hwmon / 'device').resolve())))
    sensor = sorted(candidates, key=lambda s: (s['name'], s['label'], s['device']))[0] if candidates else 'unavailable'
    temperature = int(Path(sensor['input']).read_text()) / 1000 if candidates else None
    supplies = {}
    for p in sorted(power_root.glob('*')):
        kind = read_optional(p / 'type')
        if kind in {'Mains', 'USB', 'USB_C', 'USB_PD', 'USB_PD_DRP', 'Wireless', 'UPS', 'Battery'} or (p / 'online').exists():
            supplies[p.name] = {k: read_optional(p / k) for k in ('type', 'online', 'status', 'present')}
    return dict(frequency=dict(available=bool(policies), policies=policies),
                turbo=dict(available=bool(turbo), interfaces=turbo), temperature_sensor=sensor, temperature_c=temperature,
                power_supply=dict(available=bool(supplies), entries=supplies))


def execution_state(value):
    power = value['power_supply']
    entries = {name: {k: supply[k] for k in ('type', 'present', 'online')
                      if k in supply and (k != 'online' or supply.get('type') != 'Battery')}
               for name, supply in power['entries'].items()}
    return {k: value[k] for k in ('turbo', 'temperature_sensor')} | {
        'power_supply': dict(available=power['available'], entries=entries),
        'frequency': dict(available=value['frequency']['available'], policies={p: {k: v for k, v in fields.items() if k != 'scaling_cur_freq'}
                                                                           for p, fields in value['frequency']['policies'].items()})}


def kernel_identity():
    require(platform.system() == 'Linux' and platform.machine() == 'x86_64', 'BLOCKED: Linux x86_64 required')
    require(Path('/sys/kernel/sched_ext/state').is_file(), 'BLOCKED: kernel sched_ext interface missing')
    btf = Path('/sys/kernel/btf/vmlinux')
    require(btf.is_file(), 'BLOCKED: kernel BTF missing')
    config_path = Path('/boot') / ('config-' + platform.release())
    config = config_path.read_text() if config_path.exists() else None
    if config is None and Path('/proc/config.gz').exists():
        config_path = Path('/proc/config.gz')
        with gzip.open(config_path, 'rt') as stream:
            config = stream.read()
    required = ('CONFIG_BPF', 'CONFIG_BPF_SYSCALL', 'CONFIG_SCHED_CLASS_EXT', 'CONFIG_DEBUG_INFO_BTF')
    if config is not None:
        require(all(re.search(r'^' + k + '=y$', config, re.M) for k in required), 'BLOCKED: required BPF/sched_ext kernel configuration missing')
    return dict(kernel=platform.release(), boot_id=BOOT_ID.read_text().strip(), architecture=platform.machine(),
                btf=dict(path=str(btf), size=btf.stat().st_size, sha256=sha(btf)),
                kernel_config=dict(path=str(config_path) if config is not None else 'unavailable',
                                   required={k: 'y' for k in required} if config is not None else 'unavailable'))


def artifact_identity():
    hashes = {name: sha(SCHED / name) for name in ARTIFACTS}
    loader = (SCHED / 'bin/llama_scx').read_bytes()
    paths = {s[:-1].decode() for s in re.findall(rb'/[^\x00]+/llama_scx\.bpf\.o\x00', loader)}
    expected = str(SCHED / 'llama_scx.bpf.o')
    require(paths == {expected}, 'BLOCKED: loader embedded BPF path differs from active repository: ' + repr(paths))
    return dict(hashes=hashes, bpf_object_path=expected)


def generate(model):
    owner = REPO.stat().st_uid
    require(owner != 0 and os.getuid() == owner, 'Generate the profile as the invoking non-root repository owner')
    user = pwd.getpwuid(owner)
    model = Path(model).expanduser().resolve()
    require(model.is_file() and model.stat().st_size == 1117321312 and sha(model) == MODEL_SHA, 'BLOCKED: model identity mismatch')
    topology = discover_topology()
    return dict(schema=1, generated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(), repository_root=str(REPO),
                uid=owner, username=user.pw_name, home=str(Path.home()), model=dict(path=str(model), size=model.stat().st_size, sha256=MODEL_SHA),
                host=kernel_identity(), topology=topology, allocation=allocation(topology), capabilities=capabilities(), scheduler=artifact_identity())


def load(path):
    path = Path(path)
    value = json.loads(path.read_text())
    require(value['schema'] == 1 and value['repository_root'] == str(REPO), 'Host profile schema/repository differs')
    require(value['uid'] == REPO.stat().st_uid and value['uid'] != 0, 'Host profile owner differs')
    user = pwd.getpwuid(value['uid'])
    require(value['username'] == user.pw_name and Path(value['home']).is_absolute(), 'Host profile user identity differs')
    require(value['model']['size'] == 1117321312 and value['model']['sha256'] == MODEL_SHA, 'Host profile model identity differs')
    require(value['allocation'] == allocation(value['topology']), 'Host profile CPU allocation differs from detector rules')
    require(set(value['scheduler']['hashes']) == set(ARTIFACTS) and all(re.fullmatch('[0-9a-f]{64}', h) for h in value['scheduler']['hashes'].values()), 'Incomplete scheduler identity')
    require(value['scheduler']['bpf_object_path'] == str(SCHED / 'llama_scx.bpf.o'), 'Profile BPF path differs')
    require(path.stat().st_uid == value['uid'] and not path.stat().st_mode & 0o022, 'Host profile ownership/mode differs')
    return value


def validate_current(value, *, initial_affinity=False):
    model = Path(value['model']['path'])
    require(model.is_file() and model.stat().st_size == value['model']['size'] and sha(model) == value['model']['sha256'], 'Frozen model identity changed')
    require(kernel_identity() == value['host'], 'Host kernel/boot/BTF changed; refresh profile before a new campaign')
    if initial_affinity:
        require(sorted(os.sched_getaffinity(0)) == value['topology']['allowed_cpus'], 'Invoking allowed CPU set differs; regenerate profile in the intended environment')
    require(discover_topology(value['topology']['allowed_cpus']) == value['topology'], 'Host topology changed')
    require(execution_state(capabilities()) == execution_state(value['capabilities']), 'Host frequency/thermal/power capability or configuration changed')
    require(artifact_identity() == value['scheduler'], 'Scheduler artifact identity changed')


def require_refreshable():
    pointer = REPO / 'benchmark-results/step10/.active-run'
    if pointer.exists():
        from common import active_run, read_json
        require(read_json(active_run() / 'manifest.json')['status'] in {'FAILED', 'FINALIZED', 'SUPERSEDED'}, 'Profile is frozen by a prepared/active campaign')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', default=os.environ.get('MODEL', str(REPO.parent / 'model.gguf')))
    parser.add_argument('--output', type=Path, default=DEFAULT_PROFILE)
    parser.add_argument('--refresh', action='store_true', help='Replace the profile only outside a prepared/active campaign')
    parser.add_argument('--check', action='store_true', help='Validate an existing profile without changing it')
    args = parser.parse_args()
    if args.check:
        value = load(args.output)
        validate_current(value, initial_affinity=True)
    else:
        require_refreshable()
        require(not args.output.exists() or args.refresh, 'Profile exists; use --check or --refresh before a new campaign')
        value = generate(args.model)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        write_json(args.output, value)
        args.output.chmod(0o444)
    print(json.dumps(dict(result='PASS', profile=str(args.output), sha256=sha(args.output), allocation=value['allocation'],
                          temperature_sensor=value['capabilities']['temperature_sensor']), indent=2))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        raise SystemExit('HOST_PROFILE_RESULT=BLOCKED: ' + str(error))
