#!/usr/bin/env python3
"""Bounded, unprivileged AVX2 runtime comparison; never loads sched_ext."""
from cli_ko import ArgumentParser, main_entry
import copy
import ctypes
import datetime
import fcntl
import hashlib
import http.client
import json
import os
from pathlib import Path
import platform
import random
import re
import resource
import shutil
import signal
import socket
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / 'state/intel'
REV = '7a2db1a0cf38e5f4eb278a58c3903d295258d0ea'
MODEL_SHA = 'f3bdf9cf31dee4b57ae4e455a1cb0d01b5c2c1b50d72d3112141c195506c2840'
R_HEADER = ROOT / 'experiments/r-pool-validation-v1/candidates/R/overlay/ggml/src/ggml-cpu/newa-q4-policy.h'
FIXTURES = ROOT / 'experiments/a-component-scheduler-replication-v1/fixtures.json'
LOAD = ROOT / 'experiments/a-component-scheduler-replication-v1/code/load.py'
ARMS = ['B0_L', 'F6_L', 'A_L']


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def read(path):
    return json.loads(path.read_text())


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(data)
    return h.hexdigest()


def text(path, default='unavailable'):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return default


def cpu_list(value):
    result = []
    for part in value.split(','):
        ends = part.split('-')
        require(len(ends) in (1, 2), 'CPU 목록이 올바르지 않습니다.')
        lo, hi = int(ends[0]), int(ends[-1])
        require(0 <= lo <= hi < 1024, 'CPU 범위가 올바르지 않습니다.')
        result.extend(range(lo, hi + 1))
    require(len(result) == len(set(result)), 'CPU 번호가 중복됐습니다.')
    return sorted(result)


def choose_cpus(rows, requested=None):
    by_cpu = {r['cpu']: r for r in rows}
    groups = {}
    for r in rows:
        groups.setdefault((r['package'], r['core']), []).append(r)
    require(len(groups) >= 6, 'E 정책에는 사용 가능한 물리 코어 6개가 필요합니다.')
    # SMT-capable cores first: a documented inference, not a CPUID core-type claim.
    order = sorted(groups.values(), key=lambda g: (-max(len(r['siblings']) for r in g), min(r['cpu'] for r in g)))
    selected = requested if requested is not None else sorted(min(r['cpu'] for r in g) for g in order[:6])
    require(len(selected) == 6 and len(set(selected)) == 6 and set(selected) <= by_cpu.keys(),
            '--cpus에 서로 다른 허용 CPU 6개를 지정하세요.')
    physical = {(by_cpu[c]['package'], by_cpu[c]['core']) for c in selected}
    require(len(physical) == 6, '한 물리 코어의 SMT 스레드 두 개를 함께 선택할 수 없습니다.')
    others = [r for r in rows if r['cpu'] not in selected]
    require(others, '서버의 CPU 범위 밖에 제어용 CPU가 하나 필요합니다.')
    others.sort(key=lambda r: ((r['package'], r['core']) in physical, r['cpu']))
    return selected, others[0]['cpu']


def temperatures():
    # Retain the historical JSON field while allowing hosts without sensors.
    return {}


def guard():
    require(os.getuid() != 0, 'sudo 없이 일반 사용자로 실행하세요.')
    require(text('/sys/kernel/sched_ext/state', 'unsupported') in ('disabled', 'unsupported'),
            '다른 커널 스케줄러가 이미 활성화되어 실험을 중단합니다.')
    require(os.sched_getscheduler(0) == os.SCHED_OTHER, '제어 프로세스는 Linux 기본 스케줄링 정책이어야 합니다.')


