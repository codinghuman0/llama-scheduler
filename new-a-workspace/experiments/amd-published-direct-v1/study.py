#!/usr/bin/env python3
"""Serial, paired AMD measurements of the published integration-v2 runtime."""

from contextlib import nullcontext
import copy
import fcntl
import os
from pathlib import Path
import re
import secrets
import signal
import sys
import threading
import time


HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[1]
PROJECTS = WORKSPACE.parents[1]
PRESERVED = PROJECTS / 'new-a-workspace'
OLD = PRESERVED / 'experiments/a-b0-direct-confirmation-v1'
BUILD = WORKSPACE / 'state/integration-v2/builds/amd-published-direct-v1'
DATA = WORKSPACE / 'state/integration-v2/amd-published-direct-v1'
MODEL = PROJECTS / 'model.gguf'
sys.path[:0] = [str(WORKSPACE / 'tools/integration_v2'), str(WORKSPACE / 'tools')]
sys.path.append(str(WORKSPACE / 'experiments/a-b0-direct-confirmation-v1/code'))
from cli_ko import ArgumentParser, main_entry
import contention
import runtime
from intel_experiment import clean_env, guard, payload_for, read, require, sha, temperatures, validate_body

sys.path.insert(0, str(runtime.SERVING))
import runner


P = read(HERE / 'protocol.json')
ARMS = ('B0', 'A', 'I')
CPUS = P['cpus']
TOKENS = P['tokens_per_request']
CANCEL = threading.Event()

TOPICS = (
    ('harbor inspection', 'library displays', 'evening shuttle', 'plant nursery', 'road resurfacing',
     'seed exchange', 'public pool', 'school fair'),
    ('weather station', 'rail car repairs', 'food pantry', 'forest trail', 'radio broadcast',
     'meeting minutes', 'basketball league', 'theater rehearsal'),
)


def options():
    command = argparse.ArgumentParser()
    command.set_defaults(relaxed_host_checks=False)
    runtime.add_configuration(command)
    return command.parse_args(['--profile', P['profile'], '--resources', P['resources']])


def snapshot():
    return {'temperature_c': temperatures(), 'cpu_ticks': Path('/proc/stat').read_text().splitlines()[:13],
            'ac_online': {p.name: p.read_text().strip() for p in sorted(Path('/sys/class/power_supply').glob('*/online'))}}


def sealed_inputs():
    manifest = runtime.verify_build(BUILD)
    require(manifest['source_revision'] == P['integrated_revision'] and manifest['backend'] == P['build_backend'],
            'Unexpected integrated source or backend')
    effective = runtime.resolve(options(), manifest)
    require(effective['cpus'] == CPUS and effective['scheduler'] == P['scheduler'] and
            all(effective[key] == value for key, value in P['effective'].items()), 'Integrated profile differs from protocol')
    frozen = read(OLD / 'identity.json')
    require(frozen['B0']['source_revision'] == P['original_revision'], 'Wrong original source revision')
    old_cases = read(OLD / 'cases.json')
    arms = {}
    for name in ('B0', 'A'):
        case = old_cases[name]
        artifacts = case['artifacts']
        require(all(sha(Path(path)) == digest for path, digest in artifacts.items()), f'Preserved {name} artifact changed')
        arms[name] = {'binary': case['server_argv'][0], 'artifacts': artifacts, 'source_revision': frozen[name]['source_revision'],
                      'env': {key: value for key, value in case['server_env'].items() if key.startswith(('NEWA_', 'GGML_NEWA_'))}}
    arms['I'] = {'binary': str(BUILD / 'bin/llama-server'), 'artifacts': {str(BUILD / 'bin' / name): digest
                                                                     for name, digest in manifest['artifacts'].items()},
                 'source_revision': manifest['source_revision']}
    return {'build': manifest, 'effective': {key: value for key, value in effective.items() if key != 'run_id'}, 'arms': arms}


def command_for(arm, binary, port, parallel):
    command = ['taskset', '-c', ','.join(map(str, CPUS)), binary, '--model', str(MODEL), '--host', '127.0.0.1',
               '--port', str(port), '-ngl', '0', '--threads', '5', '--threads-batch', '6', '--threads-http', '8',
               '--ctx-size', '8192', '--parallel', str(parallel), '--batch-size', '512', '--ubatch-size', '256',
               '--flash-attn', 'on', '--no-kv-unified', '--spec-type', 'none', '--no-ui', '--offline', '--perf']
    if arm in ('A', 'I'):
        command += ['--server-compute-profile-mode', 'phase']
    if arm == 'I':
        command += runtime.mixed_prefill_arguments(P['effective'])
    return command


