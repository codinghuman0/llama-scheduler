# SPDX-License-Identifier: GPL-2.0
"""Frozen campaign constants and read-only identity checks."""
import contextlib
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import pwd
import shutil
import select
import signal
import socket
import struct
import subprocess
import time

REPO = Path(__file__).resolve().parents[3]
BENCH = Path(__file__).resolve().parent
RESULTS = REPO / 'benchmark-results/step10'
MODEL = Path(os.environ.get('MODEL', str(REPO.parent / 'model.gguf'))).expanduser().resolve()
UID = REPO.stat().st_uid
USER_HOME = Path(pwd.getpwuid(UID).pw_dir)
HOST = {}
THREADS = dict(compute=0, batch=0, http=2)
PROFILE_PATH = REPO / 'benchmark-results/host-profile.json'
MODEL_SHA = 'f3bdf9cf31dee4b57ae4e455a1cb0d01b5c2c1b50d72d3112141c195506c2840'
TAGS = {
    'original-performance-baseline-v1': '7a2db1a0cf38e5f4eb278a58c3903d295258d0ea',
    'llama-side-lightweight-v1': 'c8b9d61d12b4997d902a03e5dc55a185d18c3bc9',
    'neutral-sched-ext-base-v1': 'ea4a36bbad1100d7d3f7c6aa57caadcb782a26fa',
    'one-repo-golden-validation-v1': '542850645a54fc2e35a9a8189ff8dfcf35b9c51d',
}
REVISIONS = dict(zip('ABC', [TAGS['original-performance-baseline-v1']] + [TAGS['llama-side-lightweight-v1']] * 2))
SCHED_HASHES = {}
SCHED = REPO / 'tools/sched_ext/build'
SERVER_CPUS = set()
HOUSE_CPUS = set()
PORT = 8096
MIN_FREE = 512 * 1024 * 1024
BOOT_ID = Path('/proc/sys/kernel/random/boot_id')
BASE = 'A small public library stands beside the town square. Its shelves hold stories, science books, travel guides, and local history. Every morning the librarian opens the windows, checks returned books, and prepares a quiet room for readers. Children visit after school to choose books and ask questions. Older residents use newspapers and share memories of the town. Visitors find maps and learn about nearby walking routes. A reading group meets once a week. Each person explains one idea from a book and listens to the other readers. The library supports curiosity, patient learning, and friendly conversation.'
PROMPT = 'Read the following notes and continue with a concise description of the library.\n\n' + '\n\n'.join([BASE] * 8) + '\n\nContinue this sentence: The library is useful because'
REQUEST = dict(prompt=PROMPT, n_predict=128, temperature=0, seed=424242, stream=False,
               cache_prompt=False, ignore_eos=True, id_slot=0, n_cache_reuse=0,
               stop=[], return_tokens=False, timings_per_token=False)
PROMPT_SHA = 'b7be51379d30270d4d645aefb6014525e89e2bcba6e4be60f5f5613efbe5b4a9'
REQUEST_SHA = '7b68e4809a1f9bca18c2bc29b87c62c637e19e2ccd3785745cc717c046999e1d'


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True) + '\n').encode()


