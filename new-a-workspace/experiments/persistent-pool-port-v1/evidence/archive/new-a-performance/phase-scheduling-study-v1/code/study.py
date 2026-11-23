#!/usr/bin/env python3
"""Fixed-runtime, distinct-request scheduling study. Private local research."""
import argparse
import copy
from contextlib import nullcontext
import datetime
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import sys
import time

STUDY = Path(__file__).resolve().parents[1]
WORKSPACE = STUDY.parents[1]
REPO = WORKSPACE / 'new-a-llm-scheduler'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


m = module('study_measure', REPO / 'tools/sched_ext/new_a_portable_runtime/measure.py')
characterize = module('study_cohort', REPO / 'experiments/phase_generalization/characterize.py')
contention = module('study_contention', REPO / 'experiments/controlled_load/contention.py')
handoff_build = module('study_handoff', REPO / 'experiments/idle_handoff/build.py')
scheduler_evidence = module('study_scheduler_evidence', Path(__file__).with_name('scheduler_evidence.py'))
decode_policy_evidence = module('study_decode_policy_evidence', Path(__file__).with_name('decode_policy_evidence.py'))
prefill_pressure_evidence = module('study_prefill_pressure_evidence', Path(__file__).with_name('prefill_pressure_evidence.py'))
system_libraries = module('study_system_libraries', Path(__file__).with_name('system_libraries.py'))
require, save, sha = m.require, m.save, m.sha


def read(path):
    return json.loads(Path(path).read_text())


def record(event, status, details):
    ledger = read(STUDY / 'ledger.json')
    ledger['entries'].append(dict(id=event, status=status,
        time=datetime.datetime.now(datetime.timezone.utc).isoformat(), **details))
    save(STUDY / 'ledger.json', ledger)
    with (STUDY / 'GOAL_STATE.md').open('a') as stream:
        stream.write('\nLatest event: ' + event + ' / ' + status + '\n' + json.dumps(details) + '\n')


def check_hashes(values):
    for path, expected in values.items():
        require(sha(path) == expected, 'Protected input changed: ' + path)