def env_for(arm, identity):
    case = identity['arms'][arm]
    if arm == 'I':
        effective = identity['effective'] | {'run_id': secrets.randbits(63) or 1}
        return runtime.environment(options(), effective, BUILD)
    return clean_env() | {'LD_LIBRARY_PATH': str(Path(case['binary']).parent), 'OMP_NUM_THREADS': '6',
                          'OMP_DYNAMIC': 'FALSE'} | case['env']


def verify_loaded(arm, pid, identity):
    case = identity['arms'][arm]
    executable = Path(f'/proc/{pid}/exe').resolve()
    require(executable == Path(case['binary']).resolve(), f'{arm}: unexpected executable')
    libraries = runner.loaded_libraries(pid)
    if arm == 'I':
        return runtime.verify_loaded(BUILD, identity['build'], identity['effective'], MODEL, pid, libraries)
    actual = {Path(row['path']): row['sha256'] for row in libraries if 'sha256' in row}
    actual[executable] = sha(executable)
    for path, digest in case['artifacts'].items():
        expected = Path(path)
        require(any(found_hash == digest and expected.samefile(found) for found, found_hash in actual.items()),
                f'{arm}: sealed ELF not loaded: {expected.name}')
    require(any(path.name.startswith('libgomp.so') for path in actual), f'{arm}: OpenMP not loaded')
    require(any(line.split(maxsplit=5)[-1] == str(MODEL) for line in Path(f'/proc/{pid}/maps').read_text().splitlines()),
            f'{arm}: original model was not mapped')
    workers = {}
    for task in Path(f'/proc/{pid}/task').iterdir():
        try:
            tid = int(task.name)
            workers[task.name] = {'cpus': sorted(os.sched_getaffinity(tid)), 'scheduler': os.sched_getscheduler(tid)}
        except ProcessLookupError:
            continue
    require(workers and all(row == {'cpus': CPUS, 'scheduler': os.SCHED_OTHER} for row in workers.values()),
            f'{arm}: worker scheduler or mask changed')
    return {'loaded_libraries': libraries, 'workers': workers, 'model': str(MODEL)}


def new_fixtures(identity, reference):
    binary = identity['arms']['B0']['binary']
    port = runner.free_port()
    argv = command_for('B0', binary, port, parallel=1) + ['--no-warmup']
    server = runner.Server(argv, port, DATA / 'tokenizer.log', cleanup_timeout=15, env=env_for('B0', identity))
    fixtures = {}
    seen = {tuple(request['prompt']) for fixture in reference for request in fixture['requests']}
    try:
        server.start(120, CANCEL)
        verify_loaded('B0', server.process.pid, identity)
        for name, topics, template in zip(P['new_cohorts'], TOPICS, reference, strict=True):
            fixture = copy.deepcopy(template)
            fixture['id'] = name
            fixture['oracle'] = None
            for index, (topic, item, request) in enumerate(zip(topics, fixture['items'], fixture['requests'], strict=True)):
                text = (f'Prepare a practical briefing on {topic} for a group of volunteers. Start with the most pressing issue. '
                        f'The temporary records refer to zone {index + 11}, a review meeting next Wednesday, and a second inspection '
                        'at the end of the month. Describe the checks that should be completed before the meeting, the information '
                        'that should be carried forward, and a clear way to identify an unresolved item. Include distinct examples '
                        'for preparation, follow-up, and a final review. Finish with a short checklist for the coordinator. '
                        'Use numbered steps so the next shift can take over. Include the purpose of each step, how it should be '
                        'recorded, and which details must be escalated to the project lead before the next briefing.\n')
                ids = runner.json_request(port, 'POST', '/tokenize', {'content': text, 'add_special': True}, timeout=15)['tokens']
                length = len(request['prompt'])
                require(len(ids) >= length and tuple(ids[:length]) not in seen, f'{name}: prompt length or distinctness failed')
                request['prompt'] = ids[:length]
                item.update(id=f'{name}-{index + 1}', prompt=text)
                seen.add(tuple(request['prompt']))
            fixtures[name] = fixture
    finally:
        server.stop()
    require(server.cleanup['returncode'] == 0 and not server.cleanup['forced_leader_kill'], 'Tokenizer cleanup failed')
    return fixtures