def sha(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def write_json(path, value):
    path = Path(path)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')
    os.replace(temp, path)


def command(argv, *, cwd=REPO, env=None, log=None, capture=True):
    if not capture:
        require(log is not None, 'Streaming command requires a log path')
        with open(log, 'w') as output:
            process = subprocess.Popen([str(arg) for arg in argv], cwd=cwd, env=env,
                                       stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                code = process.wait()
            except BaseException:
                # Only this command's new process group receives cleanup signals.
                if process.returncode is None:
                    try:
                        os.killpg(process.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        process.wait(timeout=5)
                raise
        if code:
            with open(log, 'rb') as output:
                length = output.seek(0, os.SEEK_END)
                output.seek(max(0, length - 8192))
                tail = output.read().decode(errors='replace')
            raise RuntimeError(f'Command failed ({code}): {argv}\nFull log: {log}\n{tail}')
        return ''
    result = subprocess.run([str(arg) for arg in argv], cwd=cwd, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if log:
        Path(log).write_text(result.stdout)
    require(result.returncode == 0, f'Command failed ({result.returncode}): {argv}\n{result.stdout}')
    return result.stdout.strip()


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


def wait_gone(saved, timeout=15):
    deadline = time.monotonic() + timeout
    while same_process(saved) and time.monotonic() < deadline:
        time.sleep(0.05)
    require(not same_process(saved), f'Process remains: {saved}')


def live_project_processes():
    found = []
    for proc in Path('/proc').glob('[0-9]*'):
        try:
            if (proc / 'comm').read_text().strip() in {'llama-server', 'llama_scx', 'llama_scx_child'}:
                found.append(identity(int(proc.name)))
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            pass
    return found


def port_free():
    with socket.socket() as probe:
        # Match the server's reuse rule without allowing a second listener.
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind(('127.0.0.1', PORT))


def parse_cpus(text):
    result = set()
    for part in text.strip().split(','):
        ends = list(map(int, part.split('-')))
        result.update(range(ends[0], ends[-1] + 1))
    return result


def load_profile(path=PROFILE_PATH):
    global MODEL, USER_HOME
    import host_profile
    value = host_profile.load(path)
    HOST.clear()
    HOST.update(value)
    MODEL = Path(value['model']['path'])
    USER_HOME = Path(value['home'])
    SERVER_CPUS.clear()
    SERVER_CPUS.update(value['allocation']['server_cpus'])
    HOUSE_CPUS.clear()
    HOUSE_CPUS.update(value['allocation']['housekeeping_cpus'])
    THREADS.update(compute=value['allocation']['compute_threads'], batch=value['allocation']['batch_threads'], http=value['allocation']['http_threads'])
    SCHED_HASHES.clear()
    SCHED_HASHES.update(value['scheduler']['hashes'])
    return value


def topology():
    import host_profile
    require(HOST, 'Generate/load a host profile first')
    current = host_profile.discover_topology(HOST['topology']['allowed_cpus'])
    require(current == HOST['topology'], 'Host topology changed')
    return current


def model_identity():
    require(MODEL.stat().st_size == 1117321312 and sha(MODEL) == MODEL_SHA, 'Model identity mismatch')
    return dict(path=str(MODEL), size=MODEL.stat().st_size, sha256=MODEL_SHA)


ACCEPTED_BASE = '340468bd398624027624060198393d90aed42873'
PORTABLE_FILES = {
    'README.md', 'tools/sched_ext/BENCHMARK_PROTOCOL.md', 'tools/sched_ext/SEASON2_EXPERIMENT_PROTOCOL.md',
} | {'tools/sched_ext/bench/' + name for name in (
    'README.md', 'common.py', 'machine.py', 'host_profile.py', 'step10.py', 'root_helper.py', 'test_campaign.py',
    'test_host_profile.py', 'detect_host_topology.sh', 'clean_room_setup.sh', 'portability_smoke.sh',
    'step10_phase_a_prepare.sh', 'step10_phase_b_arm.sh', 'step10_phase_c_campaign.sh', 'step10_phase_d_finalize.sh')}
REQUIRED_TAGS = TAGS | {'lightweight-base-v1-release': '3f2f968cd6a8904f97659f82ca2ebbd10ce8b04a'}


def repo_check(*, allow_dirty=False):
    require(command(['git', 'rev-parse', '--show-toplevel']) == str(REPO), 'Repository mismatch')
    require(command(['git', 'branch', '--show-current']) == 'lightweight-base', 'Branch mismatch')
    if not allow_dirty:
        require(not command(['git', 'status', '--porcelain']), 'Worktree must be clean')
    command(['git', 'diff', '--check'])
    for tag, revision in REQUIRED_TAGS.items():
        require(command(['git', 'rev-parse', 'refs/tags/' + tag + '^{commit}']) == revision, f'Tag mismatch: {tag}')
    command(['git', 'merge-base', '--is-ancestor', ACCEPTED_BASE, 'HEAD'])
    changed = command(['git', 'diff', '--name-only', ACCEPTED_BASE]).splitlines()
    changed += command(['git', 'log', '--format=', '--name-only', ACCEPTED_BASE + '..HEAD']).splitlines()
    changed = [p for p in changed if p]
    changed += command(['git', 'ls-files', '--others', '--exclude-standard']).splitlines()
    require(set(changed) <= PORTABLE_FILES, 'Files outside the explicit portability scope changed: ' + repr(sorted(set(changed) - PORTABLE_FILES)))
    runtime = ['src', 'ggml', 'common', 'include', 'tools/server', 'CMakeLists.txt']
    require(not command(['git', 'diff', '--name-only', TAGS['llama-side-lightweight-v1'], '--'] + runtime), 'Frozen llama implementation changed')
    scheduler = ['tools/sched_ext/llama_scx.bpf.c', 'tools/sched_ext/llama_scx.c', 'tools/sched_ext/llama_scx_child.c',
                 'tools/sched_ext/include', 'tools/sched_ext/Makefile', 'tools/sched_ext/provenance']
    require(not command(['git', 'diff', '--name-only', TAGS['neutral-sched-ext-base-v1'], '--'] + scheduler), 'Frozen scheduler implementation changed')
    return command(['git', 'rev-parse', 'HEAD'])


def scheduler_check():
    import host_profile
    require(HOST and host_profile.artifact_identity() == HOST['scheduler'], 'Scheduler artifacts or embedded BPF path changed')
    require(HOST['scheduler']['hashes'] == SCHED_HASHES, 'Scheduler profile identity changed')


def bundle_env(bundle):
    prefixes = ('LLAMA_ARG_', 'GGML_', 'OMP_', 'GOMP_', 'KMP_', 'OPENBLAS_', 'MKL_', 'CMAKE_')
    keys = {'LD_PRELOAD', 'LD_LIBRARY_PATH', 'CFLAGS', 'CXXFLAGS', 'LDFLAGS', 'PYTHONPATH', 'CC', 'CXX',
            'CPATH', 'CPLUS_INCLUDE_PATH', 'C_INCLUDE_PATH', 'LIBRARY_PATH', 'PKG_CONFIG_PATH', 'GCC_EXEC_PREFIX'}
    env = {k: v for k, v in os.environ.items() if not k.startswith(prefixes) and k not in keys}
    env.update(PATH='/usr/bin:/bin', OMP_NUM_THREADS=str(THREADS['compute']), OMP_DYNAMIC='FALSE', LD_LIBRARY_PATH=str(bundle / 'bin'))
    return env


def order():
    return [dict(visit=block * 4 + pos + 1, block=block + 1, position=pos + 1, config=config)
            for block in range(10) for pos, config in enumerate('ABCD'[block % 4:] + 'ABCD'[:block % 4])]


def active_run():
    name = (RESULTS / '.active-run').read_text().strip()
    require(bool(re.fullmatch(r'\d{8}T\d{6}Z(?:-\d+)?', name)), 'Invalid active-run pointer')
    path = RESULTS / name
    require(not path.is_symlink() and path.resolve().parent == RESULTS.resolve() and path.is_dir(), 'Campaign directory identity invalid')
    return path


@contextlib.contextmanager
def locked(run):
    with open(run / '.lock', 'a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def protocol_identity():
    return dict(path='tools/sched_ext/BENCHMARK_PROTOCOL.md', sha256=sha(REPO / 'tools/sched_ext/BENCHMARK_PROTOCOL.md'))


def helper_request(run, op, **args):
    armed = read_json(run / 'armed.json')
    with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET) as peer:
        peer.settimeout(45)
        peer.connect('\0' + armed['socket'])
        pid, uid, _ = struct.unpack('3i', peer.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
        require(uid == 0 and pid == armed['helper']['pid'] and same_process(armed['helper']), 'Helper identity mismatch')
        peer.sendall(canonical(dict(op=op, token=armed['token'], **args)))
        response = json.loads(peer.recv(65536))
    require(response.get('ok'), f'Root helper rejected {op}: {response}')
    return response['result']


def reduced_bpf():
    result = {}
    for kind in ('prog', 'link', 'map'):
        objects = json.loads(command([shutil.which('bpftool') or '/usr/sbin/bpftool', '-j', kind, 'show']))
        result[kind] = [{k: obj[k] for k in ('id', 'name', 'type', 'prog_id', 'map_id', 'map_ids') if k in obj} for obj in objects]
    result.update(sched_ext=state(), enable_seq=int(Path('/sys/kernel/sched_ext/enable_seq').read_text()))
    return result


def project_objects(inventory):
    programs = [o for o in inventory['prog'] if o.get('name', '').startswith('llama_')]
    maps = [o for o in inventory['map'] if o.get('name', '').startswith(('llama_', 'llama_sc.'))]
    prog_ids, map_ids = {o['id'] for o in programs}, {o['id'] for o in maps}
    links = [o for o in inventory['link'] if o.get('prog_id') in prog_ids or o.get('map_id') in map_ids]
    return [dict(object_class=kind, **obj) for kind, objects in (('prog', programs), ('link', links), ('map', maps)) for obj in objects]


def bpf_timeline(run, label, baseline, exit_time):
    snapshots = []
    for index, requested in enumerate((0, 50, 100, 250, 500, 1000, 2000)):
        time.sleep(max(0, exit_time + requested / 1000 - time.monotonic()))
        start = (time.monotonic() - exit_time) * 1000
        snapshot = reduced_bpf()
        snapshot.update(checkpoint=f'T{index}', requested_ms=requested, start_after_exit_ms=start,
                        end_after_exit_ms=(time.monotonic() - exit_time) * 1000)
        # Persist exact inventories before classification or assertions.
        write_json(run / f'{label}-bpf-T{index}.json', snapshot)
        baseline_ids = {kind: {o['id'] for o in baseline[kind]} for kind in ('prog', 'link', 'map')}
        attributable = [o for o in project_objects(snapshot) if o['id'] not in baseline_ids[o['object_class']]]
        snapshots.append(dict(checkpoint=f'T{index}', start_after_exit_ms=start, project_objects=attributable))
    require(not snapshots[-1]['project_objects'] and state() == 'disabled', 'BPF teardown did not converge by deadline')
    return snapshots


def validate_response(response, status, prompt_n=None):
    require(status == 200 and isinstance(response, dict), 'HTTP request failed')
    timings = response.get('timings', {})
    for key in ('prompt_per_second', 'predicted_per_second', 'prompt_ms', 'predicted_ms'):
        value = timings.get(key)
        require(isinstance(value, (int, float)) and math.isfinite(value) and value > 0, f'Invalid timing: {key}')
    count = timings.get('prompt_n')
    require(isinstance(count, int) and 512 <= count <= 1536 and (prompt_n is None or count == prompt_n), 'Prompt token count mismatch')
    require(timings.get('cache_n') == 0 and timings.get('predicted_n') == 128, 'Cache/generation count mismatch')
    require(response.get('tokens_evaluated') == count and response.get('tokens_predicted') == 128, 'Response token counts disagree')
    require(not response.get('truncated', True) and bool(response.get('content')), 'Truncated or empty response')
    require(response.get('stop_type') == 'limit', 'Request stopped before the fixed generation limit')
    return count