def preflight(args):
    require(sys.version_info >= (3, 10), 'Python 3.10 이상이 필요합니다.')
    require(platform.system() == 'Linux' and platform.machine() == 'x86_64', 'x86-64 Linux가 필요합니다.')
    guard()
    cpuinfo = {}
    for block in Path('/proc/cpuinfo').read_text().strip().split('\n\n'):
        item = dict(line.split(':', 1) for line in block.splitlines() if ':' in line)
        item = {k.strip(): v.strip() for k, v in item.items()}
        if 'processor' in item:
            cpuinfo[int(item['processor'])] = item
    allowed = sorted(os.sched_getaffinity(0))
    rows = []
    for cpu in allowed:
        top = Path(f'/sys/devices/system/cpu/cpu{cpu}/topology')
        rows.append(dict(cpu=cpu, package=int(text(top/'physical_package_id')), core=int(text(top/'core_id')),
                         siblings=cpu_list(text(top/'thread_siblings_list')), core_type=text(top/'core_type'),
                         max_frequency_khz=text(top.parent/'cpufreq/cpuinfo_max_freq')))
    selected, controller = choose_cpus(rows, cpu_list(args.cpus) if args.cpus else None)
    for cpu in selected:
        required = {'avx', 'avx2', 'fma', 'f16c', 'sse4_2'}
        require(required <= set(cpuinfo[cpu]['flags'].split()), f'CPU {cpu} lacks required AVX2/FMA/F16C/SSE4.2 flags')
    vendor = cpuinfo[selected[0]]['vendor_id']
    require(vendor == 'GenuineIntel' or args.allow_non_intel, 'Intel 전용 과거 실험입니다. 다른 장비의 호환성 검사에는 --allow-non-intel을 지정하세요.')
    for tool in ('git', 'cmake', 'gcc', 'g++', 'make', 'taskset', 'tar'):
        require(shutil.which(tool), '필요한 프로그램이 없습니다: ' + tool)
    return dict(status='PREFLIGHT_PASS', cpu_model=cpuinfo[selected[0]]['model name'], vendor=vendor,
                intel_hardware=vendor == 'GenuineIntel', kernel=platform.release(), os_release=text('/etc/os-release'),
                allowed_cpus=allowed, topology=rows, selected_cpus=selected, controller_cpu=controller,
                selection='one thread per physical core, SMT-capable cores first; P/E is inferred, not assumed',
                scheduler='default Linux only', sched_ext=text('/sys/kernel/sched_ext/state', 'unsupported'),
                temperature_c=temperatures(),
                governors={str(c): text(f'/sys/devices/system/cpu/cpu{c}/cpufreq/scaling_governor') for c in selected},
                gcc=subprocess.check_output(['gcc', '--version'], text=True).splitlines()[0])


def clean_env():
    # Prevent shell CFLAGS/LD_PRELOAD/NEWA/OMP settings from contaminating either arm.
    return {k: os.environ[k] for k in ('PATH', 'HOME', 'LANG', 'TMPDIR', 'SSL_CERT_FILE', 'SSL_CERT_DIR') if k in os.environ} | {'LC_ALL': 'C'}


def run_logged(command, log, timeout=1800):
    print('RUN', ' '.join(map(str, command)), 'LOG', log, flush=True)
    with log.open('w') as output:
        process = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT,
                                   env=clean_env(), cwd=ROOT, start_new_session=True)
        try:
            code = process.wait(timeout=timeout)
            require(code == 0, '명령 실행 실패 (종료 코드 ' + str(code) + '). 로그 파일: ' + str(log))
        finally:
            stop_owned(process)


def tree_hashes(directory):
    return {str(p.relative_to(directory)): sha(p) for p in sorted(directory.rglob('*'))
            if p.is_file() and not p.is_symlink() and '.git' not in p.parts and '__pycache__' not in p.parts}


