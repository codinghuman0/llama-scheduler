# SPDX-License-Identifier: GPL-2.0
"""Experimental thread/affinity proposals. No scheduler or runtime changes."""
from pathlib import Path
import re
from collect import portable, require

PROFILE = 'intel_hybrid_experimental_performance'
VERSION = 'new_a_hybrid.experimental.v1'


def checked_plan(detected):
    plan = detected['portable_plan']
    expected = portable.fingerprint(dict(snapshot=plan['snapshot'], cpuid=plan['cpuid'], extra=detected['hardware'], probe=detected['probe_sha256']))
    require(detected['schema'] == 1 and detected['fingerprint'] == expected, 'Detection fingerprint changed')
    require(portable.fingerprint(plan) == portable.fingerprint(portable.plan(plan['snapshot'], plan['cpuid'])), 'Portable classification changed')
    return plan


def e_groups(detected, cpus):
    plan = detected['portable_plan']
    hardware = detected['hardware']['cpus']
    groups = {}
    for cpu in cpus:
        info = plan['snapshot']['cpus'][str(cpu)]
        caches = [c for c in hardware[str(cpu)]['caches'] if c['level'] == 2 and c['type'] in ['Unified', 'Data']]
        memberships = {tuple(c['shared_cpus']) for c in caches}
        if not memberships:
            return None
        require(len(memberships) == 1, 'Conflicting L2 groups for an E-core')
        members = next(iter(memberships))
        require(cpu in members and set(members) <= set(plan['snapshot']['possible_cpus']), 'Invalid L2 sharing set')
        for other in set(members) & set(cpus):
            other_sets = {tuple(c['shared_cpus']) for c in hardware[str(other)]['caches'] if c['level'] == 2 and c['type'] in ['Unified', 'Data']}
            require(other_sets == {members}, 'Non-reciprocal E-core L2 groups')
        key = (info['package'], info['die'], members)
        groups.setdefault(key, []).append(cpu)
    return [dict(package=key[0], die=key[1], shared_cpus=list(key[2]), usable_e_cpus=sorted(value))
            for key, value in sorted(groups.items(), key=lambda item: min(item[1]))]


def select_e(detected, count, placement):
    require(placement in ['compact', 'spread', 'lowest'], 'Unknown E-core placement')
    plan = detected['portable_plan']
    cpus = sorted(plan['unused_e_cpus'])
    require(type(count) is int and 0 <= count <= len(cpus), 'Requested E-core count unavailable')
    if not count:
        return [], [], 'NO_E_CORE_SELECTED'
    groups = e_groups(detected, cpus)
    if groups is None:
        require(placement != 'spread', 'Cannot claim spread placement without verified L2 groups')
        return cpus[:count], [], 'LOWEST_CPU_IDS_L2_NOT_VERIFIED'
    if placement == 'lowest':
        selected = cpus[:count]
        rule = 'LOWEST_USABLE_E_CPU_IDS'
    elif placement == 'compact':
        # Prefer one sufficient group; otherwise pack stable ascending groups.
        sufficient = next((g for g in groups if len(g['usable_e_cpus']) >= count), None)
        ordered = [sufficient] if sufficient is not None else groups
        selected = [c for g in ordered for c in g['usable_e_cpus']][:count]
        rule = 'SINGLE_L2_GROUP' if sufficient else 'PACK_MULTIPLE_L2_GROUPS_NO_SINGLE_GROUP_LARGE_ENOUGH'
    else:
        queues = [list(g['usable_e_cpus']) for g in groups]
        selected = []
        while len(selected) < count:
            for queue in queues:
                if queue and len(selected) < count:
                    selected.append(queue.pop(0))
        rule = 'ROUND_ROBIN_ACROSS_VERIFIED_L2_GROUPS'
    used = [dict(g, selected_cpus=sorted(set(g['usable_e_cpus']) & set(selected))) for g in groups if set(g['usable_e_cpus']) & set(selected)]
    return sorted(selected), used, rule


