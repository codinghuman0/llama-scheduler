# SPDX-License-Identifier: GPL-2.0
"""Keep Firefox/Codex closed from Phase A through Phase D; use one terminal/TTY. Only campaign() issues completion requests."""
import argparse
import datetime
import hashlib
import http.client
import json
import math
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time

from common import (BENCH, BOOT_ID, HOUSE_CPUS, HOST, PROFILE_PATH, THREADS, UID, MIN_FREE, MODEL, PORT, PROMPT, PROMPT_SHA, REPO, REQUEST,
                    REQUEST_SHA, RESULTS, REVISIONS, SCHED, SCHED_HASHES, SERVER_CPUS, TAGS,
                    active_run, bundle_env, canonical, command, helper_request, identity,
                    live_project_processes, locked, model_identity, order, port_free,
                    project_objects, protocol_identity, read_json, repo_check, require,
                    same_process, scheduler_check, sha, signal_exact, state, topology,
                    validate_response, wait_gone, write_json)
import common
import host_profile
import analysis
import machine

CMAKE_OPTIONS = [
    '-G', 'Unix Makefiles', '-DCMAKE_C_COMPILER=/usr/bin/cc', '-DCMAKE_CXX_COMPILER=/usr/bin/c++',
    '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_C_FLAGS=', '-DCMAKE_CXX_FLAGS=',
    '-DCMAKE_EXPORT_COMPILE_COMMANDS=ON', '-DBUILD_SHARED_LIBS=ON',
    '-DGGML_CPU=ON', '-DGGML_NATIVE=ON', '-DGGML_OPENMP=ON', '-DGGML_CPU_REPACK=ON', '-DGGML_LLAMAFILE=ON',
    '-DGGML_BACKEND_DL=OFF', '-DGGML_CPU_ALL_VARIANTS=OFF', '-DGGML_BLAS=OFF', '-DGGML_CUDA=OFF',
    '-DGGML_VULKAN=OFF', '-DGGML_METAL=OFF', '-DGGML_HIP=OFF', '-DGGML_SYCL=OFF', '-DGGML_OPENCL=OFF',
    '-DGGML_RPC=OFF', '-DGGML_LTO=OFF', '-DGGML_CCACHE=OFF', '-DLLAMA_BUILD_COMMON=ON',
    '-DLLAMA_BUILD_TOOLS=ON', '-DLLAMA_BUILD_SERVER=ON', '-DLLAMA_BUILD_TESTS=OFF', '-DLLAMA_BUILD_EXAMPLES=OFF',
    '-DLLAMA_BUILD_APP=OFF', '-DLLAMA_BUILD_UI=OFF', '-DLLAMA_USE_PREBUILT_UI=OFF', '-DLLAMA_BUILD_MTMD=OFF',
    '-DLLAMA_OPENSSL=OFF', '-DLLAMA_SUBPROCESS=ON', '-DLLAMA_USE_SYSTEM_GGML=OFF',
]
BUILD_JOBS = 2


def sources():
    return {p.name: sha(p) for p in sorted(BENCH.glob('*.py'))} | {p.name: sha(p) for p in sorted(BENCH.glob('*.sh'))}


def change_status(run, status, **extra):
    manifest = read_json(run / 'manifest.json')
    manifest.update(status=status, **extra)
    write_json(run / 'manifest.json', manifest)


def require_status(run, expected):
    manifest = read_json(run / 'manifest.json')
    hint = (' No campaign has completed. Phase D must run only after Phase C prints CAMPAIGN_COMPLETE.'
            if expected == {'CAMPAIGN_COMPLETE'} else '')
    require(manifest['status'] in expected, f"Phase not allowed in state {manifest['status']}." + hint)
    require(manifest['helper_sources'] == sources(), 'Campaign automation changed after preparation')
    require(manifest['protocol'] == protocol_identity(), 'Protocol changed after preparation')
    require(manifest['head'] == repo_check(), 'Campaign repository revision changed')
    verify_profile(run, manifest)
    return manifest


def verify_profile(run, manifest):
    require(sha(PROFILE_PATH) == sha(run / 'host-profile.json') == manifest['host_profile_sha256'], 'Frozen host profile changed')
    require(read_json(run / 'host-profile.json') == HOST, 'Campaign host profile differs')
    host_profile.validate_current(HOST)
    scheduler_check()


def audit_command(run, argv, **kwargs):
    with open(run / 'commands.jsonl', 'ab') as log:
        log.write(canonical(dict(argv=[str(a) for a in argv], cwd=str(kwargs.get('cwd', REPO)))))
    return command(argv, **kwargs)


def free_space(path):
    free = shutil.disk_usage(path).free
    require(free >= MIN_FREE, f'Free disk below reserved 512 MiB: {free} bytes')
    return free


def dependencies(server, env):
    output = command(['/usr/bin/ldd', server], env=env)
    require('not found' not in output, 'Runtime dependency unresolved')
    paths = re.findall(r'=> (/\S+) \(', output)
    return output, [Path(p).resolve() for p in paths]


def toolchain():
    versions = {name: command([path, '--version']) for name, path in
                [('cc', '/usr/bin/cc'), ('c++', '/usr/bin/c++'), ('cmake', '/usr/bin/cmake'), ('make', '/usr/bin/make')]}
    return dict(versions=versions, compiler_hashes={p: sha(p) for p in ('/usr/bin/cc', '/usr/bin/c++')})


def toolchain_identity(tools):
    # Translated license text is not a build identity.
    return dict(compiler_hashes=tools['compiler_hashes'],
                versions={name: text.splitlines()[0] for name, text in tools['versions'].items()})


def validate_entry_points():
    for path in sorted(BENCH.glob('*.py')):
        compile(path.read_text(), str(path), 'exec')
    wrappers = sorted(BENCH.glob('step10_phase_*.sh'))
    require(len(wrappers) == 4, 'Expected exactly four phase scripts')
    for path in wrappers:
        command(['bash', '-n', path])
        plan = json.loads(command([path, '--dry-run']))
        require(plan['dry_run'] and plan['server_cpus'] == sorted(SERVER_CPUS), 'Entry point dry-run differs')


def require_no_helper():
    rows = command(['ps', '-eo', 'pid=,args=']).splitlines()
    require(not any(str(BENCH / 'root_helper.py') in row for row in rows), 'Another campaign root helper is active')