def build(args):
    base = STATE / 'builds'
    base.mkdir(parents=True, exist_ok=True)
    flags = ['-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_C_COMPILER=gcc', '-DCMAKE_CXX_COMPILER=g++',
             '-DCMAKE_C_FLAGS=-march=x86-64 -mtune=generic', '-DCMAKE_CXX_FLAGS=-march=x86-64 -mtune=generic',
             '-DCMAKE_EXPORT_COMPILE_COMMANDS=ON', '-DBUILD_SHARED_LIBS=ON', '-DGGML_NATIVE=OFF',
             '-DGGML_OPENMP=ON', '-DGGML_BLAS=OFF', '-DGGML_BACKEND_DL=OFF', '-DGGML_CPU_ALL_VARIANTS=OFF',
             '-DLLAMA_BUILD_TESTS=OFF', '-DLLAMA_BUILD_EXAMPLES=OFF', '-DLLAMA_BUILD_SERVER=ON',
             '-DLLAMA_BUILD_UI=OFF', '-DLLAMA_USE_PREBUILT_UI=OFF', '-DLLAMA_CURL=OFF',
             '-DLLAMA_SCX_PHASE_TRACE=OFF']
    for name in ('AVX', 'AVX2', 'FMA', 'F16C', 'SSE42'):
        flags.append('-DGGML_' + name + '=ON')
    for name in ('BMI2', 'AVX_VNNI', 'AVX512', 'AVX512_VBMI', 'AVX512_VNNI', 'AVX512_BF16',
                 'AMX_TILE', 'AMX_INT8', 'AMX_BF16', 'CUDA', 'VULKAN', 'HIP', 'SYCL', 'METAL', 'RPC'):
        flags.append('-DGGML_' + name + '=OFF')
    inputs = dict(recipe_version=2, source_sha256=tree_hashes(ROOT/'src/llama'), r_header_sha256=sha(R_HEADER),
                  baseline_commit=REV, common_cmake_flags=flags,
                  compiler=subprocess.check_output(['g++', '--version'], text=True),
                  gcc_sha256=sha(Path(shutil.which('gcc')).resolve()),
                  gxx_sha256=sha(Path(shutil.which('g++')).resolve()))
    require(inputs['r_header_sha256'] == '014ec3787142838295cb9e8193453ea504cf7a27f18c14a0fa6b8799fcd93029', 'R 커널 헤더의 해시가 다릅니다.')
    key = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()[:16]
    destination = base / key
    if (destination/'complete.json').exists():
        result = read(destination/'complete.json')
        require(read(destination/'inputs.json') == inputs, '빌드 입력 해시가 달라졌습니다.')
        for p, digest in result['binary_sha256'].items():
            require(sha(Path(p)) == digest, '빌드 산출물이 바뀌었습니다: ' + p)
        print('REUSE VERIFIED BUILD', destination, flush=True)
        return result
    require(not destination.exists(), '미완성 빌드가 남아 있습니다: ' + str(destination) + '. 로그를 확인하고 해당 빌드 폴더를 보관한 후 다시 시도하세요.')
    destination.mkdir()
    save(destination/'inputs.json', inputs)
    source_a = destination/'source-A'
    shutil.copytree(ROOT/'src/llama', source_a, ignore=shutil.ignore_patterns('.git', '__pycache__'))
    shutil.copy2(R_HEADER, source_a/'ggml/src/ggml-cpu/newa-q4-policy.h')
    source_b = destination/'source-B0'
    source_b.mkdir()
    repo = Path(args.baseline_repo).resolve() if args.baseline_repo else destination/'baseline-git'
    if not args.baseline_repo:
        run_logged(['git', 'init', str(repo)], destination/'git-init.log')
        run_logged(['git', '-C', str(repo), 'fetch', '--depth=1', 'https://github.com/ggml-org/llama.cpp.git', REV], destination/'git-fetch.log', 300)
    actual = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', REV+'^{commit}'], text=True).strip()
    require(actual == REV, '과거 원본 커밋을 찾을 수 없습니다. --baseline-repo로 보존된 저장소를 지정하세요.')
    archive = destination/'baseline-source.tar'
    with archive.open('wb') as stream:
        subprocess.run(['git', '-C', str(repo), 'archive', REV], stdout=stream, check=True)
    subprocess.run(['tar', '-xf', str(archive), '-C', str(source_b)], check=True)
    archive.unlink()
    # The same frozen, disabled web UI in both arms avoids network/Node dependencies.
    for filename in ('CMakeLists.txt', 'frozen-ui.cpp', 'frozen-ui.h', 'ui.h'):
        shutil.copy2(source_a/'tools/ui'/filename, source_b/'tools/ui'/filename)
    artifacts = {}
    for name, source in [('B0', source_b), ('A', source_a)]:
        target = destination/('build-'+name)
        command = ['cmake', '-S', str(source), '-B', str(target), *flags,
                   '-DLLAMA_SCX_PHASE_HINT=' + ('ON' if name == 'A' else 'OFF')]
        save(destination/(name+'-source-sha256.json'), tree_hashes(source))
        save(destination/(name+'-configure-command.json'), command)
        run_logged(command, destination/(name+'-configure.log'))
        run_logged(['cmake', '--build', str(target), '--target', 'llama-server', '-j', str(args.jobs)], destination/(name+'-build.log'))
        commands = read(target/'compile_commands.json')
        combined = '\n'.join(c['command'] for c in commands)
        require(not re.search(r'-march=native|-mtune=native|-mavx512|-mamx|-mavxvnni|-march=znver', combined), 'CPU 전용 ISA 옵션이 섞여 있습니다.')
        require(all(flag in combined for flag in ('-mavx2', '-mfma', '-mf16c', '-fopenmp')), 'AVX2/OpenMP 컴파일 옵션이 없습니다.')
        for path in (target/'bin').iterdir():
            if path.is_file() and (path.name == 'llama-server' or '.so' in path.name):
                artifacts[str(path.resolve())] = sha(path)
    result = dict(status='BUILD_PASS', build_id=key, directory=str(destination), inputs_sha256=sha(destination/'inputs.json'),
                  binary_sha256=artifacts, baseline_commit=REV,
                  baseline_overlay='Only tools/ui/{CMakeLists.txt,frozen-ui.cpp,frozen-ui.h,ui.h}; disabled web UI shared with A',
                  candidate_overlay='src/llama + preserved R newa-q4-policy.h; no donor pool',
                  identity_note='Fresh AVX2 builds, not byte-identical to the frozen AMD runtimes')
    save(destination/'complete.json', result)
    return result