def recommend(detected, placement='compact', e_count=None):
    plan = checked_plan(detected)
    hybrid = plan['architecture'] == 'INTEL_HYBRID'
    representatives = sorted(plan['selected_cpus'])
    p = len(representatives)
    e = len(plan['unused_e_cpus']) if hybrid else 0
    require(not hybrid or p > 0 and e > 0, 'Both available P and E cores required for the hybrid formula')
    require(hybrid or e_count in [None, 0], 'E-core override is not valid for homogeneous CPUs')
    count = e // 2 if e_count is None else e_count
    selected_e, caches, rule = select_e(detected, count, placement) if hybrid else ([], [], 'HOMOGENEOUS_PHYSICAL_REPRESENTATIVES')
    affinity = sorted(representatives + selected_e)
    header = Path(__file__).resolve().parents[4] / 'src/llama/ggml/include/ggml.h'
    limits = re.findall(r'^#define\s+GGML_MAX_N_THREADS\s+(\d+)\s*$', header.read_text(), re.M)
    require(len(limits) == 1 and 1 <= p <= len(affinity) <= int(limits[0]), 'Thread count exceeds the checked GGML header limit; no silent truncation')
    require(len(affinity) == len(set(affinity)) == p + len(selected_e), 'Duplicate CPU in affinity')
    require(set(affinity) <= set(plan['snapshot']['usable_cpus']), 'Selected CPU is not online/allowed')
    info = plan['snapshot']['cpus']
    keys = [(info[str(c)]['package'], info[str(c)]['die'], info[str(c)]['core']) for c in affinity]
    require(len(keys) == len(set(keys)), 'SMT siblings selected twice')
    mapping = [dict(cpu=c, type='P' if hybrid and c in representatives else 'E' if hybrid else 'HOMOGENEOUS',
                    package=info[str(c)]['package'], die=info[str(c)]['die'], core=info[str(c)]['core'],
                    siblings_all=info[str(c)]['siblings_all'], numa_node=detected['hardware']['cpus'][str(c)]['numa_node']) for c in affinity]
    domains = {(x['package'], x['numa_node']) for x in mapping}
    warnings = ['Actual OpenMP team size and Decode P-core residence are NOT_VERIFIED.',
                'Configuration generation is not kernel/BPF or performance approval.']
    if hybrid and not caches and selected_e:
        warnings.append('L2 placement is NOT_VERIFIED; numeric fallback does not claim cache locality.')
    if any(x['numa_node'] is None for x in mapping):
        warnings.append('NUMA association is NOT_VERIFIED for some selected CPUs.')
    if len(domains) > 1:
        warnings.append('Multiple package/NUMA domains selected; memory locality requires separate review.')
    if set(plan['snapshot']['online_cpus']) != set(plan['snapshot']['present_cpus']):
        warnings.append('Offline CPUs excluded; counts describe available cores, not all installed cores.')
    constraints = detected['hardware']['cgroup']
    if constraints['version'] == 'NOT_VERIFIED' or constraints['cpuset_cpus_effective'] is None:
        warnings.append('Cgroup cpuset metadata unavailable; effective sched_getaffinity and online mask remain authoritative.')
    if constraints['cpu_max'] and not constraints['cpu_max'].startswith('max '):
        warnings.append('Visible cgroup CPU bandwidth quota is limited; thread count is not a capacity guarantee.')
    value = dict(schema=1, algorithm=VERSION, profile=PROFILE if hybrid else 'conservative_homogeneous_physical',
                 status='CONFIGURATION_ONLY_REQUIRES_RUNTIME_REVIEW', auto_proposed=True, performance_validated=False,
                 execution_admitted=False, team_cpu_runtime='TEAM_CPU_RUNTIME_NOT_TESTED',
                 cpu_model=plan['cpu_model'], vendor=plan['vendor'], architecture=plan['architecture'],
                 available_physical_cores=plan['usable_physical_cores'], available_p_cores=plan['physical_p_cores'], available_e_cores=plan['physical_e_cores'],
                 online_logical_cpus=len(plan['snapshot']['online_cpus']), present_logical_cpus=len(plan['snapshot']['present_cpus']),
                 compute_threads=p, batch_threads=len(affinity), http_threads=2,
                 p_representatives=representatives if hybrid else [], physical_representatives=representatives,
                 selected_e_cpus=selected_e, excluded_smt_cpus=plan['excluded_smt_cpus'],
                 smt_active_in_online_topology=any(len(set(x['siblings_all']) & set(plan['snapshot']['online_cpus'])) > 1 for x in info.values()),
                 affinity_cpus=affinity, cpu_affinity=','.join(map(str, affinity)), affinity_mask_hex=hex(sum(1 << c for c in affinity)),
                 cpu_mapping=mapping, e_placement_policy=placement, e_placement_effective=rule, selected_e_l2_groups=caches,
                 single_e_l2_group=bool(caches) and len(caches) == 1,
                 formula='P + floor(E/2)' if hybrid and e_count is None else 'EXPLICIT_E_CORE_COUNT_RESEARCH' if hybrid else 'AVAILABLE_PHYSICAL_CORES',
                 explicit_e_count=e_count, requested_cpus=detected['requested_cpus'], topology_fingerprint=detected['fingerprint'],
                 server_thread_arguments=['--threads', str(p), '--threads-batch', str(len(affinity)), '--threads-http', '2'],
                 runtime_requirement='NEW_HOST_BASELINE_AND_GENERALIZED_GUARD_ADAPTER_REQUIRED;_NO_RUNTIME_WIRED',
                 validation='ONLINE_ALLOWED_TYPES_AND_UNIQUE_PHYSICAL_CORES_CHECKED', unverified_assumptions=warnings,
                 strict_acceptance='FAILED', safety_verdict='FAIL', overhead_review='OVERHEAD_REVIEW_REQUIRED')
    value['matches_historical_i5_1240p_configuration'] = bool(hybrid and 'i5-1240P' in plan['cpu_model'] and p == 4 and e == 8 and affinity == [0,2,4,6,8,9,10,11] and count == 4)
    value['configuration_fingerprint'] = portable.fingerprint(value)
    return value