def schedule(campaign):
    blocks = []
    for condition in P['condition_order'][campaign - 1]:
        for index in range(4):
            for cohort_index, cohort in enumerate(P['new_cohorts']):
                order = P['orders_per_cohort'][cohort_index][index]
                if (campaign == 2) != (condition == 'cpu25'):
                    order = order[::-1]
                blocks.append({'condition': condition, 'cohort': cohort, 'order': order, 'block': index * 2 + cohort_index + 1})
    return blocks


def prepare(identity):
    DATA.mkdir()
    all_ref = {fixture['id']: fixture for fixture in read(OLD / 'fixtures.json')}
    reference = [all_ref[name] for name in P['reference_fixtures']]
    fixtures = {fixture['id']: fixture for fixture in reference} | new_fixtures(identity, reference)
    runner.write_json(DATA / 'fixtures.json', fixtures)
    runner.write_json(DATA / 'order.json', {str(index): schedule(index) for index in (1, 2)})
    files = (HERE / 'study.py', HERE / 'analyze.py', HERE / 'protocol.json', DATA / 'fixtures.json', DATA / 'order.json',
             OLD / 'code/contention.py', OLD / 'code/load.py')
    runner.write_json(DATA / 'frozen.json', {'files': {str(file): sha(file) for file in files}, 'identity': identity,
                                            'model_sha256': sha(MODEL), 'kernel': os.uname().release})


def observe(port, pid, load, payload, fixture, folder, exposure):
    guard()
    before_env = snapshot()
    before = contention.read_process(pid)
    before_load = load.snapshot() if load else None
    start = time.monotonic_ns()
    response = runner.json_request(port, 'POST', '/completion', payload, timeout=180)
    end = time.monotonic_ns()
    after_load = load.snapshot() if load else None
    after = contention.read_process(pid)
    after_env = snapshot()
    path = folder / f'{exposure}-response.json'
    runner.write_json(path, response)
    wall = (end - start) / 1e9
    evidence = {'start_ns': start, 'end_ns': end, 'server_before': before, 'server_after': after,
                'environment_before': before_env, 'environment_after': after_env}
    if load:
        evidence.update(load_before=before_load, load_after=after_load, load=contention.metrics(before_load, after_load, wall))
    runner.write_json(folder / f'{exposure}-window.json', evidence)
    validate_body(response, fixture, TOKENS)
    require(all(before[key] == after[key] for key in ('pid', 'starttime', 'affinity', 'policy')), 'Server identity changed')
    require(before['affinity'] == CPUS and before['policy'] == os.SCHED_OTHER, 'Server left the resource envelope')
    if load and exposure == 'measured':
        limits = P['cpu25']
        require(limits['minimum'] <= evidence['load']['mean_cpu_cores'] <= limits['maximum'], 'cpu25 consumption outside protocol')