def http_json(port, path, payload=None, timeout=180):
    conn = http.client.HTTPConnection('127.0.0.1', port, timeout=timeout)
    try:
        conn.request('GET' if payload is None else 'POST', path,
                     None if payload is None else json.dumps(payload).encode(), {'Content-Type': 'application/json'})
        response = conn.getresponse()
        body = response.read()
        require(response.status == 200, f'HTTP {response.status} {path}: {body[:200]!r}')
        return json.loads(body)
    finally:
        conn.close()


def process_counter(pid):
    fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
    return dict(pid=pid, starttime=int(fields[19]), cpu_ticks=int(fields[11])+int(fields[12]),
                tick_hz=os.sysconf('SC_CLK_TCK'), affinity=sorted(os.sched_getaffinity(pid)),
                policy=os.sched_getscheduler(pid))


def cpu_seconds(before, after):
    for name in ('pid', 'starttime', 'tick_hz', 'affinity', 'policy'):
        require(before[name] == after[name], '프로세스 카운터 식별자가 바뀌었습니다: ' + name)
    return (after['cpu_ticks'] - before['cpu_ticks']) / before['tick_hz']


def worker_envelope(pid, cpus):
    workers = {}
    for path in Path(f'/proc/{pid}/task').iterdir():
        try:
            workers[path.name] = dict(affinity=sorted(os.sched_getaffinity(int(path.name))),
                                      policy=os.sched_getscheduler(int(path.name)))
        except ProcessLookupError:
            continue
    require(workers and all(w['affinity'] == cpus and w['policy'] == 0 for w in workers.values()),
            '서버 스레드의 CPU 범위 또는 Linux 스케줄러 정책이 다릅니다.')
    return workers


def stop_owned(proc):
    if proc is None:
        return None
    if proc.poll() is None:
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=5)
    return proc.returncode


def payload_for(fixture, n_predict):
    payload = copy.deepcopy(fixture['requests'][0])
    payload.pop('id_slot')
    payload['prompt'] = [r['prompt'] for r in fixture['requests']]
    payload['n_predict'] = n_predict
    return payload


def validate_body(body, fixture, n_predict):
    if isinstance(body, dict) and len(fixture['requests']) == 1:
        body = [body]
    require(isinstance(body, list) and len(body) == len(fixture['requests']), '생성 응답이 누락됐습니다.')
    require(sorted(v['index'] for v in body) == list(range(len(body))), '요청 번호가 중복되거나 누락됐습니다.')
    body.sort(key=lambda v: v['index'])
    for row, request in zip(body, fixture['requests']):
        require(len(row['tokens']) == row['tokens_predicted'] == n_predict, '생성된 토큰 수가 다릅니다.')
        require(row['tokens_evaluated'] == row['timings']['prompt_n'] == len(request['prompt']), 'Prefill 입력 토큰 수가 달라졌습니다.')
        require(row['timings']['cache_n'] == 0, '요청 사이에 프롬프트 또는 KV 캐시 재사용이 감지됐습니다.')
        require(row['generation_settings']['temperature'] == 0 and row['generation_settings']['seed'] == 424242,
                '결정적 토큰 생성 설정이 다릅니다.')
    return body