def validate(config, detected):
    expected = recommend(detected, config['e_placement_policy'], config['explicit_e_count'])
    require(portable.fingerprint(config) == portable.fingerprint(expected), 'Stale, altered or foreign configuration; generate a separate proposal')
    return dict(status='VALID_CONFIGURATION_ONLY', configuration_fingerprint=config['configuration_fingerprint'],
                affinity_cpus=config['affinity_cpus'], compute_threads=config['compute_threads'], batch_threads=config['batch_threads'],
                execution_admitted=False, performance_validated=False, team_cpu_runtime='TEAM_CPU_RUNTIME_NOT_TESTED')


def experiments(detected, expect_p=None, expect_e=None):
    plan = checked_plan(detected)
    require(plan['architecture'] == 'INTEL_HYBRID', 'Hybrid experiment plan requires verified Intel P/E types')
    p, e = plan['physical_p_cores'], plan['physical_e_cores']
    require(expect_p is None or p == expect_p, 'Expected available physical P-core count does not match')
    require(expect_e is None or e == expect_e, 'Expected available E-core count does not match')
    count_b = e // 2
    require(count_b > 0, 'No E-core subset available')
    counts = dict(A=0, B=count_b, C=(3 * e) // 4, D=e)
    candidates = {name: recommend(detected, 'compact', n) for name, n in counts.items()}
    main = candidates['B']
    orders = [['C-B', 'E-B'], ['E-B', 'C-B']]
    functional = [dict(policy=policy, candidate='B', mode=mode, configuration=main, runtime='NOT_IMPLEMENTED_NOT_AUTHORIZED')
                  for policy in ['C', 'E'] for mode in ['audit', 'clean']]
    sessions = [dict(block=b, position=i, condition=condition, configuration=main, warmups=2, measurements=1)
                for b, order in enumerate(orders, 1) for i, condition in enumerate(order, 1)]
    spread = recommend(detected, 'spread') if e_groups(detected, plan['unused_e_cpus']) is not None else None
    return dict(schema=1, status='DESIGN_ONLY_NOT_EXECUTABLE', available_p=p, available_e=e,
                priority='B', candidates=candidates, alternate_b_l2_spread=spread,
                primary_comparison='LINUX_VS_NEW_A_FULL_SAME_THREADS_SAME_AFFINITY', FUNCTIONAL=functional, EXPLORATION=sessions,
                optional_candidates=['C','D'], candidate_comparison_confound='A/B/C/D change both batch threads and affinity',
                thread_only_control=dict(affinity_cpus=candidates['D']['affinity_cpus'], batch_threads=sorted({p+n for n in counts.values()}), compute_threads=p),
                prerequisites=['NEW_HOST_PROFILE', 'NEW_RUNTIME_BASELINE', 'BTF_KFUNC', 'GENERALIZED_GUARD_ADAPTER',
                              'FROZEN_MODEL_REQUEST_HASHES', 'AC_FIXED_TURBO_GOVERNOR_POWER', 'AUDIT_CLEAN', 'MASK_TRACKING', 'THERMAL_CLEANUP_SCHED_EXT_DISABLED'],
                observation='SEPARATE_OVERHEAD_VALIDATED_STUDY_REQUIRED;_NO_ASSUMED_DECODE_PLACEMENT',
                promotion='Only coherent exploratory HTTP direction without unacceptable CPU/Decode regression merits >=6 independent paired blocks; no automatic expansion',
                execution_admitted=False, performance_validated=False, team_cpu_runtime='TEAM_CPU_RUNTIME_NOT_TESTED',
                strict_acceptance='FAILED', safety_verdict='FAIL', overhead_review='OVERHEAD_REVIEW_REQUIRED')