def visit(arm, identity, fixture, directory, condition):
    require(not runner.existing_servers(Path(identity['arms'][arm]['binary'])), 'Another model server is active')
    guard()
    directory.mkdir()
    port = runner.free_port()
    command = command_for(arm, identity['arms'][arm]['binary'], port, P['request_count'])
    env = env_for(arm, identity)
    payload = payload_for(fixture, TOKENS)
    runner.write_json(directory / 'launch.json', {'argv': command, 'env': env, 'payload': payload})
    log = directory / 'server.log'
    server = runner.Server(command, port, log, cleanup_timeout=15, env=env)
    ctx = contention.ControlledLoad(directory / 'cpu25', P['cpu25']['cpu']) if condition == 'cpu25' else nullcontext(None)
    try:
        with ctx as load:
            if load:
                time.sleep(0.5)
            server.start(120, CANCEL)
            pid = server.process.pid
            runner.write_json(directory / 'runtime-start.json', verify_loaded(arm, pid, identity))
            if arm == 'I':
                runtime.verify_effective(log.read_text(), identity['effective'])
            for item, request in zip(fixture['items'], fixture['requests'], strict=True):
                ids = runner.json_request(port, 'POST', '/tokenize', {'content': item['prompt'], 'add_special': True}, timeout=15)['tokens']
                require(ids[:len(request['prompt'])] == request['prompt'], f'{arm}: fixture tokenizer differs')
            for window in ('warmup', 'measured'):
                observe(port, pid, load, payload, fixture, directory, window)
            runner.write_json(directory / 'runtime-end.json', verify_loaded(arm, pid, identity))
    finally:
        server.stop()
        runner.write_json(directory / 'cleanup.json', server.cleanup)
    require(server.cleanup['returncode'] == 0 and not server.cleanup['forced_leader_kill'], f'{arm}: abnormal server cleanup')
    if arm == 'I':
        log_text = log.read_text()
        startup = runtime.verify_effective(log_text, identity['effective'])
        require('mode=phase_batch prefill_reference=1' in log_text, 'Integrated R reference path absent')
        runner.write_json(directory / 'integrated-proof.json', {'role_pool': startup, 'R_reference': True,
                                                               'pressure_lines': [line for line in log_text.splitlines()
                                                                                  if re.search(r'pressure|NEWA_E', line)]})
    guard()


def run(identity, name, plan):
    fixtures = read(DATA / 'fixtures.json')
    parent = DATA / name
    parent.mkdir(exist_ok=True)
    for spec in plan:
        block = parent / f'{spec["condition"]}-{spec["block"]:02d}'
        result = block / 'result.json'
        if result.exists():
            continue
        if block.exists():
            runner.write_json(result, {'spec': spec, 'status': 'interrupted', 'arms': {}})
            continue
        guard()
        block.mkdir()
        runner.write_json(block / 'planned.json', spec)
        statuses = {}
        for arm in spec['order']:
            guard()
            print(name, spec['condition'], spec['block'], spec['cohort'], arm, 'starting', flush=True)
            try:
                visit(arm, identity, fixtures[spec['cohort']], block / arm, spec['condition'])
                statuses[arm] = 'ok'
            except (RuntimeError, OSError, ValueError, KeyError) as exc:
                statuses[arm] = {'error': str(exc)}
                print(name, spec['condition'], spec['block'], arm, 'failed:', exc, flush=True)
        runner.write_json(result, {'spec': spec, 'status': 'finished', 'arms': statuses})
        print(name, spec['condition'], spec['block'], 'complete', statuses, flush=True)


def main():
    cli = ArgumentParser(description="기존 AMD 장비의 원본 런타임 비교 실험")
    cli.add_argument('action', choices=('prepare', 'smoke', 'confirm-1', 'confirm-2'))
    action = cli.parse_args().action

    def stop(_signum, _frame):
        CANCEL.set()
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    require((PRESERVED / 'state/.measurement.lock').is_file(), '원본 AMD 캠페인은 보존된 B0/A 런타임이 필요합니다. 새 장비에서는 공통 스크립트를 실행하세요.')
    with (PRESERVED / 'state/.measurement.lock').open('r') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        guard()
        require(os.sched_getscheduler(0) == os.SCHED_OTHER and P['controller_cpu'] in os.sched_getaffinity(0),
                'Controller CPU or policy unavailable')
        identity = sealed_inputs()
        require(sha(MODEL) == P['model_sha256'], 'Original model hash changed')
        os.sched_setaffinity(0, {P['controller_cpu']})
        if action == 'prepare':
            prepare(identity)
            return
        seal = read(DATA / 'frozen.json')
        require(identity == seal['identity'] and seal['kernel'] == os.uname().release and
                all(sha(Path(path)) == digest for path, digest in seal['files'].items()), 'Frozen campaign inputs changed')
        if action == 'smoke':
            run(identity, action, [{'condition': condition, 'cohort': cohort, 'order': list(ARMS), 'block': 1}
                                   for condition, cohort in zip(('ambient', 'cpu25'), P['reference_fixtures'], strict=True)])
            return
        require(all(read(DATA / 'smoke' / f'{condition}-01/result.json')['arms'] == dict.fromkeys(ARMS, 'ok')
                    for condition in ('ambient', 'cpu25')),
                'Historical fixture smoke has technical failures')
        run(identity, action, read(DATA / 'order.json')[action[-1]])


if __name__ == '__main__':
    main_entry(main)