def cases():
    b1_identity = read(STUDY / 'identity/B1.json')
    b1 = b1_identity['study_config']
    base = {k: copy.deepcopy(b1[k]) for k in ['server_argv', 'server_env', 'artifacts']}
    base.update(runtime='B1_start_q4_exact', scheduler='linux', profile='legacy',
                system_libraries=system_libraries.expected(b1_identity, WORKSPACE))
    original = copy.deepcopy(base)
    b0 = read(STUDY / 'identity/B0/identity.json')
    original['server_argv'][0] = b0['server']
    index = original['server_argv'].index('--server-compute-profile-mode')
    del original['server_argv'][index:index + 2]
    original['server_env'] = {k: v for k, v in original['server_env'].items() if not k.startswith('GGML_NEWA_')}
    original['server_env']['LD_LIBRARY_PATH'] = b0['runtime_dir']
    original.update(runtime='B0_original_7a2db1a', profile='original', artifacts=b0['artifacts'],
                    system_libraries=system_libraries.expected(b0, WORKSPACE))
    result = {'B0': original, 'B1': base}
    for name, profile, generation, batch, scheduler in [
        ('C0', 'legacy', 5, 6, 'decode'),
        ('A-phase5-linux', 'phase', 5, 6, 'linux'),
        ('A-fixed6-linux', 'phase', 6, 6, 'linux'),
        ('A-fixed5-linux', 'phase', 5, 5, 'linux'),
        ('A-phase5-scx', 'phase', 5, 6, 'decode'),
        ('B-observe', 'legacy', 5, 6, 'observe'),
        ('AB-observe', 'phase', 5, 6, 'observe'),
    ]:
        case = copy.deepcopy(base)
        for key, value in [('--server-compute-profile-mode', profile), ('--threads', generation), ('--threads-batch', batch)]:
            case['server_argv'][case['server_argv'].index(key) + 1] = str(value)
        case.update(scheduler=scheduler, profile=profile)
        result[name] = case
    scheduler = read(STUDY / 'identity/start-scheduler.json')
    guard_path = STUDY / 'artifacts/scx-decode-guard/identity.json'
    if guard_path.exists():
        guard = read(guard_path)
        case = copy.deepcopy(result['C0'])
        case.update(loader=guard['loader']['path'], instrumentation='GUARD_NO_DETAIL',
                    scheduler_identity=guard, scheduler_build_path=str(guard_path),
                    scheduler_artifacts={guard[k]['path']: guard[k]['sha256'] for k in ['source', 'object', 'loader']})
        result['C-guard'] = case
    base = copy.deepcopy(result['B1'])
    static = scheduler['static_build']
    base.update(scheduler='base', loader=static['loader']['path'],
                scheduler_artifacts={static[k]['path']: static[k]['sha256'] for k in ['source', 'full_object', 'loader']})
    result['S-base'] = base
    locality_path = WORKSPACE / 'new-a-lab/locality-build-v2/locality-static.json'
    if locality_path.exists():
        locality = read(locality_path)
        for mode in ['all', 'decode']:
            variant = locality['variants'][mode]
            case = copy.deepcopy(base)
            case.update(scheduler='locality_' + mode, loader=variant['loader']['path'],
                        scheduler_build_path=str(locality_path), scheduler_identity=locality,
                        scheduler_artifacts={variant[k]['path']: variant[k]['sha256'] for k in ['source', 'loader']})
            case['scheduler_artifacts'].update({v['path']: v['sha256'] for v in variant['objects'].values()})
            result['C-locality-' + mode] = case
    resource_path = STUDY / 'artifacts/runtime-decode-cost-v1/identity.json'
    if resource_path.exists():
        resource = read(resource_path)
        for policy in ['off', 'fixed6', 'fixed5', 'adaptive']:
            for schedule, parent in [('linux', 'A-phase5-linux'), ('observe', 'AB-observe'), ('decode', 'A-phase5-scx'),
                                     ('base', 'S-base'), ('locality-all', 'C-locality-all'),
                                     ('locality-decode', 'C-locality-decode')]:
                if parent not in result:
                    continue
                case = copy.deepcopy(result[parent])
                case['server_argv'][case['server_argv'].index('--server-compute-profile-mode') + 1] = 'phase'
                case['server_argv'][0] = resource['server']
                case['server_env']['LD_LIBRARY_PATH'] = str(Path(resource['server']).parent)
                case['server_env']['NEWA_DECODE_RESOURCE'] = policy
                case.update(runtime='NEW_A_decode_cost_v1', profile='phase', correctness_family='B1_start_q4_exact',
                            artifacts=resource['artifacts'], runtime_identity_path=str(resource_path),
                            marker=str(Path(resource['server']).parent / 'libllama-server-impl.so'),
                            resource_policy=policy, allowed_teams=[5, 6],
                            required_teams=[6] if policy == 'fixed6' else [5, 6])
                result['D-' + policy + '-' + schedule] = case
    pressure_path = STUDY / 'artifacts/runtime-prefill-pressure-v2/identity.json'
    if pressure_path.exists():
        pressure = read(pressure_path)
        for policy in ['off', 'fixed6', 'fixed5', 'pressure']:
            for schedule, parent in [('linux', 'A-phase5-linux'), ('observe', 'AB-observe'), ('base', 'S-base')]:
                case = copy.deepcopy(result[parent])
                case['server_argv'][case['server_argv'].index('--server-compute-profile-mode') + 1] = 'phase'
                case['server_argv'][0] = pressure['server']
                case['server_env']['LD_LIBRARY_PATH'] = str(Path(pressure['server']).parent)
                case['server_env']['NEWA_DECODE_RESOURCE'] = policy
                case.update(runtime='NEW_A_prefill_pressure_v2', profile='phase', correctness_family='B1_start_q4_exact',
                            artifacts=pressure['artifacts'], runtime_identity_path=str(pressure_path),
                            marker=str(Path(pressure['server']).parent / 'libllama-server-impl.so'),
                            resource_policy=policy, resource_evidence_kind='prefill_pressure', allowed_teams=[5, 6],
                            required_teams=[6] if policy in ['pressure', 'fixed6'] else [5, 6])
                result['E-' + policy + '-' + schedule] = case
    return result