def build_bundle(run, config):
    temp = run / '.prepare' / config
    temp.mkdir(parents=True)
    source, build = temp / 'source', temp / 'build'
    metadata = run / 'builds' / config
    metadata.mkdir(parents=True)
    free_space(run)
    revision = REVISIONS[config]
    audit_command(run, ['git', 'worktree', 'add', '--detach', source, revision], log=metadata / 'worktree.log')
    require(command(['git', 'rev-parse', 'HEAD'], cwd=source) == revision, 'Build source revision mismatch')
    env = bundle_env(temp)
    env.pop('LD_LIBRARY_PATH')
    argv = ['cmake', '-S', str(source), '-B', str(build)] + CMAKE_OPTIONS
    if config != 'A':
        argv += ['-DLLAMA_SCX_PHASE_HINT=' + ('ON' if config == 'C' else 'OFF'), '-DLLAMA_SCX_PHASE_TRACE=OFF']
    write_json(metadata / 'configure-command.json', argv)
    audit_command(run, argv, env=env, log=metadata / 'configure.log', capture=False)
    audit_command(run, ['cmake', '--build', build, '--target', 'llama-server', '--parallel', str(BUILD_JOBS)], env=env, log=metadata / 'build.log', capture=False)
    free_space(run)
    cache = (build / 'CMakeCache.txt').read_text()
    cache_values = dict(re.findall(r'^([^/#\n][^:\n]*):[^=\n]+=(.*)$', cache, re.M))
    for option in CMAKE_OPTIONS:
        if option.startswith('-D'):
            key, value = option[2:].split('=', 1)
            require(cache_values.get(key) == value, f'Unexpected CMake option: {key}')
    require(cache_values.get('CMAKE_CXX_FLAGS_RELEASE') == '-O3 -DNDEBUG', 'Release optimization differs')
    commands = (build / 'compile_commands.json').read_text()
    require('-march=native' in commands and '-O3' in commands and '-DNDEBUG' in commands, 'Native Release flags absent')
    require(not any(flag in commands for flag in ('-fsanitize=', '-pg ', '-flto')), 'Unexpected instrumentation/LTO')
    if config != 'A':
        require(cache_values['LLAMA_SCX_PHASE_HINT'] == ('ON' if config == 'C' else 'OFF') and cache_values['LLAMA_SCX_PHASE_TRACE'] == 'OFF', 'Hint/TRACE configuration mismatch')
    for filename in ('CMakeCache.txt', 'compile_commands.json'):
        shutil.copy2(build / filename, metadata / filename)
    short_revision = command(['git', 'rev-parse', '--short', 'HEAD'], cwd=source)
    info = (build / 'common/build-info.cpp').read_text()
    require(short_revision in info, 'Generated build-info revision is stale')
    (metadata / 'build-info.cpp').write_text(info)
    bundle = run / 'artifacts' / config
    (bundle / 'bin').mkdir(parents=True)
    server = build / 'bin/llama-server'
    original_ldd, libraries = dependencies(server, env)
    shutil.copy2(server, bundle / 'bin/llama-server')
    project_libraries = {p for p in libraries if p.is_relative_to(build)}
    for library in project_libraries:
        shutil.copy2(library, bundle / 'bin' / library.name)
    # Keep SONAME/unversioned aliases, with one physical copy per library.
    for alias in (build / 'bin').iterdir():
        if alias.is_symlink() and alias.resolve() in project_libraries:
            (bundle / 'bin' / alias.name).symlink_to(alias.resolve().name)
    runtime_env = bundle_env(bundle)
    ldd, bundled_libraries = dependencies(bundle / 'bin/llama-server', runtime_env)
    require(not any(p.is_relative_to(temp) for p in bundled_libraries), 'Bundle still depends on temporary build')
    for p in bundled_libraries:
        if p.name.startswith(('libggml', 'libllama', 'libmtmd')):
            require(p.is_relative_to(bundle), 'Cross-build project library resolution')
    version = audit_command(run, ['/usr/bin/taskset', '-c', ','.join(map(str, sorted(SERVER_CPUS))), bundle / 'bin/llama-server', '--version'], env=runtime_env, log=metadata / 'version.txt')
    require(short_revision in version, 'Server --version does not identify frozen revision')
    if config == 'C':
        symbols = command(['nm', '-D', bundle / 'bin/libllama-server-impl.so'])
        require(re.search(r'\bT llama_scx_phase_v1$', symbols, re.M), 'C marker missing from DSO')
    elf = {p.name: command(['readelf', '-n', p]) for p in sorted((bundle / 'bin').iterdir())}
    dynamic = {p.name: command(['readelf', '-d', p]) for p in sorted((bundle / 'bin').iterdir())}
    record = dict(revision=revision, hint='absent' if config == 'A' else 'ON' if config == 'C' else 'OFF', trace='absent' if config == 'A' else 'OFF',
                  configure_argv=argv, cache_subset=cache_values, version=version, elf_notes=elf, elf_dynamic=dynamic,
                  original_ldd=original_ldd, bundle_ldd=ldd,
                  system_libraries={str(p): sha(p) for p in bundled_libraries if not p.is_relative_to(bundle)},
                  symlinks={str(p.relative_to(bundle)): os.readlink(p) for p in (bundle / 'bin').iterdir() if p.is_symlink()},
                  files={str(p.relative_to(bundle)): sha(p) for p in sorted((bundle / 'bin').iterdir())})
    write_json(metadata / 'identity.json', record)
    # Only this campaign's worktree/build may be removed, after bundle validation.
    audit_command(run, ['git', 'worktree', 'remove', '--force', source])
    shutil.rmtree(build)
    temp.rmdir()
    free_space(run)
    return record