def visit(args, host, identity, arm, condition, fixture, n_predict, folder):
    from intel_policy_evidence import validate as validate_policy
    guard()
    folder.mkdir()
    cpus = host['selected_cpus']
    bindir = Path(identity['directory'])/('build-B0' if arm == 'B0_L' else 'build-A')/'bin'
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    command = [str(bindir/'llama-server'), '--model', str(args.model.resolve()), '--host', '127.0.0.1', '--port', str(port),
               '--n-gpu-layers', '0', '--threads', '5', '--threads-batch', '6', '--threads-http', '8',
               '--ctx-size', '8192', '--parallel', '8', '--batch-size', '512', '--ubatch-size', '256',
               '--flash-attn', 'on', '--no-ui', '--perf', '--log-verbosity', '4', '--no-kv-unified', '--spec-type', 'none']
    env = clean_env() | dict(LD_LIBRARY_PATH=str(bindir), OMP_NUM_THREADS='6', OMP_DYNAMIC='FALSE',
                             OMP_DISPLAY_AFFINITY='TRUE', OMP_AFFINITY_FORMAT='NEWA_TEAM pid=%P team=%N index=%n native=%i')
    mode = 'off'
    if arm != 'B0_L':
        mode = 'pressure' if arm == 'A_L' else 'fixed6'
        command += ['--server-compute-profile-mode', 'phase']
        env.update(GGML_NEWA_POOL='off', GGML_NEWA_Q6_BATCH='phase_batch', GGML_NEWA_Q4_TILE32='phase_batch',
                   GGML_NEWA_PREFILL_ATTN='off', GGML_NEWA_REPACK_PAGES='huge', NEWA_DECODE_RESOURCE=mode)
    save(folder/'launch.json', dict(argv=command, env=env, cpus=cpus, arm=arm, condition=condition,
                                  temperature_before_c=temperatures()))
    payload = payload_for(fixture, n_predict)
    save(folder/'payload.json', payload)
    server = load = None
    samples = []
    started = time.monotonic()
    parent_pid = os.getpid()
    def child_setup():
        # Linux-only; this runner is single-threaded. No surviving server on parent death.
        libc = ctypes.CDLL(None, use_errno=True)
        if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0 or os.getppid() != parent_pid:
            os._exit(126)
    def expired(signum, frame):
        raise TimeoutError('Visit exceeded 600 seconds')
    prior_alarm = signal.signal(signal.SIGALRM, expired)
    signal.alarm(600)
    try:
        with (folder/'server.log').open('w') as server_log, (folder/'load.jsonl').open('w') as load_log:
            if condition == 'cpu25':
                load = subprocess.Popen([sys.executable, '-B', '-u', str(LOAD), '--cpu', str(cpus[-1]),
                                         '--parent', str(os.getpid()), '--seconds', '600'],
                                        env=clean_env(), stdout=load_log, stderr=subprocess.STDOUT, start_new_session=True)
                time.sleep(.5)
                require(load.poll() is None and 'READY' in (folder/'load.jsonl').read_text(), 'CPU 부하 프로세스를 시작하지 못했습니다.')
            server = subprocess.Popen(['taskset', '-c', ','.join(map(str, cpus)), *command],
                                      env=env, stdout=server_log, stderr=subprocess.STDOUT,
                                      start_new_session=True, preexec_fn=child_setup)
            save(folder/'owned-processes.json', dict(server_pid=server.pid, load_pid=load.pid if load else None))
            deadline = time.monotonic() + 120
            while True:
                require(server.poll() is None, '서버가 종료됐습니다. server.log를 확인하세요.')
                try:
                    http_json(port, '/health', timeout=1)
                    break
                except (OSError, RuntimeError, http.client.HTTPException):
                    require(time.monotonic() < deadline, '서버가 제한 시간 내에 준비되지 않았습니다.')
                    time.sleep(.1)
            actual = Path(f'/proc/{server.pid}/cmdline').read_bytes().rstrip(b'\0').decode().split('\0')
            require(actual == command, '예상과 다른 서버 명령입니다. 포트 충돌을 확인하세요.')
            mapped = sorted({line.split()[-1] for line in Path(f'/proc/{server.pid}/maps').read_text().splitlines() if '/' in line})
            loaded = {p: sha(Path(p)) for p in mapped if Path(p).is_file() and ('.so' in Path(p).name or p == command[0])}
            expected = {p: h for p, h in identity['binary_sha256'].items() if Path(p).parent == bindir}
            require(expected and all(loaded.get(p) == h for p, h in expected.items()), '새 빌드의 공유 라이브러리 해시가 일치하지 않습니다.')
            require(all(str(bindir) in p for p in loaded if Path(p).name.startswith(('libllama', 'libggml'))), '이전 llama/ggml 공유 라이브러리가 로드됐습니다.')
            require(str(args.model.resolve()) in mapped, '예상한 모델이 매핑되지 않았습니다.')
            save(folder/'runtime.json', dict(loaded_sha256=loaded, mapped=mapped, model_sha256=MODEL_SHA,
                                            workers=worker_envelope(server.pid, cpus)))
            for item, request in zip(fixture['items'], fixture['requests']):
                tokens = http_json(port, '/tokenize', dict(content=item['prompt'], add_special=True))['tokens']
                require(tokens[:fixture['input_token_cap']] == request['prompt'], '모델의 토크나이저가 실험 입력과 일치하지 않습니다.')
            for role in ('warmup', 'measured'):
                guard()
                before = process_counter(server.pid)
                workers_before = worker_envelope(server.pid, cpus)
                lb = process_counter(load.pid) if load else None
                t0 = time.monotonic_ns()
                body = http_json(port, '/completion', payload, timeout=180)
                t1 = time.monotonic_ns()
                la = process_counter(load.pid) if load else None
                after = process_counter(server.pid)
                save(folder/(role+'-responses.json'), body)
                rows = validate_body(body, fixture, n_predict)
                wall = (t1 - t0) / 1e9
                generated = sum(len(r['tokens']) for r in rows)
                sample = dict(role=role, start_ns=t0, end_ns=t1, wall_s=wall, actual_generated_tokens=generated,
                              throughput=generated/wall, server_before=before, server_after=after,
                              cpu_time_s=cpu_seconds(before, after), temperature_after_c=temperatures(),
                              workers_before=workers_before, workers_after=worker_envelope(server.pid, cpus),
                              tokens=[r['tokens'] for r in rows], per_request_timings=[r['timings'] for r in rows])
                if load:
                    require(load.poll() is None and lb['affinity'] == la['affinity'] == [cpus[-1]] and lb['policy'] == la['policy'] == 0,
                            '백그라운드 부하가 중단됐거나 CPU·정책이 변경됐습니다.')
                    sample.update(load_before=lb, load_after=la, load_mean_cpu_cores=cpu_seconds(lb, la)/wall)
                samples.append(sample)
                save(folder/'samples.json', samples)
                if load and role == 'measured':
                    require(.22 <= sample['load_mean_cpu_cores'] <= .28, '실제 cpu25 부하가 0.22~0.28코어 범위를 벗어났습니다.')
                guard()
                print(json.dumps(dict(event='COHORT_COMPLETE', arm=arm, cohort=fixture['id'], condition=condition,
                                      role=role, throughput=sample['throughput'])), flush=True)
            require(samples[0]['tokens'] == samples[1]['tokens'], '같은 서버에서 생성 토큰이 다릅니다.')
    finally:
        server_rc = stop_owned(server)
        load_rc = stop_owned(load)
        signal.alarm(0)
        signal.signal(signal.SIGALRM, prior_alarm)
        save(folder/'cleanup.json', dict(server_returncode=server_rc, load_returncode=load_rc,
                                         elapsed_s=time.monotonic()-started, temperature_c=temperatures()))
    require(server_rc == 0 and (load is None or load_rc == 0), '서버가 비정상 종료됐습니다. 로그를 확인하세요.')
    log = (folder/'server.log').read_text()
    policy = validate_policy(log, mode, cpus, os.sysconf('SC_CLK_TCK'))
    teams = sorted({int(n) for n in re.findall(r'NEWA_TEAM pid=\d+ team=(\d+)', log)})
    require(teams and set(teams) <= {5, 6}, 'OpenMP 스레드 팀 실행 증빙이 잘못됐거나 없습니다.')
    measured = samples[1]
    epochs = [e for e in policy.get('epochs', []) if measured['start_ns'] <= e['sample']['model_start'] <= measured['end_ns']]
    decisions = [sum(e['eligible_by_size_5_6'][size][j] for e in epochs for size in range(2, 9)) for j in range(2)]
    require({5+j for j, n in enumerate(decisions) if n} <= set(teams), '실제 OpenMP 로그에 선택한 프로파일이 없습니다.')
    save(folder/'policy-recomputed.json', policy)
    result = dict(status='VALID', arm=arm, condition=condition, cohort=fixture['id'],
                  metrics=measured, actual_openmp_teams=teams, measured_multi_decode_5_6=decisions,
                  policy_exercised=sum(decisions) > 0, raw_directory=str(folder))
    save(folder/'result.json', result)
    return result