def find_ops(value):
    if isinstance(value, dict):
        if value.get('name') == 'llama_new_a' and 'flags' in value:
            return [value]
        return [item for child in value.values() for item in find_ops(child)]
    return [item for child in value for item in find_ops(child)] if isinstance(value, list) else []


def prepare(args):
    root = STUDY / 'runs' / args.name
    require(os.getuid() != 0 and os.sched_getscheduler(0) == 0, 'Use ordinary Linux account')
    require(not root.exists(), 'Use a new attempt name; preserve previous attempts')
    require(not m.active_experiments(), 'Another experiment is active')
    require(m.optional('/sys/kernel/sched_ext/state') == 'disabled', 'Scheduler already active')
    require(not m.config.AFFINITY_ENV.intersection(os.environ), 'Inherited affinity environment')
    require(shutil.disk_usage(WORKSPACE).free >= 512 * 1024**2, 'Disk reserve reached')
    protocol = read(STUDY / 'protocol.json')
    require(sha(WORKSPACE / 'model.gguf') == protocol['correctness']['model_sha256'], 'Model changed')
    check_hashes(read(STUDY / 'identity/protected-start-hashes.json'))
    scheduler = read(STUDY / 'identity/start-scheduler.json')
    static = scheduler['static_build']
    selection = m.topology.discover(static['cpu_probe']['path'])
    for key in ['topology_fingerprint', 'cpuid_fingerprint']:
        require(selection[key] == static['guard'][key], 'Host identity changed: ' + key)
    require(selection['selected_cpus'] == static['guard']['server_cpus'] == scheduler['cpus'], 'CPU envelope changed')
    controls = m.controls()
    require(static['kernel'] == controls['kernel'] and static['btf_sha256'] == sha('/sys/kernel/btf/vmlinux'), 'Kernel/BTF changed')
    require('1' in controls['ac'].values() and controls['bpf_stats_enabled'] == '0', 'Power/instrumentation changed')
    handoff_build.validate(WORKSPACE / 'new-a-lab/build-idle-handoff-v1', scheduler['handoff_build'])
    registry = cases()
    require(all(name in registry for name in args.arms), 'Unknown arm')
    selected = {name: registry[name] for name in args.arms}
    require(len(selected) == len(args.arms), 'Duplicate arm')
    frozen = None
    if getattr(args, 'freeze', None):
        frozen = read(args.freeze)
        require(frozen['status'] == 'FROZEN_BEFORE_HELDOUT_COMPLETIONS', 'Replay selection is not frozen')
        check_hashes(frozen['protected'])
        expected_cases = {name: frozen['cases'][alias] for name, alias in
                          [('B0','B0'),('B1','B1'),(frozen['selection']['C'],'C'),(frozen['selection']['C-off'],'C-off')]}
        require(selected == expected_cases, 'Smoke/pilot replay differs from frozen cases')
    if any(v['scheduler'] != 'linux' for v in selected.values()):
        probe = subprocess.run(['sudo', '-n', 'taskset', '-c', '11', scheduler['loader'], '--help'], capture_output=True, text=True, timeout=10)
        require(probe.returncode == 0, 'Guarded loader permission unavailable: ' + probe.stderr)
    protected = {}
    for value in selected.values():
        protected.update(value['artifacts'])
        protected.update(value['system_libraries'])
        protected.update(value.get('scheduler_artifacts', {}))
        if value.get('runtime_identity_path'):
            protected[value['runtime_identity_path']] = sha(value['runtime_identity_path'])
            extra_runtime = read(value['runtime_identity_path'])
            require(extra_runtime['arithmetic_kernel_dsos_byte_identical'], 'New runtime replaced old arithmetic libraries')
            check_hashes(extra_runtime['source_hashes'])
        if value.get('scheduler_build_path'):
            protected[value['scheduler_build_path']] = sha(value['scheduler_build_path'])
            extra = value['scheduler_identity']
            require(extra['guard'] == static['guard'] and extra['kernel'] == static['kernel'] and
                    extra['btf_sha256'] == static['btf_sha256'], 'Extra scheduler host guard changed')
        if value.get('instrumentation') == 'GUARD_NO_DETAIL':
            builder = module('study_guard_builder', Path(__file__).with_name('build_guard_accounting.py'))
            extra = value['scheduler_identity']
            original = Path(scheduler['handoff_build']['variants']['decode']['source']['path']).read_text()
            require(Path(extra['source']['path']).read_text() == builder.derive(original), 'Guard source derivation changed')
            require(builder.proof(extra['baseline']['path'], extra['object']['path']) == extra['proof'], 'Guard static proof changed')
            require((extra['object']['path'] + '\0').encode() in Path(value['loader']).read_bytes(), 'Guard loader binding changed')
        if value['scheduler'].startswith('locality_'):
            builder = module('study_locality_builder', REPO / 'experiments/soft_locality/locality_build.py')
            builder.validate(Path(value['scheduler_build_path']).parent, value['scheduler_identity'])
            require(value['scheduler_identity']['baseline_source'] == static['source'], 'Locality baseline source differs')
    for key in ['cpu_probe', 'child', 'source', 'loader', 'full_object', 'plain_object']:
        protected[static[key]['path']] = static[key]['sha256']
    for variant in scheduler['handoff_build']['variants'].values():
        protected[variant['loader']['path']] = variant['loader']['sha256']
        protected.update({value['path']: value['sha256'] for value in variant['objects'].values()})
    sources = [Path(__file__), Path(m.__file__), Path(characterize.__file__), Path(contention.__file__),
               Path(contention.__file__).with_name('load.py'), REPO / 'tools/sched_ext/new_a/session.py',
               Path(scheduler_evidence.__file__), Path(decode_policy_evidence.__file__), Path(prefill_pressure_evidence.__file__),
               Path(system_libraries.__file__)]
    protected.update({str(p): sha(p) for p in sources})
    if frozen:
        for path, expected in frozen['protected'].items():
            require(path not in protected or protected[path] == expected, 'Replay protected identity conflict')
            protected[path] = expected
        protected[str(Path(args.freeze).resolve())] = sha(args.freeze)
    check_hashes(protected)
    reference = WORKSPACE / 'new-a-performance/phase-generalization-goal/batch8-separated-fa-functional-v1'
    requests = read(reference / 'requests.json')
    require(len(requests) == 8 and all(r['n_predict'] == 128 for r in requests), 'Exploration request set differs')
    items = read(REPO / 'experiments/phase_generalization/workloads.json')['short'][:8]
    golden = read(reference / 'result.json')
    require(golden['status'] == 'FUNCTIONAL_PASS_NOT_PERFORMANCE_EVIDENCE', 'Retained golden incomplete')
    golden_tokens = [row['response']['tokens'] for row in golden['rounds'][0]['responses']]
    require(all([r['response']['tokens'] for r in turn['responses']] == golden_tokens for turn in golden['rounds']), 'Retained golden unstable')
    canonical = {'B1_start_q4_exact': golden_tokens}
    if args.reference:
        prior = STUDY / 'runs' / args.reference
        evidence = read(prior / 'summary.json')
        require(evidence['status'] == 'COMPLETE' and requests == read(prior / 'requests.json'), 'Reference incomplete/different workload')
        require(evidence['canonical_tokens'].get('B1_start_q4_exact') == golden_tokens, 'Reference differs from fixed NEW_A golden')
        canonical.update(evidence['canonical_tokens'])
    plan = []
    for condition in args.conditions:
        for block in range(1, (1 if args.stage == 'smoke' else 2) + 1):
            for arm in args.arms if block % 2 else args.arms[::-1]:
                plan.append(dict(condition=condition, block=block, arm=arm))
    root.mkdir(parents=True)
    (root / 'topology.bin').write_bytes(m.topology.original.encode(selection['policy']))
    setup = dict(stage=args.stage, plan=plan, cases=selected, scheduler=scheduler,
                 cpus=scheduler['cpus'], housekeeping=scheduler['housekeeping'], load_cpu=selection['selected_cpus'][-1],
                 controls=controls, protected=protected, protocol=protocol, concurrency=8,
                 warmups=1, canonical_tokens=canonical, workload='exploration-old-short-8',
                 source_snapshots={str(p): sha(p) for p in sources}, input_items=items,
                 scope='FIXED_AFFINITY_LOCAL_RESEARCH_NOT_GLOBAL_SAFETY_APPROVAL')
    save(root / 'setup.json', setup)
    save(root / 'requests.json', requests)
    save(root / 'selection.json', selection)
    for p in sources:
        target = root / 'sources' / (str(p.relative_to(WORKSPACE)).replace('/', '__'))
        target.parent.mkdir(exist_ok=True)
        shutil.copy2(p, target)
    return root, setup, requests