def validate_artifacts(run, *, model=False, offline=False):
    artifacts = read_json(run / 'artifacts.json')
    for config in 'ABC':
        require(artifacts[config]['revision'] == REVISIONS[config], 'Artifact source mismatch')
        bundle = run / 'artifacts' / config
        require({str(p.relative_to(bundle)) for p in (bundle / 'bin').iterdir()} == set(artifacts[config]['files']), 'Bundle file set changed')
        for name, digest in artifacts[config]['files'].items():
            require(sha(bundle / name) == digest, f'Bundle hash changed: {config}/{name}')
        links = {str(p.relative_to(bundle)): os.readlink(p) for p in (bundle / 'bin').iterdir() if p.is_symlink()}
        require(links == artifacts[config]['symlinks'], 'Runtime SONAME aliases changed')
        if not offline:
            for name, digest in artifacts[config]['system_libraries'].items():
                require(sha(name) == digest, 'System runtime library changed')
    require(artifacts['D']['reuse'] == 'C' and artifacts['D']['files'] == artifacts['C']['files'], 'D does not reuse exact C bytes')
    if not offline:
        scheduler_check()
    require(artifacts['D']['scheduler_hashes'] == SCHED_HASHES, 'Recorded scheduler hashes differ')
    require(sha(run / 'workload/prompt.txt') == PROMPT_SHA and sha(run / 'workload/request.json') == REQUEST_SHA, 'Frozen request identity changed')
    if model:
        model_identity()
    return artifacts


def unused_preparation(run, manifest):
    return (manifest['status'] == 'PREPARED' and (run / 'raw').is_dir() and not any((run / 'raw').iterdir())
            and not (run / 'armed.json').exists() and not (run / 'CAMPAIGN_COMPLETE').exists())


def replaceable_campaign(run):
    manifest = read_json(run / 'manifest.json')
    return manifest['status'] in {'FAILED', 'FINALIZED', 'SUPERSEDED'} or unused_preparation(run, manifest)


def reuse_bundles(run, previous, tools):
    old = read_json(previous / 'manifest.json')
    require(replaceable_campaign(previous), 'Only closed or unused PREPARED campaigns may provide reusable bundles')
    require(toolchain_identity(old['toolchain']) == toolchain_identity(tools) and old['tags'] == TAGS and old['topology'] == topology()
            and old['request_sha256'] == REQUEST_SHA and old['prompt_sha256'] == PROMPT_SHA
            and old['metrics'] == list(analysis.METRICS) and old['warmups_per_visit'] == 2 and old['measured_per_config'] == 10
            and old['bootstrap_seed'] == 20261006 and old['bootstrap_draws'] == 10000
            and old['order'] == order() and old['scheduler_hashes'] == SCHED_HASHES and old['uid'] == UID
            and sha(previous / 'protocol.md') == old['protocol']['sha256'], 'Reusable build/toolchain/measurement identity differs')
    artifacts = validate_artifacts(previous)
    for cfg in 'ABC':
        record = artifacts[cfg]
        expected = 'absent' if cfg == 'A' else 'ON' if cfg == 'C' else 'OFF'
        require(record['hint'] == expected and record['trace'] == ('absent' if cfg == 'A' else 'OFF'), 'Reusable hint/TRACE configuration differs')
        options = CMAKE_OPTIONS + ([] if cfg == 'A' else ['-DLLAMA_SCX_PHASE_HINT=' + expected, '-DLLAMA_SCX_PHASE_TRACE=OFF'])
        require(record['configure_argv'][5:] == options, 'Reusable configure command differs')
        for option in options:
            if option.startswith('-D'):
                key, value = option[2:].split('=', 1)
                require(record['cache_subset'].get(key) == value and option in record['configure_argv'], 'Reusable build option differs: ' + key)
        require(record['cache_subset'].get('CMAKE_CXX_FLAGS_RELEASE') == '-O3 -DNDEBUG', 'Reusable Release flags differ')
        # Runtime bytes are immutable. Hardlinks avoid another full bundle copy.
        shutil.copytree(previous / 'artifacts' / cfg, run / 'artifacts' / cfg, symlinks=True, copy_function=os.link)
        shutil.copytree(previous / 'builds' / cfg, run / 'builds' / cfg)
        for name, digest in record['files'].items():
            require(sha(run / 'artifacts' / cfg / name) == digest, 'Reused runtime bytes differ')
        require(read_json(run / 'builds' / cfg / 'identity.json') == record, 'Saved build metadata differs')
        bundle = run / 'artifacts' / cfg
        env = bundle_env(bundle)
        ldd, libraries = dependencies(bundle / 'bin/llama-server', env)
        require(all(p.is_relative_to(bundle) for p in libraries if p.name.startswith(('libllama', 'libggml', 'libmtmd'))),
                'Reused bundle resolves a project library outside the new bundle')
        version = audit_command(run, ['/usr/bin/taskset', '-c', ','.join(map(str, sorted(SERVER_CPUS))), bundle / 'bin/llama-server', '--version'], env=env)
        require(version == record['version'], 'Reused server version differs')
        write_json(run / 'builds' / cfg / 'reuse-validation.json', dict(bundle_ldd=ldd, version=version))
    write_json(run / 'artifacts.json', artifacts)
    write_json(run / 'reused-artifacts.json', dict(source=str(previous), source_head=old['head'], source_protocol=old['protocol'],
                                                files={cfg: artifacts[cfg]['files'] for cfg in 'ABC'}))
    return artifacts


