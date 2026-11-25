# SPDX-License-Identifier: GPL-2.0
"""실제 허용 물리 코어를 검증하고 변경 없는 E의 tier ABI로 변환한다."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import subprocess

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('new_a_original_topology', HERE.parent / 'new_a/topology.py')
original = importlib.util.module_from_spec(spec)
spec.loader.exec_module(original)
MAX_CPUS = original.MAX_CPUS


class Unsupported(ValueError):
    pass


def require(value, message):
    if not value:
        raise Unsupported(message)


def cpulist(text):
    require(isinstance(text, str) and bool(text.strip()), 'CPU 목록이 비어 있습니다')
    result = set()
    for token in text.strip().split(','):
        match = re.fullmatch(r'(\d+)(?:-(\d+))?', token)
        require(match is not None, 'CPU 목록 형식이 잘못됐습니다: ' + token)
        first, last = int(match[1]), int(match[2] or match[1])
        require(0 <= first <= last < MAX_CPUS, 'CPU 번호가 지원 범위를 벗어났습니다')
        values = set(range(first, last + 1))
        require(not result & values, 'CPU 목록에 중복 번호가 있습니다')
        result.update(values)
    return sorted(result)


def ids(value, name, empty=False):
    require(isinstance(value, list) and (empty or bool(value)), name + ' 목록이 없습니다')
    require(all(type(c) is int and 0 <= c < MAX_CPUS for c in value), name + '의 CPU 번호가 지원 범위를 벗어났습니다')
    require(value == sorted(set(value)), name + ' 목록이 정렬되지 않았거나 중복됐습니다')
    return set(value)


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def optional(path):
    try:
        return Path(path).read_text().strip()
    except FileNotFoundError:
        return None


def cpuinfo(path):
    rows = {}
    for block in Path(path).read_text().strip().split('\n\n'):
        fields = dict(line.split(':', 1) for line in block.splitlines() if ':' in line)
        fields = {k.strip():v.strip() for k,v in fields.items()}
        if 'processor' in fields:
            index = int(fields['processor'])
            require(index not in rows, '/proc/cpuinfo에 중복 CPU가 있습니다')
            rows[index] = fields
    return rows


def snapshot(*, cpu_root=Path('/sys/devices/system/cpu'), proc=Path('/proc/cpuinfo'), requested=None, affinity=None):
    cpu_root = Path(cpu_root)
    get_affinity = affinity or os.sched_getaffinity
    allowed = sorted(get_affinity(0))
    possible = cpulist((cpu_root / 'possible').read_text())
    present = cpulist((cpu_root / 'present').read_text())
    online = cpulist((cpu_root / 'online').read_text())
    ids(allowed, '실제 허용 CPU')
    require(set(online) <= set(present) <= set(possible), 'online/present/possible CPU 집합이 모순됩니다')
    if requested is not None:
        ids(requested, '요청 CPU')
        require(set(requested) <= set(allowed), '요청 CPU가 실제 허용 집합 밖입니다')
    effective = allowed if requested is None else requested
    usable = sorted(set(online) & set(effective))
    require(usable, '현재 사용할 수 있는 온라인 CPU가 없습니다')
    proc_rows = cpuinfo(proc)
    cpus = {}
    for c in online:
        base = cpu_root / ('cpu' + str(c)) / 'topology'
        try:
            package = int((base / 'physical_package_id').read_text())
            core = int((base / 'core_id').read_text())
            die = optional(base / 'die_id')
            die = None if die is None or die == '-1' else int(die)
            siblings_raw = optional(base / 'thread_siblings_list')
            core_raw = optional(base / 'core_cpus_list')
            require(siblings_raw is not None or core_raw is not None, 'SMT sibling 정보가 없습니다')
            siblings = cpulist(siblings_raw if siblings_raw is not None else core_raw)
            if siblings_raw is not None and core_raw is not None:
                require(siblings == cpulist(core_raw), '두 sibling 인터페이스가 모순됩니다')
            require(package >= 0 and core >= 0 and (die is None or die >= 0), '물리 코어 ID가 유효하지 않습니다')
            info = proc_rows[c]
            require(info['vendor_id'] in ['GenuineIntel', 'AuthenticAMD'] and bool(info['model name']), 'CPU 제조사 또는 모델이 지원되지 않습니다')
            cpus[str(c)] = dict(package=package, die=die, core=core, siblings_all=siblings,
                core_type_raw=optional(base / 'core_type') or '', capacity=optional(cpu_root / ('cpu'+str(c)) / 'cpu_capacity'),
                vendor=info['vendor_id'], model_name=info['model name'], family=int(info['cpu family']), model=int(info['model']), stepping=int(info['stepping']))
        except (OSError, KeyError, ValueError) as error:
            raise Unsupported('CPU ' + str(c) + '의 topology를 확인할 수 없습니다: ' + str(error)) from error
    require(online == cpulist((cpu_root / 'online').read_text()) and allowed == sorted(get_affinity(0)), '탐지 도중 online 또는 실제 허용 CPU가 변경됐습니다')
    return dict(possible_cpus=possible, present_cpus=present, online_cpus=online, process_allowed_cpus=allowed,
                allowed_cpus=sorted(effective), usable_cpus=usable, cpus=cpus)


def probe(snapshot_value, helper):
    before = set(os.sched_getaffinity(0))
    result = subprocess.run([str(Path(helper).resolve()), *map(str, snapshot_value['usable_cpus'])], capture_output=True, text=True, timeout=30)
    require(before == set(os.sched_getaffinity(0)), '부모 프로세스 Affinity가 변경됐습니다')
    require(result.returncode == 0, 'CPU별 CPUID 확인 실패: ' + result.stderr.strip())
    try:
        value = json.loads(result.stdout)
        require(type(value['schema']) is int and value['schema'] == 1 and value['max_cpus'] == MAX_CPUS and value['affinity_restored'] is True, 'CPUID probe의 범위 또는 복원 증거가 다릅니다')
        rows = value['cpus']
        require(isinstance(rows, list) and [x['cpu'] for x in rows] == snapshot_value['usable_cpus'], 'CPUID CPU Identity가 누락/중복/불일치합니다')
        return value
    except (KeyError, TypeError, ValueError) as error:
        raise Unsupported('CPUID 결과 형식을 검증할 수 없습니다: ' + str(error)) from error


def plan(value, evidence):
    try:
        possible = ids(value['possible_cpus'], 'possible')
        present = ids(value['present_cpus'], 'present')
        online = ids(value['online_cpus'], 'online')
        process_allowed = ids(value['process_allowed_cpus'], '실제 허용')
        allowed = ids(value['allowed_cpus'], '설정 허용')
        usable = ids(value['usable_cpus'], '사용 가능')
        require(online <= present <= possible and allowed <= process_allowed <= possible and usable == online & allowed, 'CPU 집합의 교차 관계가 모순됩니다')
        require(set(value['cpus']) == {str(c) for c in online}, '온라인 CPU topology 기록이 누락됐습니다')
        groups = {}
        for c in sorted(online):
            info = value['cpus'][str(c)]
            require(all(type(info[k]) is int and info[k] >= 0 for k in ['package','core']), 'package/core ID가 유효하지 않습니다')
            require(info['die'] is None or type(info['die']) is int and info['die'] >= 0, 'die ID가 유효하지 않습니다')
            siblings = ids(info['siblings_all'], 'sibling')
            require(c in siblings and siblings <= possible, 'sibling 범위가 모순됩니다')
            groups.setdefault((info['package'], info['die'], info['core']), []).append(c)
        sibling_owner = {}
        for key, group in groups.items():
            sibling_sets = [set(value['cpus'][str(c)]['siblings_all']) for c in group]
            require(all(s == sibling_sets[0] and s & online == set(group) for s in sibling_sets), '물리 코어 ID와 상호 sibling 관계가 모순됩니다')
            for sibling in sibling_sets[0]:
                require(sibling not in sibling_owner, '한 sibling이 서로 다른 물리 코어에 속합니다')
                sibling_owner[sibling] = key
        require(type(evidence['schema']) is int and evidence['schema'] == 1 and evidence['max_cpus'] == MAX_CPUS and evidence['affinity_restored'] is True, 'CPUID 범위/복원 증거가 잘못됐습니다')
        rows = evidence['cpus']
        require(isinstance(rows,list) and all(type(x['cpu']) is int for x in rows), 'CPUID CPU 번호 형식이 잘못됐습니다')
        require([x['cpu'] for x in rows] == sorted(usable), 'CPUID CPU 기록이 누락/중복됐습니다')
        cpu_rows = {x['cpu']:x for x in rows}
        vendors = {x['vendor'] for x in rows}
        require(len(vendors) == 1 and next(iter(vendors)) in ['GenuineIntel', 'AuthenticAMD'], '단일 지원 제조사를 확인할 수 없습니다')
        vendor = next(iter(vendors))
        require(len({(x['family'],x['model'],x['stepping']) for x in rows}) == 1, '혼합 CPU signature는 지원하지 않습니다')
        for x in rows:
            info = value['cpus'][str(x['cpu'])]
            require(isinstance(info['core_type_raw'], str) and (info['capacity'] is None or isinstance(info['capacity'], str)), 'sysfs 코어 유형/capacity 형식 오류')
            require(x['vendor'] == info['vendor'] and all(type(x[k]) is int and x[k] == info[k] for k in ['family','model','stepping']), 'CPUID와 /proc CPU Identity가 모순됩니다')
            require(type(x['hybrid']) is bool and type(x['amd_heterogeneous']) is bool and type(x['amd_leaf26']) is bool, 'CPUID feature 형식 오류')
            require(type(x['core_type']) is int and type(x['native_model']) is int, 'CPUID core type 형식 오류')
        hybrid = vendor == 'GenuineIntel' and all(x['hybrid'] for x in rows)
        require(vendor != 'GenuineIntel' or len({x['hybrid'] for x in rows}) == 1, 'Intel Hybrid feature가 CPU마다 다릅니다')
        if vendor == 'AuthenticAMD':
            require(not any(x['hybrid'] or x['amd_heterogeneous'] or x['core_type'] != 0 for x in rows), 'AMD 이종/미지원 코어 유형은 지원하지 않습니다')
            require(len({(x['amd_leaf26'],x['native_model']) for x in rows}) == 1, 'AMD 코어별 유형/모델 정보가 일치하지 않습니다')
        if hybrid:
            require(all(x['core_type'] in [0x20,0x40] for x in rows), '지원하지 않는 Intel Hybrid core type입니다')
        else:
            require(all(x['core_type'] == 0 for x in rows), '동종 코어 가정을 확인할 수 없습니다')
            raw = {value['cpus'][str(c)]['core_type_raw'].lower() for c in usable}
            require(raw <= {'','core','performance'} and len(raw - {''}) <= 1, '동종 CPU의 sysfs core type이 미지원/불일치입니다')
            capacities = {value['cpus'][str(c)]['capacity'] for c in usable}
            require(len(capacities) == 1, '동종 CPU의 capacity 정보가 서로 다릅니다')
        normalized = dict(usable_cpus=sorted(usable), online_cpus=sorted(online), allowed_cpus=sorted(allowed),
                          cpus={k:dict(v, die=-1 if v['die'] is None else v['die']) for k,v in value['cpus'].items()},
                          heterogeneous=dict(multiple_core_types=False, frequency_hint=False))
        types = {c:cpu_rows[c]['core_type'] if hybrid else 0 for c in usable}
        policy = original.classify(normalized, types)
        require(policy['enabled'], '기존 E tier 변환이 거부됐습니다: ' + policy['reason'])
        selected = policy['tiers'][0]
        require(selected, '사용 가능한 P-core 또는 물리 코어 대표가 없습니다')
        selected_groups = {(value['cpus'][str(c)]['package'],value['cpus'][str(c)]['die'],value['cpus'][str(c)]['core']) for c in selected}
        require(len(selected) == len(selected_groups), '동일 물리 코어를 중복 선택했습니다')
        core_rows = []
        for group in groups.values():
            members = sorted(set(group) & usable)
            if not members:
                continue
            rep = members[0]
            core_rows.append(dict(package=value['cpus'][str(rep)]['package'], die=value['cpus'][str(rep)]['die'], core=value['cpus'][str(rep)]['core'],
                                  representative=rep, usable_siblings=members, core_type='P' if hybrid and types[rep] == 64 else 'E' if hybrid else 'HOMOGENEOUS'))
        return dict(status='SUPPORTED_CONFIGURATION_ONLY',vendor='Intel' if vendor=='GenuineIntel' else 'AMD',vendor_id=vendor,
                    cpu_model=value['cpus'][str(min(usable))]['model_name'],architecture='INTEL_HYBRID' if hybrid else 'HOMOGENEOUS',
                    usable_physical_cores=len(core_rows),physical_p_cores=sum(x['core_type']=='P' for x in core_rows) if hybrid else None,
                    physical_e_cores=sum(x['core_type']=='E' for x in core_rows) if hybrid else None,selected_physical_cores=len(selected),selected_cpus=selected,
                    excluded_smt_cpus=policy['tiers'][2],unused_e_cpus=policy['tiers'][1],compute_threads=len(selected),batch_threads=len(selected),http_threads=2,
                    cpu_affinity=','.join(map(str,selected)),cores=core_rows,policy=policy,housekeeping='NOT_ASSIGNED_SYSTEM_UNCHANGED',
                    topology_fingerprint=fingerprint(value),cpuid_fingerprint=fingerprint(evidence),snapshot=value,cpuid=evidence,
                    execution_admitted=False,strict_acceptance='FAILED',safety_verdict='FAIL',other_host_runtime='NOT_TESTED')
    except (KeyError, TypeError, IndexError) as error:
        raise Unsupported('필수 topology/CPUID 자료를 검증할 수 없습니다: ' + str(error)) from error


def discover(helper, requested=None, reader=None, prober=None):
    require(platform.system() == 'Linux' and platform.machine() == 'x86_64', 'Linux x86_64만 지원합니다')
    reader = reader or (lambda:snapshot(requested=requested))
    prober = prober or (lambda value:probe(value,helper))
    before = reader()
    evidence = prober(before)
    after = reader()
    require(before == after, 'CPUID 확인 도중 topology/hotplug/허용 CPU 상태가 변경됐습니다. 재시도하지 않습니다')
    return plan(before,evidence)