def visit(root, spec, setup, requests, canonical):
    folder = root / spec['condition'] / ('block-' + str(spec['block'])) / spec['arm']
    folder.mkdir(parents=True)
    case = setup['cases'][spec['arm']]
    command, env = list(case['server_argv']), dict(case['server_env'])
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    command[command.index('--port') + 1] = str(port)
    ext = case['scheduler'] != 'linux'
    scheduler = setup['scheduler']
    loader = (case.get('loader') or scheduler['handoff_build']['variants'][case['scheduler']]['loader']['path']) if ext else None
    require(m.controls() == setup['controls'], 'Controls changed')
    require(shutil.disk_usage(WORKSPACE).free >= 512 * 1024**2, 'Disk reserve reached')
    require(int(re.search(r'MemAvailable:\s+(\d+)', Path('/proc/meminfo').read_text())[1]) >= 3000000, 'Memory reserve reached')
    require(m.temperatures().get('k10temp:temp1_input', 100) < 85, 'Pre-visit CPU temperature unsafe')
    check_hashes(setup['protected'])
    session = m.Session(folder, command, setup['cpus'], setup['housekeeping'], policy='E' if ext else 'C',
        topology=root / 'topology.bin', env=env, diagnostics=ext, marker=case.get('marker', scheduler['marker']),
        loader_binary=loader, child_binary=scheduler['child'])
    load_context = contention.ControlledLoad(folder / 'controlled-load', setup['load_cpu']) if spec['condition'] == 'cpu25' else nullcontext(None)
    result = dict(**spec, runtime=case['runtime'], scheduler=case['scheduler'], status='RUNNING', directory=str(folder))
    try:
        with load_context as load, session:
            m.ready(session, port)
            pid = session.server['pid']
            actual_command = Path(f'/proc/{pid}/cmdline').read_bytes().rstrip(b'\0').decode().split('\0')
            actual_env = dict(item.split('=', 1) for item in Path(f'/proc/{pid}/environ').read_bytes().rstrip(b'\0').decode().split('\0'))
            mapped = sorted({line.split()[-1] for line in Path(f'/proc/{pid}/maps').read_text().splitlines() if '/' in line})
            require(actual_command == command and actual_env == env, 'Actual configuration differs')
            require(set(case['artifacts']).issubset(mapped), 'Actual project libraries differ')
            loaded = {path: sha(path) for path in mapped if Path(path).is_file() and ('.so' in Path(path).name or path == command[0])}
            save(folder / 'runtime.json', dict(argv=actual_command, environment=actual_env, mapped=mapped, loaded_elf_sha256=loaded))
            system_libraries.validate(loaded, case['system_libraries'], WORKSPACE)
            for request, item in zip(requests, setup['input_items']):
                tokens, _, _ = m.http(port, '/tokenize', dict(content=item['prompt'], add_special=True))
                require(tokens['tokens'][:setup.get('input_token_cap', 256)] == request['prompt'], 'Runtime input tokenization differs')
            if ext:
                require('FULL_GUARD_MONITOR_READY' in (folder / 'loader.log').read_text(), 'Guard not ready')
                dump = subprocess.run(['sudo', '-n', 'bpftool', '-j', 'struct_ops', 'dump', 'name', 'llama_ops'], capture_output=True, text=True, timeout=15)
                require(dump.returncode == 0, 'Scheduler inspection failed: ' + dump.stderr)
                ops = json.loads(dump.stdout)
                save(folder / 'struct-ops.json', ops)
                found = find_ops(ops)
                require(len(found) == 1 and int(str(found[0]['flags']), 0) == 8, 'Scheduler partial-switch mode differs')
            for role in ['warmup', 'measured']:
                before = m.snapshot(pid, setup['cpus'], 7 if ext else 0)
                if load:
                    before['controlled_load'] = load.snapshot()
                concurrency = setup.get('concurrency', 8)
                require(concurrency != 1 or len(requests) == 1, 'Single-request timer requires exactly one request')
                responses, client_total_s = characterize.cohort(port, requests, concurrency)
                if concurrency == 1:
                    responses[0]['cohort_http_ms'] = responses[0]['http_ms']
                # HTTP timing stops at receipt of all bytes, before JSON/output validation.
                elapsed = responses[0]['cohort_http_ms'] / 1000
                after = m.snapshot(pid, setup['cpus'], 7 if ext else 0)
                if load:
                    after['controlled_load'] = load.snapshot()
                save(folder / (role + '-responses.json'), responses)
                save(folder / (role + '-counters.json'), dict(before=before, after=after))
                tokens = [row['response']['tokens'] for row in responses]
                require(all(len(t) == r['n_predict'] for t, r in zip(tokens, requests)), 'Output tokens incomplete')
                family = case.get('correctness_family', case['runtime'])
                if family not in canonical:
                    require(case['runtime'] in ['B0_original_7a2db1a', 'B1_start_q4_exact'],
                            'A candidate cannot create its own correctness reference')
                    if 'allow_reference_creation' in setup:
                        require(setup['allow_reference_creation'], 'Missing independent correctness reference')
                    canonical[family] = tokens
                require(tokens == canonical[family], 'Token mismatch within fixed runtime/new policy')
                require(m.controls() == setup['controls'], 'Controls changed during cohort')
                require(m.optional('/sys/kernel/sched_ext/state') == ('enabled' if ext else 'disabled'), 'Scheduler detached or unexpectedly attached')
                if ext:
                    require(session.loader.poll() is None, 'Loader exited during cohort')
                metrics = m.metrics(before, after, responses[0]['response'], elapsed * 1000, setup['cpus'], 'process_ticks')
                metrics.pop('prefill_tps')
                metrics.pop('decode_tps')
                generated = sum(row['response']['tokens_predicted'] for row in responses)
                metrics.update(cohort_wall_s=elapsed, client_with_validation_s=client_total_s,
                    generated_tokens=generated, generated_tokens_per_s=generated / elapsed,
                    per_request_timings=[r['response']['timings'] for r in responses])
                delivered = contention.metrics(before['controlled_load'], after['controlled_load'], metrics['counter_window_s']) if load else None
                save(folder / (role + '-metrics.json'), dict(metrics=metrics, controlled_load=delivered))
                if load:
                    require(.22 <= delivered['mean_cpu_cores'] <= .28, 'Delivered load outside fixed range')
                print(json.dumps(dict(event='COHORT', role=role, **spec, wall_s=elapsed, load=delivered)), flush=True)
            log = (folder / 'server.stderr.log').read_text()
            sizes = sorted({int(size) for size in re.findall(r'NEWA_TEAM pid=\d+ team=(\d+)', log)})
            expected_teams = sorted({int(command[command.index('--threads') + 1]), int(command[command.index('--threads-batch') + 1])}) if case['profile'] == 'phase' else [int(command[command.index('--threads-batch') + 1])]
            if 'allowed_teams' in case:
                require(set(sizes).issubset(case['allowed_teams']) and set(case['required_teams']).issubset(sizes),
                        'Resource policy actual teams differ')
            else:
                require(sizes == expected_teams, 'Expected teams not observed')
            teams = m.openmp_teams(log, pid, sizes)
        require(read(folder / 'cleanup.json')['status'] == 'PASS', 'Session cleanup failed')
        log = (folder / 'server.stderr.log').read_text()
        routing = {}
        if case['runtime'] != 'B0_original_7a2db1a':
            for key, pattern in [('q4', r'NEWA_Q4_TILE32 stats worker0_calls=(\d+)/(\d+)/(\d+)/(\d+)'),
                                 ('q6', r'NEWA_Q6 stats worker0_chunks=(\d+)/(\d+)/(\d+)/(\d+)')]:
                counts = re.findall(pattern, log)
                require(len(counts) == 1, 'Missing retained kernel evidence: ' + key)
                routing[key] = list(map(int, counts[0]))
                require(routing[key][0] == 0 and routing[key][1] > 0, 'Retained Prefill kernel disabled or UNKNOWN used')
                if setup.get('require_decode_kernel', True):
                    require(routing[key][2] > 0, 'Retained Decode kernel disabled')
        diagnostics = scheduler_evidence.validate(read(folder / 'scheduler-stats.json'), setup['cpus'],
            scheduler['static_build']['guard']['possible_cpu_slots'], case.get('instrumentation', 'FULL')) if ext else dict(status='LINUX')
        handoff = read(folder / 'scheduler-stats.json').get('idle_handoff') if ext else None
        require(bool(handoff) == (case['scheduler'] in ['decode', 'observe']), 'Decision counter schema differs')
        if handoff:
            require(handoff['mode'] == case['scheduler'], 'Handoff mode differs')
            require(len(handoff['attempts']) == len(handoff['moved']) == 4, 'Handoff phase arrays differ')
            require(all(a >= b >= 0 for a, b in zip(handoff['attempts'], handoff['moved'])), 'Invalid handoff counts')
            if case['scheduler'] == 'observe':
                require(handoff['moved'] == [0, 0, 0, 0], 'Observe unexpectedly dispatched')
            if case['scheduler'] == 'decode':
                require(all(handoff['attempts'][i] == handoff['moved'][i] == 0 for i in [0, 1, 3]), 'Handoff outside declared phase')
        resource_auditor = prefill_pressure_evidence if case.get('resource_evidence_kind') == 'prefill_pressure' else decode_policy_evidence
        resource = resource_auditor.validate(log, case['resource_policy']) if 'resource_policy' in case else None
        if resource:
            decisions = resource.get('decisions_5_6', [])
            if 'epochs' in resource:
                decisions = [row for epoch in resource['epochs'] for row in epoch['decisions_5_6']]
            submitted = {5 + i for i in range(2) if any(row[i] > 0 for row in decisions)}
            require(submitted.issubset(sizes), 'Submitted resource profile lacks observed OpenMP team')
            save(folder / 'resource-decisions.json', resource)
        result.update(status='COMPLETE', metrics=metrics, controlled_load=delivered, teams=teams,
                      routing=routing, diagnostics=diagnostics, handoff=handoff, resource_policy=resource)
    except BaseException as error:
        result.update(status='FAILED', error=repr(error))
        raise
    finally:
        result['scheduler_end_state'] = m.optional('/sys/kernel/sched_ext/state')
        save(folder / 'result.json', result)
    return result