def prepare(*, reuse_artifacts=False):
    head = repo_check()
    scheduler_check()
    require(state() == 'disabled' and not live_project_processes(), 'Project runtime is active')
    host_profile.validate_current(HOST)
    hardware = topology()
    model = model_identity()
    tools = toolchain()
    validate_entry_points()
    require_no_helper()
    RESULTS.mkdir(parents=True, exist_ok=True)
    pointer = RESULTS / '.active-run'
    previous_run = None
    if pointer.exists():
        previous_run = active_run()
        require(replaceable_campaign(previous_run), 'Previous campaign is armed/running or contains requests; do not replace it')
    require(not reuse_artifacts or previous_run is not None, 'No previous campaign bundles to reuse')
    name = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    run = RESULTS / name
    suffix = 0
    while run.exists():
        suffix += 1
        run = RESULTS / f'{name}-{suffix}'
    run.mkdir()
    if previous_run:
        with locked(previous_run):
            previous = read_json(previous_run / 'manifest.json')
            require(replaceable_campaign(previous_run), 'Previous campaign state changed')
            if unused_preparation(previous_run, previous):
                change_status(previous_run, 'SUPERSEDED', replacement=run.name,
                              reason='Unused preparation replaced before arming or requests; original artifacts/evidence retained')
    (RESULTS / '.active-run.tmp').write_text(run.name + '\n')
    os.replace(RESULTS / '.active-run.tmp', pointer)
    for directory in ('workload', 'raw'):
        (run / directory).mkdir()
    shutil.copy2(PROFILE_PATH, run / 'host-profile.json')
    shutil.copy2(REPO / 'tools/sched_ext/BENCHMARK_PROTOCOL.md', run / 'protocol.md')
    (run / 'workload/prompt.txt').write_bytes(PROMPT.encode())
    (run / 'workload/request.json').write_bytes(canonical(REQUEST))
    write_json(run / 'visit-order.json', order())
    manifest = dict(schema=1, status='PREPARING', run_id=run.name, head=head, tags=TAGS,
                    uid=UID, host_profile_sha256=sha(run / 'host-profile.json'), model=model, topology=hardware, toolchain=tools, order=order(),
                    protocol=protocol_identity(), helper_sources=sources(), scheduler_hashes=SCHED_HASHES,
                    request_sha256=REQUEST_SHA, prompt_sha256=PROMPT_SHA,
                    clock=vars(time.get_clock_info('perf_counter')), kernel=os.uname().release,
                    boot_id=BOOT_ID.read_text().strip(), btf_sha256=sha('/sys/kernel/btf/vmlinux'),
                    metrics=list(analysis.METRICS), warmups_per_visit=2, measured_per_config=10,
                    bootstrap_seed=20261006, bootstrap_draws=10000, quiet_all_phases=True, build_jobs=BUILD_JOBS)
    write_json(run / 'manifest.json', manifest)
    try:
        with locked(run):
            artifacts = (reuse_bundles(run, previous_run, tools) if reuse_artifacts else
                         {cfg: build_bundle(run, cfg) for cfg in 'ABC'})
            baseline_cache = artifacts['A']['cache_subset']
            for cfg in 'BC':
                for option in CMAKE_OPTIONS:
                    if option.startswith('-D'):
                        key = option[2:].split('=')[0]
                        require(artifacts[cfg]['cache_subset'][key] == baseline_cache[key], 'Cross-build CMake options differ')
            artifacts['D'] = dict(reuse='C', files=artifacts['C']['files'], revision=REVISIONS['C'], scheduler_revision=TAGS['neutral-sched-ext-base-v1'], scheduler_hashes=SCHED_HASHES)
            write_json(run / 'artifacts.json', artifacts)
            validate_artifacts(run)
            require(repo_check() == head and state() == 'disabled', 'Preparation altered repository/scheduler state')
            change_status(run, 'PREPARED')
    except BaseException as error:
        change_status(run, 'FAILED', error=str(error))
        raise
    print(f'Phase A complete: {run}\nKeep applications closed through Phase D.\nNext: ./tools/sched_ext/bench/step10_phase_b_arm.sh')


def arm():
    run = active_run()
    with locked(run):
        manifest = require_status(run, {'PREPARED'})
        validate_artifacts(run, model=True)
        require(state() == 'disabled' and not live_project_processes(), 'Runtime processes already active')
        require_no_helper()
        port_free()
        snapshot = machine.snapshot()
        machine.validate(snapshot)
        require(snapshot['kernel'] == manifest['kernel'] and snapshot['boot_id'] == manifest['boot_id'] and sha('/sys/kernel/btf/vmlinux') == manifest['btf_sha256'], 'Host ABI/boot changed since Phase A')
        write_json(run / 'machine.json', dict(before=snapshot))
        argv = ['sudo', '/usr/bin/taskset', '-c', ','.join(map(str, sorted(HOUSE_CPUS))), '/usr/bin/python3', '-I', '-B', str(BENCH / 'root_helper.py'), '--arm', str(run)]
        print('One privileged interaction; helper arms only, no scheduler load:\n' + shlex.join(argv), flush=True)
        ready = None
        try:
            ready = json.loads(audit_command(run, argv, log=run / 'arming-output.txt'))
            write_json(run / 'armed.json', ready)
            require(ready['helper']['uid'] == 0 and ready['helper']['policy'] == 0 and ready['helper']['affinity'] == sorted(HOUSE_CPUS), 'Helper identity differs')
            helper_request(run, 'HELLO')
            helper_request(run, 'CHECK')
            change_status(run, 'ARMED')
        except BaseException as error:
            if ready:
                try:
                    helper_request(run, 'ABORT')
                    wait_gone(ready['helper'])
                except Exception as cleanup:
                    write_json(run / 'arming-cleanup-error.json', dict(error=str(cleanup), helper=ready['helper']))
            change_status(run, 'FAILED', error=str(error))
            raise
    print('Phase B complete. Keep Firefox/Codex and unnecessary applications closed through Phase D.\n'
          'From the same terminal or TTY run: ./tools/sched_ext/bench/step10_phase_c_campaign.sh')


def server_argv(run, config):
    bundle = run / 'artifacts' / ('C' if config == 'D' else config)
    argv = [str(bundle / 'bin/llama-server'), '-m', str(MODEL), '--host', '127.0.0.1', '--port', str(PORT),
            '--n-gpu-layers', '0', '--threads', str(THREADS['compute']), '--threads-batch', str(THREADS['batch']), '--threads-http', '2',
            '--ctx-size', '2048', '--parallel', '1', '--batch-size', '512', '--ubatch-size', '256',
            '--flash-attn', 'off', '--no-ui']
    if config != 'A':
        argv += ['--server-compute-profile-mode', 'legacy']
    return argv, bundle


def health():
    client = http.client.HTTPConnection('127.0.0.1', PORT, timeout=2)
    try:
        client.request('GET', '/health', headers={'Connection': 'close'})
        response = client.getresponse()
        response.read()
        return response.status == 200
    except (ConnectionError, OSError, http.client.HTTPException):
        return False
    finally:
        client.close()


