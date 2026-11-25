# SPDX-License-Identifier: GPL-2.0
"""Read-only topology extension of the unchanged Portable detector."""
import importlib.util
import hashlib
from pathlib import Path
import platform
import re
import subprocess

HERE = Path(__file__).resolve().parent
PORTABLE = HERE.parent / 'new_a_portable'
spec = importlib.util.spec_from_file_location('hybrid_existing_portable_topology', PORTABLE / 'topology.py')
portable = importlib.util.module_from_spec(spec)
spec.loader.exec_module(portable)
require = portable.require
Unsupported = portable.Unsupported


def optional(path):
    try:
        return Path(path).read_text().strip()
    except (FileNotFoundError, PermissionError, OSError):
        return None


def cgroup_constraints(cgroup=Path('/proc/self/cgroup'), mountinfo=Path('/proc/self/mountinfo')):
    result = dict(version='NOT_VERIFIED', cpuset_cpus_effective=None, cpuset_mems_effective=None,
                  cpu_max=None, scope='VISIBLE_CURRENT_CGROUP;_ANCESTOR_QUOTAS_MAY_BE_STRICTER',
                  effective_cpu_authority='SCHED_GETAFFINITY_INTERSECT_ONLINE', paths_redacted=True)
    memberships = optional(cgroup)
    mounts = optional(mountinfo)
    if memberships is None or mounts is None:
        return result
    unescape = lambda s: re.sub(r'\\([0-7]{3})', lambda m: chr(int(m[1], 8)), s)
    for line in memberships.splitlines():
        parts = line.split(':', 2)
        if len(parts) != 3:
            continue
        controllers, member = parts[1:]
        version = 'v2' if not controllers else 'v1' if 'cpuset' in controllers.split(',') else None
        if version is None or '..' in Path(member).parts:
            continue
        for mount in mounts.splitlines():
            left, sep, right = mount.partition(' - ')
            fields, fs = left.split(), right.split()
            if not sep or len(fields) < 6 or len(fs) < 3:
                continue
            if fs[0] != ('cgroup2' if version == 'v2' else 'cgroup'):
                continue
            if version == 'v1' and 'cpuset' not in fs[2].split(','):
                continue
            root, point = Path(unescape(fields[3])), Path(unescape(fields[4]))
            if Path(member).is_relative_to(root):
                relative = Path(member).relative_to(root)
            elif member == '/':
                relative = Path('.')
            else:
                continue
            location = point / relative
            if not location.is_dir() or not location.resolve().is_relative_to(point.resolve()):
                continue
            cpus = optional(location / ('cpuset.cpus.effective' if version == 'v2' else 'cpuset.effective_cpus'))
            mems = optional(location / ('cpuset.mems.effective' if version == 'v2' else 'cpuset.effective_mems'))
            if version == 'v1' and cpus is None:
                # Empty v1 masks can inherit an ancestor's restriction.
                parent = location
                while parent.is_relative_to(point):
                    cpus = optional(parent / 'cpuset.cpus')
                    if cpus:
                        break
                    if parent == point:
                        break
                    parent = parent.parent
            result.update(version=version,
                          cpuset_cpus_effective=portable.cpulist(cpus) if cpus else None,
                          cpuset_mems_effective=portable.cpulist(mems) if mems else None,
                          cpu_max=optional(location / 'cpu.max') if version == 'v2' else None)
            return result
    return result


def extras(snapshot, cpu_root=Path('/sys/devices/system/cpu'), constraints=None):
    rows = {}
    for cpu in snapshot['online_cpus']:
        path = Path(cpu_root) / ('cpu' + str(cpu))
        caches = []
        for index in sorted((path / 'cache').glob('index*')):
            level, kind, shared = (optional(index / x) for x in ['level', 'type', 'shared_cpu_list'])
            if level not in ['2', '3']:
                continue
            if kind not in ['Unified', 'Data', 'Instruction'] or not shared:
                raise Unsupported('L2/L3 캐시 토폴로지 정보가 누락됐습니다.')
            members = portable.cpulist(shared)
            require(cpu in members and set(members) <= set(snapshot['possible_cpus']), '캐시를 공유하는 CPU 목록이 일치하지 않습니다.')
            caches.append(dict(level=int(level), type=kind, shared_cpus=members,
                               id=optional(index / 'id'), size=optional(index / 'size')))
        nodes = sorted(int(x.name[4:]) for x in path.glob('node[0-9]*') if x.name[4:].isdigit())
        require(len(nodes) <= 1, '한 CPU가 여러 NUMA 노드에 속해 있습니다.')
        rows[str(cpu)] = dict(caches=caches, numa_node=nodes[0] if nodes else None,
                             cpuinfo_max_freq_khz=optional(path / 'cpufreq/cpuinfo_max_freq'),
                             base_frequency_khz=optional(path / 'cpufreq/base_frequency'))
    constraints = cgroup_constraints() if constraints is None else constraints
    effective = constraints['cpuset_cpus_effective']
    require(effective is None or set(snapshot['usable_cpus']) <= set(effective), 'CPUID 검사 범위와 현재 cpuset이 일치하지 않습니다.')
    # Check every visible member, including allowed-out SMT siblings.
    for cpu, info in rows.items():
        for cache in info['caches']:
            for other in set(cache['shared_cpus']) & set(snapshot['online_cpus']):
                matching = [x for x in rows[str(other)]['caches'] if x['level'] == cache['level'] and x['type'] == cache['type']]
                require(any(x['shared_cpus'] == cache['shared_cpus'] for x in matching), 'CPU 간 캐시 공유 정보가 서로 일치하지 않습니다.')
    return dict(cpus=rows, cgroup=constraints, smt_control=optional(Path(cpu_root) / 'smt/control'), smt_active=optional(Path(cpu_root) / 'smt/active'))