def paired(values):
    rng = random.Random(424242)
    estimates = sorted(statistics.mean(rng.choices(values, k=len(values))) for _ in range(10000))
    return dict(blocks=len(values), gains_pct=values, mean_gain_pct=statistics.mean(values),
                bootstrap_95_pct=[estimates[249], estimates[9749]], faster_pair_fraction=sum(v > 0 for v in values)/len(values))


def analyze(rows, conditions):
    report = dict(status='PILOT_ONLY_NOT_CONFIRMATION', comparisons={})
    for condition in conditions:
        group = [r for r in rows if r['condition'] == condition]
        blocks = sorted({r['block'] for r in group})
        result = {}
        for numerator, denominator in [('A_L', 'B0_L'), ('F6_L', 'B0_L'), ('A_L', 'F6_L')]:
            gains = []
            for block in blocks:
                pair = {r['arm']: r for r in group if r['block'] == block}
                require(set(pair) == set(ARMS), '비교 블록이 완료되지 않았습니다.')
                if condition == 'cpu25':
                    loads = [r['metrics']['load_mean_cpu_cores'] for r in pair.values()]
                    require(max(loads)-min(loads) <= .025, '같은 블록에서 실제 cpu25 부하가 다릅니다.')
                gains.append(100*(pair[numerator]['metrics']['throughput']/pair[denominator]['metrics']['throughput']-1))
            result[numerator+'/'+denominator] = paired(gains)
        result['absolute_mean_tokens_per_second'] = {
            arm: statistics.mean(r['metrics']['throughput'] for r in group if r['arm'] == arm) for arm in ARMS}
        result['A_policy_exercised_blocks'] = [r['block'] for r in group if r['arm'] == 'A_L' and r['policy_exercised']]
        result['A_chose_five_workers_blocks'] = [r['block'] for r in group if r['arm'] == 'A_L' and r['measured_multi_decode_5_6'][0]]
        result['phase_contribution'] = 'NOT_ISOLATED' if not result['A_chose_five_workers_blocks'] else 'PILOT_ONLY_INCONCLUSIVE'
        report['comparisons'][condition] = result
    return report