def policy_snapshot(server, launcher=None, loader=None, bundle=None):
    require(same_process(server), 'Selected server identity changed')
    rows = dict(server=identity(server['pid']), runner=identity(os.getpid()))
    require(rows['runner']['affinity'] == sorted(HOUSE_CPUS) and rows['runner']['policy'] == 0, 'Runner must stay normal on the housekeeping set')
    expected_policy = 7 if loader else 0
    tids = sorted(int(p.name) for p in Path(f"/proc/{server['pid']}/task").iterdir())
    rows['tids'] = [identity(tid) for tid in tids]
    require(all(p['uids'] == [UID]*4 and p['policy'] == expected_policy and set(p['affinity']) == SERVER_CPUS for p in rows['tids']), 'Server TID policy/affinity mismatch')
    require(os.getpriority(os.PRIO_PROCESS, server['pid']) == 0, 'Server nice value differs')
    if launcher:
        require(same_process(launcher), 'Launcher identity changed')
        rows['launcher'] = identity(launcher['pid'])
        require(rows['launcher']['uid'] == UID and rows['launcher']['policy'] == 0 and rows['launcher']['affinity'] == sorted(HOUSE_CPUS), 'Launcher policy/affinity mismatch')
    if loader:
        require(same_process(loader), 'Loader exited during visit')
        rows['loader'] = identity(loader['pid'])
        require(rows['loader']['uid'] == 0 and rows['loader']['policy'] == 0 and rows['loader']['affinity'] == sorted(HOUSE_CPUS) and state() == 'enabled', 'Loader policy/affinity mismatch')
    else:
        require(state() == 'disabled', 'sched_ext active in default-Linux configuration')
    mappings = Path(f"/proc/{server['pid']}/maps").read_text()
    mapped = sorted(set(re.findall(r'(/\S+lib(?:llama|ggml|mtmd)[^\s]*)', mappings)))
    require(mapped and all(Path(p).resolve().is_relative_to(bundle) for p in mapped), 'Server mapped a project library outside its runtime bundle')
    rows['project_library_mappings'] = mapped
    return rows


def post_request(path, role, payload, expected_prompt):
    client = http.client.HTTPConnection('127.0.0.1', PORT, timeout=180)
    headers = {'Content-Type': 'application/json', 'Connection': 'close'}
    write_json(path / f'{role}-attempt.json', dict(role=role, endpoint=f'http://127.0.0.1:{PORT}/completion', request_sha256=REQUEST_SHA))
    # The entire timed region is a blocking POST and full body read.
    start = time.perf_counter_ns()
    try:
        client.request('POST', '/completion', body=payload, headers=headers)
        response = client.getresponse()
        body = response.read()
        end = time.perf_counter_ns()
    except Exception as error:
        write_json(path / f'{role}-client-error.json', dict(role=role, error=str(error), request_sha256=REQUEST_SHA))
        raise
    finally:
        client.close()
    (path / f'{role}-response.json').write_bytes(body)
    record = dict(role=role, request_sha256=hashlib.sha256(payload).hexdigest(), http_status=response.status,
                  response_sha256=hashlib.sha256(body).hexdigest(), request_wall_ms=(end-start)/1e6)
    write_json(path / f'{role}-client.json', record)
    value = json.loads(body)
    prompt_n = validate_response(value, response.status, expected_prompt)
    return prompt_n, value, record


def stop_process(process, saved):
    if process.poll() is None:
        signal_exact(saved, signal.SIGTERM)
        try:
            return process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            signal_exact(saved, signal.SIGKILL)
            process.wait(timeout=10)
            raise RuntimeError('Normal shutdown failed; emergency SIGKILL was required')
    return process.wait()


def registered_child(path, launcher, bundle):
    output = (path / 'server.stdout.log').read_text(errors='replace')
    match = re.search(r'phase_uprobe_registered_tgid=(\d+)', output)
    acknowledged = match is not None
    if not match:
        match = re.search(r'child_pid=(\d+)', output)
    if not match:
        return None, False
    server = identity(int(match.group(1)))
    executable = Path(f"/proc/{server['pid']}/exe").resolve()
    if not acknowledged and executable == SCHED / 'bin/llama_scx_child':
        return None, False
    require(server['ppid'] == launcher['pid'] and server['uids'] == [UID] * 4
            and executable == bundle / 'bin/llama-server', 'D child identity differs')
    log = path / 'loader.log'
    loader_output = log.read_text(errors='replace') if log.exists() else ''
    return server, acknowledged and f"registered tgid={server['pid']} uid={UID}" in loader_output