def inspect(probe, requested=None):
    require(platform.system() == 'Linux' and platform.machine() == 'x86_64', 'x86-64 Linux가 필요합니다.')
    from build_probe import verify_probe
    binary_sha = verify_probe(probe)
    before = portable.snapshot(requested=requested)
    extra_before = extras(before)
    evidence = portable.probe(before, probe)
    after = portable.snapshot(requested=requested)
    require(before == after and extra_before == extras(after), '감지하는 동안 토폴로지·CPU 범위·캐시 또는 cgroup이 바뀌었습니다. 장비 상태를 확인하세요.')
    return detection(before, evidence, extra_before, probe_sha256=binary_sha, requested=requested)


def detection(snapshot, evidence, extra, *, probe_sha256='SYNTHETIC_NOT_HARDWARE', requested=None):
    require(set(extra['cpus']) == set(snapshot['cpus']), '캐시 또는 NUMA 정보가 누락됐습니다.')
    effective = extra['cgroup']['cpuset_cpus_effective']
    require(effective is None or set(snapshot['usable_cpus']) <= set(effective), '선택한 CPU가 허용 cpuset 밖에 있습니다.')
    plan = portable.plan(snapshot, evidence)
    online_cores = {(x['package'], x['die'], x['core']) for x in snapshot['cpus'].values()}
    summary = dict(cpu_model=plan['cpu_model'], vendor=plan['vendor'], architecture=plan['architecture'],
        logical_present=len(snapshot['present_cpus']), logical_online=len(snapshot['online_cpus']), logical_usable=len(snapshot['usable_cpus']),
        physical_cores_online=len(online_cores), physical_cores_present=len(online_cores) if snapshot['present_cpus'] == snapshot['online_cpus'] else None,
        available_physical_cores=plan['usable_physical_cores'], available_p_cores=plan['physical_p_cores'], available_e_cores=plan['physical_e_cores'],
        all_online_cpu_types_probed=snapshot['usable_cpus'] == snapshot['online_cpus'],
        online_core_type_scope='Unallowed CPUs are not probed; total installed P/E counts may be unavailable')
    return dict(schema=1, status='CONFIGURATION_DETECTION_ONLY', summary=summary, requested_cpus=requested,
                portable_plan=plan, hardware=extra, probe_sha256=probe_sha256,
                fingerprint=portable.fingerprint(dict(snapshot=snapshot, cpuid=evidence, extra=extra, probe=probe_sha256)),
                execution_admitted=False, performance_validated=False, team_cpu_runtime='TEAM_CPU_RUNTIME_NOT_TESTED')


def environment():
    cpu = Path('/sys/devices/system/cpu')
    supplies = [{k: optional(p / k) for k in ['type', 'online', 'status', 'capacity']} for p in Path('/sys/class/power_supply').glob('*')]
    try:
        profile = subprocess.check_output(['powerprofilesctl', 'get'], text=True, stderr=subprocess.DEVNULL, timeout=5).strip()
    except (OSError, subprocess.SubprocessError):
        profile = 'NOT_VERIFIED'
    governors = {p.name: optional(p / 'scaling_governor') for p in (cpu / 'cpufreq').glob('policy*')}
    btf = Path('/sys/kernel/btf/vmlinux')
    return dict(kernel=platform.release(), btf_sha256=hashlib.sha256(btf.read_bytes()).hexdigest() if btf.exists() else None,
                ac_online=any(p['type'] == 'Mains' and p['online'] == '1' for p in supplies), power_supply=supplies,
                no_turbo=optional(cpu / 'intel_pstate/no_turbo'), boost=optional(cpu / 'cpufreq/boost'),
                power_profile=profile, governors=governors, sched_ext=optional('/sys/kernel/sched_ext/state'),
                temperature_millic=[],
                read_only=True, boot_and_host_ids='NOT_COLLECTED', host_profile='NEW_PROFILE_REQUIRED', runtime_baseline='NEW_BASELINE_REQUIRED',
                execution_admitted=False, STRICT_ACCEPTANCE='FAILED', safety_verdict='FAIL', OVERHEAD_REVIEW_REQUIRED=True)