def experiment(args, host, identity):
    require(args.model.is_file(), '--model로 원본 model.gguf를 지정하세요.')
    require(sha(args.model) == MODEL_SHA, '모델 SHA-256이 다릅니다. 원본 model.gguf를 사용하세요.')
    for path in Path('/proc').glob('[0-9]*/comm'):
        require(text(path) not in ('llama-server', 'llama-bench', 'cc1', 'cc1plus', 'cmake', 'ninja'),
                '경쟁하는 빌드 또는 추론 프로세스가 있습니다: ' + str(path))
    fixtures = read(FIXTURES)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output = STATE/(stamp+'-'+args.mode+'-'+str(os.getpid()))
    output.mkdir(parents=True)
    save(output/'host.json', host)
    save(output/'build-identity.json', identity)
    protocol = dict(kind=args.mode, primary_metric='actual generated tokens / whole cohort HTTP wall seconds',
                    warmup='one unmeasured identical cohort per fresh server; cache_prompt=false in both requests',
                    arms=ARMS, baseline_commit=REV, build_id=identity['build_id'], model_sha256=MODEL_SHA,
                    fixtures_sha256=sha(FIXTURES), runner_sha256=sha(Path(__file__)),
                    policy_validator_sha256=sha(ROOT/'tools/intel_policy_evidence.py'), load_sha256=sha(LOAD),
                    n_predict=16 if args.mode == 'smoke' else 128,
                    conditions=args.conditions, blocks=args.blocks if args.mode == 'pilot' else 0,
                    selected_cpus=host['selected_cpus'], background_cpu=host['selected_cpus'][-1],
                    cpu25='12.5 ms process CPU per 50 ms period on one selected CPU; actual admission 0.22..0.28 core, paired spread <=0.025',
                    excluded_samples='none; any failure invalidates this run and retains raw data',
                    inference_timeout_s=180, visit_timeout_s=600,
                    scheduler='default Linux only; not an A_S or C scheduler confirmation',
                    inference_scope='portable smoke on AMD' if not host['intel_hardware'] else 'Intel runtime smoke/pilot',
                    success_scope='Smoke correctness only, or exploratory pilot; never two-campaign confirmation')
    plan = []
    for fixture in fixtures:
        for arm in ARMS:
            plan.append(dict(stage='correctness', arm=arm, condition='ambient', cohort=fixture['id'], block=0))
    if args.mode == 'smoke' and 'cpu25' in args.conditions:
        for arm in ARMS:
            plan.append(dict(stage='correctness', arm=arm, condition='cpu25', cohort=fixtures[0]['id'], block=0))
    if args.mode == 'pilot':
        for condition in args.conditions:
            for block in range(args.blocks):
                offset = (block//2) % 3
                order = ARMS[offset:] + ARMS[:offset]
                if block % 2:
                    order = order[::-1]
                for arm in order:
                    plan.append(dict(stage='pilot', arm=arm, condition=condition,
                                     cohort=fixtures[block % 2]['id'], block=block+1))
    protocol['plan'] = plan
    save(output/'protocol.json', protocol)
    print('RESULTS', output, flush=True)
    old_affinity = os.sched_getaffinity(0)
    os.sched_setaffinity(0, {host['controller_cpu']})
    completed = []
    by_key = {}
    checks = []
    try:
        for index, spec in enumerate(plan):
            fixture = next(f for f in fixtures if f['id'] == spec['cohort'])
            folder = output/f'{index+1:03d}-{spec["stage"]}-{spec["condition"]}-{spec["cohort"]}-{spec["arm"]}'
            result = visit(args, host, identity, spec['arm'], spec['condition'], fixture, protocol['n_predict'], folder)
            result.update(block=spec['block'], stage=spec['stage'])
            completed.append(result)
            key = (spec['stage'], spec['condition'], spec['block'], spec['cohort'])
            by_key.setdefault(key, {})[spec['arm']] = result['metrics']['tokens']
            group = by_key[key]
            if len(group) == 3:
                check = dict(stage=spec['stage'], condition=spec['condition'], block=spec['block'], cohort=spec['cohort'],
                             A_equals_F6=group['A_L'] == group['F6_L'], A_equals_B0=group['A_L'] == group['B0_L'])
                checks.append(check)
                save(output/'correctness.json', checks)
                require(check['A_equals_F6'], '새 정책이 생성한 토큰이 달라 성능 비교를 중단합니다.')
                require(check['A_equals_B0'], 'B0/A 생성 토큰이 달라 파일럿을 중단합니다.')
            save(output/'progress.json', dict(status='RUNNING', completed=len(completed), total=len(plan), last=spec))
        report = analyze([r for r in completed if r['stage'] == 'pilot'], args.conditions) if args.mode == 'pilot' else dict(status='SMOKE_PASS')
        report.update(intel_hardware=host['intel_hardware'], scheduler_tested=False,
                      correctness=checks, directory=str(output), build_id=identity['build_id'])
        save(output/'summary.json', report)
        save(output/'progress.json', dict(status='COMPLETE', completed=len(completed), total=len(plan)))
        print(json.dumps(report, indent=2), flush=True)
    except BaseException as error:
        save(output/'failure.json', dict(status='INVALID_INCOMPLETE', error=repr(error), completed=len(completed),
                                        failed_plan_index=len(completed)+1, total=len(plan)))
        print('Retained failed experiment:', output, file=sys.stderr)
        raise
    finally:
        os.sched_setaffinity(0, old_affinity)


def main():
    parser = ArgumentParser(description="과거 Intel 런타임 비교 실험")
    parser.add_argument('mode', choices=['check', 'build', 'smoke', 'pilot'], nargs='?', default='check')
    parser.add_argument('--model', type=Path, default=ROOT/'models/model.gguf')
    parser.add_argument('--cpus', help='six distinct physical cores; e.g. derive IDs from check output')
    parser.add_argument('--allow-non-intel', action='store_true', help='compatibility checks only, never Intel evidence')
    parser.add_argument('--baseline-repo', help='optional local Git repo containing the exact historical B0 commit')
    parser.add_argument('--jobs', type=int, default=2)
    parser.add_argument('--blocks', type=int, default=4, help='pilot only; fixed before running, even number 2..16')
    parser.add_argument('--conditions', nargs='+', choices=['ambient', 'cpu25'], default=['ambient', 'cpu25'])
    args = parser.parse_args()
    require(1 <= args.jobs <= 4, '빌드 작업 수는 1에서 4 사이여야 합니다.')
    require(2 <= args.blocks <= 16 and args.blocks % 2 == 0, '블록 수는 2~16 사이의 짝수로 지정하세요.')
    require(len(set(args.conditions)) == len(args.conditions), '동일한 실험 조건이 중복됐습니다.')
    ROOT.joinpath('state').mkdir(exist_ok=True)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    def interrupted(signum, frame):
        raise KeyboardInterrupt('Interrupted by signal ' + str(signum))
    signal.signal(signal.SIGTERM, interrupted)
    with (ROOT/'state/.measurement.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        host = preflight(args)
        if args.mode == 'check':
            print(json.dumps(host, indent=2, ensure_ascii=False))
            return
        identity = build(args)
        if args.mode == 'build':
            print(json.dumps(identity, indent=2))
            return
        experiment(args, host, identity)


if __name__ == '__main__':
    main_entry(main)