def visit(run, plan, baseline, prompt_count):
    config, number = plan['config'], plan['visit']
    path = run / 'raw' / f'{number:02d}-{config}'
    path.mkdir()
    write_json(path / 'visit.json', dict(**plan, status='STARTED', request_sha256=REQUEST_SHA))
    argv, bundle = server_argv(run, config)
    loader = launcher = server = process = None
    root_started = False
    cleanup = dict(status='PENDING')
    stdout = open(path / 'server.stdout.log', 'wb')
    stderr = open(path / 'server.stderr.log', 'wb')
    try:
        helper_request(run, 'CHECK')
        port_free()
        if config == 'D':
            registration = helper_request(run, 'START', visit=number)
            root_started = True
            loader = registration['loader']
            argv = [str(SCHED / 'bin/llama_scx_child'), '--phase-register-socket', registration['registration_socket'], '--'] + argv
            write_json(path / 'registration.json', registration)
        write_json(path / 'command.json', dict(argv=argv, affinity=sorted(SERVER_CPUS), compute_threads=THREADS['compute'],
                                               batch_threads=THREADS['batch'], http_threads=2, scheduler='sched_ext' if loader else 'Linux',
                                               revision=REVISIONS['C' if config == 'D' else config], bundle='C' if config == 'D' else config,
                                               runtime_environment=dict(OMP_NUM_THREADS=str(THREADS['compute']), OMP_DYNAMIC='FALSE', LD_LIBRARY_PATH=str(bundle / 'bin'))))
        process = subprocess.Popen(argv, env=bundle_env(bundle), stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                                   preexec_fn=lambda: os.sched_setaffinity(0, SERVER_CPUS))
        parent = identity(process.pid)
        if config == 'D':
            launcher = parent
            deadline = time.monotonic() + 30
            accepted = False
            while time.monotonic() < deadline:
                require(process.poll() is None, 'D launcher exited during registration')
                candidate, accepted = registered_child(path, launcher, bundle)
                if candidate:
                    server = candidate
                    write_json(path / 'processes.json', dict(server=server, launcher=launcher, loader=loader))
                if accepted:
                    # Child inherits server affinity; move only its parent after ACK.
                    os.sched_setaffinity(launcher['pid'], HOUSE_CPUS)
                    break
                time.sleep(0.05)
            require(server is not None and accepted, 'D registration deadline exceeded; see server and loader logs')
        else:
            server = parent
        write_json(path / 'processes.json', dict(server=server, launcher=launcher, loader=loader))
        deadline = time.monotonic() + 180
        while not health():
            require(process.poll() is None and time.monotonic() < deadline, 'Server readiness failed')
            time.sleep(0.25)
        write_json(path / 'policies-before.json', policy_snapshot(server, launcher, loader, bundle))
        payload = (run / 'workload/request.json').read_bytes()
        require(hashlib.sha256(payload).hexdigest() == REQUEST_SHA, 'Request changed')
        for warmup in (1, 2):
            prompt_count, _, _ = post_request(path, f'warmup-{warmup}', payload, prompt_count)
        machine.readiness(path, 'readiness.json', baseline, after_warmup=True)
        write_json(path / 'policies-pre-measured.json', policy_snapshot(server, launcher, loader, bundle))
        before = machine.snapshot()
        write_json(path / 'system-before.json', before)
        machine.validate(before, baseline)
        prompt_count, measured, client = post_request(path, 'measured', payload, prompt_count)
        after = machine.snapshot()
        write_json(path / 'system-after.json', after)
        machine.validate(after, baseline)
        write_json(path / 'policies-after.json', policy_snapshot(server, launcher, loader, bundle))
        if launcher:
            signal_exact(server, signal.SIGTERM)
            exit_code = process.wait(timeout=20)
        else:
            exit_code = stop_process(process, server)
        require(exit_code == 0, f'Server/launcher shutdown returned {exit_code}')
        wait_gone(server)
        if root_started:
            root = helper_request(run, 'STOP', visit=number)
            require(root['loader_exit'] == 0 and not root['loader_sigterm_requested'], 'D loader did not exit naturally after target termination')
            wait_gone(root['loader'])
            cleanup['root'] = root
            root_started = False
        require(not live_project_processes() and state() == 'disabled', 'Project runtime survived visit cleanup')
        port_free()
        cleanup.update(status='PASS', server_launcher_exit=exit_code, sched_ext=state(), port_free=True)
        write_json(path / 'cleanup.json', cleanup)
        artifacts = read_json(run / 'artifacts.json')
        write_json(path / 'visit.json', dict(**plan, status='VALID', request_sha256=REQUEST_SHA,
                                           artifact_files=artifacts['C' if config == 'D' else config]['files'],
                                           prompt_n=prompt_count, measured_client=client, timings=measured['timings']))
        return prompt_count
    except BaseException as error:
        errors = []
        try:
            write_json(path / 'visit.json', dict(**plan, status='INVALID', error=str(error), request_sha256=REQUEST_SHA))
        except Exception as failure:
            errors.append('saving visit failure: ' + str(failure))
        if root_started:
            try:
                cleanup['root'] = helper_request(run, 'STOP', visit=number)
            except Exception as failure:
                errors.append('loader cleanup: ' + str(failure))
        try:
            if process:
                if launcher:
                    if server and same_process(server):
                        signal_exact(server, signal.SIGTERM)
                    try:
                        cleanup['server_launcher_exit'] = process.wait(timeout=20)
                    except subprocess.TimeoutExpired:
                        if server and same_process(server):
                            signal_exact(server, signal.SIGKILL)
                            cleanup['server_launcher_exit'] = process.wait(timeout=10)
                        raise RuntimeError('Launcher cleanup required emergency recovery; see processes.json')
                else:
                    cleanup['server_launcher_exit'] = (stop_process(process, server or identity(process.pid))
                                                       if process.poll() is None else process.wait())
            require(not live_project_processes() and state() == 'disabled', 'Project runtime survived emergency cleanup')
        except Exception as failure:
            errors.append('server/launcher cleanup: ' + str(failure))
        cleanup.update(status='FAILED' if errors else 'EMERGENCY', sched_ext=state())
        if errors:
            cleanup['errors'] = errors
        write_json(path / 'cleanup.json', cleanup)
        raise
    finally:
        stdout.close()
        stderr.close()


def campaign():
    run = active_run()
    with locked(run):
        manifest = require_status(run, {'ARMED'})
        machine.reject_interactive_apps()
        validate_artifacts(run, model=True)
        require(os.sched_getaffinity(0) == HOUSE_CPUS and os.sched_getscheduler(0) == 0, 'Campaign runner must be normal on the housekeeping set')
        require(not live_project_processes() and state() == 'disabled', 'Runtime already active')
        hello = helper_request(run, 'HELLO')
        require(hello['helper']['policy'] == 0 and hello['helper']['affinity'] == sorted(HOUSE_CPUS), 'Helper left the housekeeping core/normal policy')
        baseline = read_json(run / 'machine.json')['before']
        machine.validate(machine.snapshot(), baseline)
        require(sha('/sys/kernel/btf/vmlinux') == manifest['btf_sha256'], 'Host BTF changed')
        change_status(run, 'RUNNING')
        prompt_count = None
        plan = None
        try:
            for plan in order():
                if plan['position'] == 1:
                    processes = machine.reject_interactive_apps()
                    write_json(run / f"block-{plan['block']:02d}-processes.json", processes)
                    machine.readiness(run, f"block-{plan['block']:02d}-idle.json", baseline, after_warmup=False)
                print(f"Visit {plan['visit']:02d}/40: {plan['config']}", flush=True)
                prompt_count = visit(run, plan, baseline, prompt_count)
            validate_artifacts(run, model=True)
            final = helper_request(run, 'FINISH')
            helper = read_json(run / 'armed.json')['helper']
            wait_gone(helper)
            require(state() == 'disabled' and not live_project_processes(), 'Final runtime cleanup failed')
            port_free()
            end_machine = machine.snapshot()
            machine.validate(end_machine, baseline)
            write_json(run / 'machine.json', dict(before=baseline, after=end_machine))
            write_json(run / 'final-cleanup.json', dict(status='PASS', root=final, sched_ext=state(), port_free=True, helper_gone=True, no_project_processes=True,
                                                       artifacts_rehashed=True, model_after=model_identity(), scheduler_hashes=SCHED_HASHES))
            require(repo_check() == manifest['head'], 'Repository changed during campaign')
            change_status(run, 'CAMPAIGN_COMPLETE', prompt_n=prompt_count)
            (run / 'CAMPAIGN_COMPLETE').write_text('All 40 visits and cleanup gates passed.\n')
        except BaseException as error:
            try:
                helper = read_json(run / 'armed.json')['helper']
                if same_process(helper):
                    result = helper_request(run, 'ABORT')
                    write_json(run / 'abort-cleanup.json', result)
                    wait_gone(helper)
            except Exception as cleanup:
                write_json(run / 'abort-cleanup-error.json', dict(error=str(cleanup)))
            change_status(run, 'FAILED', error=str(error), invalid_block=plan['block'] if plan else None)
            raise
    print('CAMPAIGN_COMPLETE. Keep applications closed until Phase D finishes.\nNext: ./tools/sched_ext/bench/step10_phase_d_finalize.sh')