def run(args):
    root, setup, requests = prepare(args)
    canonical = copy.deepcopy(setup['canonical_tokens'])
    result = dict(status='RUNNING', stage=args.stage, visits=[], canonical_tokens=canonical)
    record(args.name, 'RUNNING', dict(path=str(root), next='Inspect running session; do not start a second measurement.'))
    try:
        for spec in setup['plan']:
            print(json.dumps(dict(event='START', **spec)), flush=True)
            row = visit(root, spec, setup, requests, canonical)
            result['visits'].append(row)
            save(root / 'summary.json', result)
            time.sleep(2)
        check_hashes(setup['protected'])
        check_hashes(read(STUDY / 'identity/protected-start-hashes.json'))
        require(m.controls() == setup['controls'], 'Final controls changed')
        result['status'] = 'COMPLETE'
        if len(canonical) == 2:
            a, b = canonical['B0_original_7a2db1a'], canonical['B1_start_q4_exact']
            result['existing_B0_B1_token_differences'] = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
    except BaseException as error:
        result.update(status='FAILED', error=repr(error))
        raise
    finally:
        save(root / 'summary.json', result)
        record(args.name, result['status'], dict(path=str(root), completed_visits=len(result['visits']),
            error=result.get('error'), next='Read raw results and select the next evidence-based pilot; confirmations remain required.'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['smoke', 'pilot'], required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--arms', nargs='+', default=['B0', 'B1', 'C0'])
    parser.add_argument('--conditions', nargs='+', choices=['ambient', 'cpu25'], default=['ambient'])
    parser.add_argument('--reference')
    parser.add_argument('--freeze', help='Require exact frozen selection/configuration for smoke or pilot replay')
    args = parser.parse_args()
    require(re.fullmatch('[a-zA-Z0-9_-]+', args.name), 'Invalid attempt name')
    with (WORKSPACE / 'new-a-runs/.measurement.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for sig in [signal.SIGTERM, signal.SIGHUP]:
            signal.signal(sig, signal.default_int_handler)
        run(args)