def check_ready():
    machine.reject_interactive_apps()
    require(not live_project_processes() and state() == 'disabled', 'Project runtime already active')
    port_free()
    machine.validate(machine.snapshot())
    print('Quiet-application/port/power/topology checks passed. No request issued. Phase C still checks load/temperature before timing.')


def collect_rows(run):
    manifest = read_json(run / 'manifest.json')
    require(read_json(run / 'visit-order.json') == order() == manifest['order'], 'Campaign order changed')
    rows = []
    visits = sorted((run / 'raw').iterdir())
    require(len(visits) == 40 and [p.name for p in visits] == [f"{p['visit']:02d}-{p['config']}" for p in order()], 'Visit directory count/order differs')
    for path, plan in zip(visits, order()):
        baseline = read_json(run / 'machine.json')['before']
        if plan['position'] == 1:
            machine.validate_readiness(read_json(run / f"block-{plan['block']:02d}-idle.json"), baseline, after_warmup=False)
        machine.validate_readiness(read_json(path / 'readiness.json'), baseline, after_warmup=True)
        value = read_json(path / 'visit.json')
        require(all(value[k] == v for k, v in plan.items()) and value['status'] == 'VALID', 'Invalid or misordered visit')
        artifact = read_json(run / 'artifacts.json')['C' if plan['config'] == 'D' else plan['config']]
        require(value['artifact_files'] == artifact['files'], 'Per-visit artifact identities differ')
        require(value['request_sha256'] == REQUEST_SHA, 'Per-visit request identity differs')
        execution = read_json(path / 'command.json')
        require(execution['revision'] == artifact['revision'] and execution['affinity'] == sorted(SERVER_CPUS)
                and execution['compute_threads'] == THREADS['compute'] and execution['batch_threads'] == THREADS['batch'] and execution['http_threads'] == 2, 'Saved runtime configuration differs')
        for role in ('warmup-1', 'warmup-2', 'measured'):
            client = read_json(path / f'{role}-client.json')
            response = read_json(path / f'{role}-response.json')
            require(client['request_sha256'] == REQUEST_SHA and client['response_sha256'] == sha(path / f'{role}-response.json'), 'Request/response identity differs')
            require(client['role'] == role and math.isfinite(client['request_wall_ms']) and client['request_wall_ms'] > 0, 'Invalid external duration/role')
            validate_response(response, client['http_status'], manifest['prompt_n'])
        cleanup = read_json(path / 'cleanup.json')
        require(cleanup['status'] == 'PASS' and cleanup['server_launcher_exit'] == 0
                and cleanup['sched_ext'] == 'disabled' and cleanup['port_free'], 'Visit cleanup did not pass')
        if plan['config'] == 'D':
            root = cleanup['root']
            require(root['clean'] and root['loader_exit'] == 0 and not root['loader_sigterm_requested'] and root['timeline'] and not root['timeline'][-1]['project_objects'], 'D cleanup/teardown invalid')
        for name in ('policies-before.json', 'policies-pre-measured.json', 'policies-after.json'):
            policy = read_json(path / name)
            expected = 7 if plan['config'] == 'D' else 0
            require(all(t['policy'] == expected and t['affinity'] == sorted(SERVER_CPUS) and t['uid'] == UID for t in policy['tids']), 'Saved TID policies/affinities differ')
            require(policy['tids'] and policy['runner']['policy'] == 0 and policy['runner']['affinity'] == sorted(HOUSE_CPUS), 'Saved runner/server snapshot invalid')
            if plan['config'] == 'D':
                require(policy['launcher']['policy'] == 0 and policy['launcher']['uid'] == UID and policy['launcher']['affinity'] == sorted(HOUSE_CPUS), 'Saved launcher isolation differs')
                require(policy['loader']['policy'] == 0 and policy['loader']['uid'] == 0 and policy['loader']['affinity'] == sorted(HOUSE_CPUS), 'Saved loader isolation differs')
        before, after = read_json(path / 'system-before.json'), read_json(path / 'system-after.json')
        machine.validate(before, read_json(run / 'machine.json')['before'])
        machine.validate(after, before)
        measured, client = read_json(path / 'measured-response.json'), read_json(path / 'measured-client.json')
        rows.append(dict(**plan, revision=artifact['revision'], request_sha256=REQUEST_SHA,
                         server_sha256=artifact['files']['bin/llama-server'],
                         scheduler='neutral_sched_ext' if plan['config'] == 'D' else 'default_Linux',
                         prefill_tps=measured['timings']['prompt_per_second'], decode_tps=measured['timings']['predicted_per_second'],
                         request_wall_ms=client['request_wall_ms'], prompt_n=measured['timings']['prompt_n'], predicted_n=128))
    return rows


def finalize():
    run = active_run()
    with locked(run):
        manifest = require_status(run, {'CAMPAIGN_COMPLETE'})
        require((run / 'CAMPAIGN_COMPLETE').is_file(), 'Completion marker absent')
        require(state() == 'disabled' and not live_project_processes(), 'Project runtime still active')
        port_free()
        validate_artifacts(run, offline=True)
        cleanup = read_json(run / 'final-cleanup.json')
        require(cleanup['status'] == 'PASS' and cleanup['artifacts_rehashed'] and cleanup['model_after'] == manifest['model'] and cleanup['scheduler_hashes'] == SCHED_HASHES, 'Final cleanup/provenance invalid')
        require(not project_objects(read_json(run / 'bpf-final.json')), 'Saved final project BPF state remains')
        try:
            rows = collect_rows(run)
            summary = analysis.summarize(rows)
            write_json(run / 'protocol-validation.json', dict(status='PASS', samples={c: sum(r['config']==c for r in rows) for c in 'ABCD'}, visits=40,
                                                             warmups=80, request_sha256=REQUEST_SHA, order_exact=True, all_artifact_hashes_valid=True,
                                                             cleanup_passed=True, analysis_version=manifest['helper_sources']['analysis.py']))
            analysis.export(run, rows, summary)
            with open(run / 'final-report.md', 'a') as report:
                report.write('\nHost profile SHA256: ' + manifest['host_profile_sha256'] + '\n')
                report.write('Thermal validation: ' + ('unavailable; only idle/load readiness validated' if HOST['capabilities']['temperature_sensor'] == 'unavailable' else 'bounded package-sensor cooldown/stability validated') + '\n')
            change_status(run, 'FINALIZED')
        except Exception as error:
            write_json(run / 'protocol-validation.json', dict(status='FAIL', error=str(error)))
            raise
    print(f'Phase D complete: {run / "final-report.md"}\nFirefox/Codex may now be reopened.')


def dry_run(phase, *, reuse_artifacts=False, quiet_mode=None):
    # No campaign state, binaries, network requests, privilege or builds are used.
    actions = {'prepare': ['stop only verified leftover managed Codex daemons after UI/CLI closes', 'reject interactive applications', 'verify', 'sequential A/B/C server-only builds; two compile jobs', 'extract/validate --version', 'remove owned temporary builds'],
               'arm': ['reject interactive applications', 'validate artifacts', 'snapshot machine', 'one sudo helper start; no sched_ext activation'],
               'campaign': ['reject interactive applications', '40 interleaved fresh-server visits; 2 warmups + 1 measurement each', 'cleanup and helper exit'],
               'finalize': ['reject interactive applications', 'validate saved evidence', 'descriptive statistics', '10000 paired-block bootstrap draws', 'applications may reopen']}
    if reuse_artifacts:
        actions['prepare'] = actions['prepare'][:3] + ['validate/share previous closed or unused A/B/C bundles; --version only; no builds']
    if quiet_mode == 'check-ready':
        actions[phase] = ['read-only application/port/power checks; no requests']
    elif quiet_mode == 'stop-codex-daemons':
        actions[phase] = ['verify managed daemon identities and closed UI/CLI', 'SIGTERM only those profile-owner daemons; no requests']
    print(json.dumps(dict(phase=phase, dry_run=True, repository=str(REPO), results=str(RESULTS),
                          pointer=str(RESULTS / '.active-run'), host_profile_sha256=sha(PROFILE_PATH),
                          model=str(MODEL), uid=UID, scheduler_hashes=SCHED_HASHES, server_cpus=sorted(SERVER_CPUS), runner_client_cpus=sorted(HOUSE_CPUS),
                          helper_loader_cpus=sorted(HOUSE_CPUS), compute_threads=THREADS['compute'], batch_threads=THREADS['batch'], http_threads=THREADS['http'], order=order(),
                          prompt_sha256=PROMPT_SHA, request_sha256=REQUEST_SHA, revisions=REVISIONS,
                          d_reuses='C', only_measurement_phase='campaign', quiet_all_phases=True, build_jobs=BUILD_JOBS,
                          actions=actions[phase]), indent=2))


def run_phase(phase, *, reuse_artifacts=False):
    if phase == 'prepare':
        stopped = machine.stop_codex_daemons()
        if stopped:
            print('Stopped verified leftover managed Codex daemons: ' + ', '.join(str(p['pid']) for p in stopped), flush=True)
    machine.reject_interactive_apps()
    if phase == 'prepare':
        prepare(reuse_artifacts=reuse_artifacts)
    else:
        globals()[phase]()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('prepare', 'arm', 'campaign', 'finalize'))
    parser.add_argument('--dry-run', action='store_true', help='Print the immutable plan; perform no operations')
    parser.add_argument('--reuse-artifacts', action='store_true', help='Phase A only: validate and reuse previous closed/unused prepared bundles in a new campaign')
    quiet_options = parser.add_mutually_exclusive_group()
    quiet_options.add_argument('--check-ready', action='store_true', help='Read-only application/port/power checks; do not execute the phase')
    quiet_options.add_argument('--stop-codex-daemons', action='store_true', help='After closing UI/CLI, stop only verified managed Codex daemons; do not execute the phase')
    args = parser.parse_args()
    global MODEL
    common.load_profile(PROFILE_PATH)
    MODEL = common.MODEL
    require('MODEL' not in os.environ or Path(os.environ['MODEL']).expanduser().resolve() == MODEL, 'MODEL override differs from frozen profile; regenerate before a new campaign')
    require(HOST['allocation']['status'] == 'PASS', 'BLOCKED: ' + str(HOST['allocation']['reason']))
    require(os.getuid() == UID, 'Run phase entry points as the frozen non-root repository owner, without sudo')
    require(not args.reuse_artifacts or args.phase == 'prepare', '--reuse-artifacts is only for Phase A')
    if args.dry_run:
        dry_run(args.phase, reuse_artifacts=args.reuse_artifacts,
                quiet_mode='check-ready' if args.check_ready else 'stop-codex-daemons' if args.stop_codex_daemons else None)
        return
    host_profile.validate_current(HOST, initial_affinity=True)
    os.sched_setaffinity(0, HOUSE_CPUS)
    require(os.sched_getaffinity(0) == HOUSE_CPUS and os.sched_getscheduler(0) == 0, 'Runner affinity/policy differs')
    def interrupted(signum, _frame):
        raise RuntimeError(f'Phase interrupted by signal {signum}')
    for sig in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, interrupted)
    if args.stop_codex_daemons:
        stopped = machine.stop_codex_daemons()
        print('Managed Codex daemons stopped: ' + ', '.join(str(p['pid']) for p in stopped) + '. No campaign request issued.')
        return
    if args.check_ready:
        check_ready()
        return
    run_phase(args.phase, reuse_artifacts=args.reuse_artifacts)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(f'Step 10 stopped: {error}', file=sys.stderr)
        sys.exit(1)
