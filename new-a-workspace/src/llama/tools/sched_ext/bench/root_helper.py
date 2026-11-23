# SPDX-License-Identifier: GPL-2.0
"""One campaign, fixed privileged operations, blocking IPC/pidfd wait."""
import argparse
import json
import os
from pathlib import Path
import secrets
import re
import pwd
import select
import selectors
import signal
import socket
import struct
import subprocess
import sys
import time

# -I ignores caller Python configuration; import only this fixed source directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
from common import (HOUSE_CPUS, HOST, UID, RESULTS, SCHED, TAGS, bpf_timeline, canonical, identity,
                    live_project_processes, project_objects, read_json, reduced_bpf,
                    order, require, same_process, scheduler_check, sha, signal_exact,
                    state, write_json)

OPS = {'HELLO', 'CHECK', 'START', 'STOP', 'FINISH', 'ABORT'}
MAX_LIFETIME = 6 * 60 * 60
MAX_LOADER_LIFETIME = 20 * 60


def validate_message(message, token):
    require(isinstance(message, dict) and message.get('token') == token, 'Bad session token')
    op = message.get('op')
    require(op in OPS, 'Operation is not allowed')
    require(set(message) == ({'op', 'token', 'visit'} if op in {'START', 'STOP'} else {'op', 'token'}), 'Unexpected command arguments')
    if op in {'START', 'STOP'}:
        require(type(message['visit']) is int and 1 <= message['visit'] <= 40, 'Invalid visit')
    return op


class Helper:
    def __init__(self, run):
        self.run = run
        require(run.parent == RESULTS.resolve() and run.is_dir() and run.stat().st_uid == UID, 'Invalid campaign directory')
        self.manifest = read_json(run / 'manifest.json')
        require(self.manifest['status'] == 'PREPARED', 'Campaign is not prepared')
        require(self.manifest['tags'] == TAGS and self.manifest['uid'] == UID, 'Campaign identity differs')
        require(self.manifest['order'] == order(), 'Campaign order differs from the fixed loader whitelist')
        for name, digest in self.manifest['helper_sources'].items():
            require(sha(Path(__file__).parent / name) == digest, 'Helper source identity changed')
        require(sha(run / 'host-profile.json') == self.manifest['host_profile_sha256'] and read_json(run / 'host-profile.json') == HOST, 'Frozen campaign profile differs')
        scheduler_check()
        self.c_artifact = read_json(run / 'artifacts.json')['C']
        require(self.c_artifact['revision'] == TAGS['llama-side-lightweight-v1'] and self.c_artifact['hint'] == 'ON' and self.c_artifact['trace'] == 'OFF', 'C artifact definition differs')
        names = self.c_artifact['files']
        require({'bin/llama-server', 'bin/libllama-server-impl.so'} <= set(names), 'C server/marker identity absent')
        require(all(re.fullmatch(r'bin/(llama-server|lib[\w.-]+\.so(?:\.\d+)*)', name) for name in names), 'Artifact path is not allowed')
        require(state() == 'disabled' and not live_project_processes(), 'Another scheduler/server is active')
        self.baseline = reduced_bpf()
        write_json(run / 'bpf-baseline.json', self.baseline)
        require(not project_objects(self.baseline), 'Stale project BPF objects')
        self.token = secrets.token_hex(32)
        self.socket_name = 'llama_step10_priv_' + run.name
        self.listener = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        self.listener.bind('\0' + self.socket_name)
        self.listener.listen(1)
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.listener, selectors.EVENT_READ, 'ipc')
        self.wake_read, self.wake_write = os.pipe2(os.O_NONBLOCK | os.O_CLOEXEC)
        signal.set_wakeup_fd(self.wake_write)
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: None)
        self.selector.register(self.wake_read, selectors.EVENT_READ, 'signal')
        self.deadline = time.monotonic() + MAX_LIFETIME
        self.child = None
        self.last = None
        self.finished = False

    def ready(self):
        return dict(helper=identity(os.getpid()), socket=self.socket_name, token=self.token,
                    lifetime_seconds=MAX_LIFETIME, allowed_uid=UID, baseline='bpf-baseline.json')

    def append_log(self):
        data = os.read(self.child['process'].stderr.fileno(), 65536)
        if data:
            with open(self.child['log'], 'ab') as output:
                output.write(data)
            self.child['startup_output'] += data
        else:
            self.selector.unregister(self.child['process'].stderr)
        return data

    def start(self, visit):
        require(self.child is None and state() == 'disabled', 'Scheduler already active')
        require(order()[visit-1]['config'] == 'D', 'Only a frozen D visit may start the loader')
        require(self.last is None or visit > self.last['visit'], 'Visit cannot be reused')
        require(self.last is None or self.last.get('clean') and self.last['loader_exit'] == 0, 'Previous loader did not cleanly finish')
        scheduler_check()
        bundle = self.run / 'artifacts/C'
        require(bundle.resolve() == self.run / 'artifacts/C', 'Bundle path changed')
        for name, digest in self.c_artifact['files'].items():
            require((bundle / name).resolve().parent == bundle / 'bin', 'Runtime file path changed')
            require(sha(bundle / name) == digest, 'C runtime bundle changed')
        path = self.run / 'raw' / f'{visit:02d}-D'
        require(path.is_dir() and not path.is_symlink(), 'Visit directory is not ready')
        registration = 'llama_scx_step10_' + self.run.name + '_' + str(visit)
        argv = [str(SCHED / 'bin/llama_scx'), '--phase-uid', str(UID), '--phase-register-socket', '@' + registration,
                '--server-exe', str(bundle / 'bin/llama-server'), '--marker-elf', str(bundle / 'bin/libllama-server-impl.so')]
        env = {'PATH': '/usr/bin:/bin', 'LANG': 'C', 'HOME': pwd.getpwuid(0).pw_dir}
        process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.PIPE, env=env, cwd='/', start_new_session=True)
        try:
            saved = identity(process.pid)
        except Exception:
            # This is our unreaped direct child; its PID cannot be reused yet.
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=15)
            (path / 'loader.log').write_bytes(process.stderr.read())
            process.stderr.close()
            raise
        self.child = dict(process=process, identity=saved, visit=visit, log=path / 'loader.log',
                          socket='@' + registration, pidfd=os.pidfd_open(process.pid),
                          deadline=time.monotonic()+MAX_LOADER_LIFETIME, startup_output=b'', administrative_stop=False)
        self.selector.register(self.child['pidfd'], selectors.EVENT_READ, 'loader_exit')
        self.selector.register(process.stderr, selectors.EVENT_READ, 'loader_log')
        write_json(path / 'loader-command.json', dict(argv=argv, identity=saved))
        require(saved['uid'] == 0 and saved['policy'] == 0 and saved['affinity'] == sorted(HOUSE_CPUS), 'Loader identity/affinity differs')
        end = time.monotonic() + 20
        while b'scheduler active; waiting for selected child' not in self.child['startup_output']:
            require(time.monotonic() < end, 'Loader startup deadline exceeded')
            for key, _ in self.selector.select(max(0, end-time.monotonic())):
                if key.data == 'loader_log':
                    self.append_log()
                elif key.data == 'loader_exit':
                    self.reap()
                    raise RuntimeError('Loader exited during startup; see loader.log')
                elif key.data == 'signal':
                    raise RuntimeError('Helper received termination during startup')
        require(state() == 'enabled', 'Scheduler did not enable')
        return dict(loader=saved, registration_socket='@' + registration, argv=argv)

    def reap(self):
        child = self.child
        code = child['process'].wait(timeout=15)
        observed = time.monotonic()
        try:
            self.selector.unregister(child['process'].stderr)
        except KeyError:
            pass
        rest = child['process'].stderr.read()
        child['process'].stderr.close()
        with open(child['log'], 'ab') as output:
            output.write(rest)
        self.selector.unregister(child['pidfd'])
        os.close(child['pidfd'])
        self.child = None
        self.last = dict(visit=child['visit'], loader=child['identity'], loader_exit=code,
                         exit_observed_monotonic=observed, natural_teardown=True, loader_sigterm_requested=child['administrative_stop'])
        # No data-map read, observer or BPF deletion; finite snapshots after exit only.
        try:
            self.last['timeline'] = bpf_timeline(self.run / 'raw' / f"{child['visit']:02d}-D", 'teardown', self.baseline, observed)
            self.last['clean'] = state() == 'disabled'
        except Exception as error:
            self.last.update(clean=False, error=str(error))
        write_json(self.run / 'raw' / f"{child['visit']:02d}-D" / 'root-cleanup.json', self.last)
        return self.last

    def stop(self, visit, emergency=False):
        if self.child:
            require(self.child['visit'] == visit, 'Wrong active visit')
            natural = not emergency and select.select([self.child['pidfd']], [], [], 3)[0]
            if not natural and same_process(self.child['identity']):
                self.child['administrative_stop'] = True
                signal_exact(self.child['identity'], signal.SIGTERM)
            require(select.select([self.child['pidfd']], [], [], 15)[0], 'Loader did not exit after cleanup request')
            self.reap()
        require(self.last and self.last['visit'] == visit, 'No loader result for visit')
        require(self.last.get('clean'), f'Loader cleanup failed: {self.last}')
        return self.last

    def check(self):
        require(self.child is None and state() == 'disabled', 'Scheduler is still active')
        current = reduced_bpf()
        if project_objects(current):
            write_json(self.run / 'bpf-check-failure.json', current)
        require(not project_objects(current), 'Project BPF objects remain')
        return dict(sched_ext=state(), inventory=current, last=self.last)

    def serve(self):
        while not self.finished:
            deadline = min(self.deadline, self.child['deadline'] if self.child else self.deadline)
            events = self.selector.select(max(0, deadline-time.monotonic()))
            require(events, 'Helper safety deadline exceeded')
            for key, _ in events:
                if key.data == 'signal':
                    raise RuntimeError('Helper termination requested')
                if key.data == 'loader_log' and self.child:
                    self.append_log()
                elif key.data == 'loader_exit' and self.child:
                    self.reap()
                elif key.data == 'ipc':
                    self.handle_peer()

    def handle_peer(self):
        with self.listener.accept()[0] as peer:
            peer.settimeout(3)
            _, uid, _ = struct.unpack('3i', peer.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
            previous_child = self.child
            try:
                require(uid == UID, 'Only the frozen profile UID may use this helper')
                packet = peer.recv(4097)
                require(len(packet) <= 4096, 'Oversized command')
                message = json.loads(packet)
                op = validate_message(message, self.token)
                if op == 'HELLO':
                    result = self.ready()
                elif op == 'START':
                    result = self.start(message['visit'])
                elif op == 'STOP':
                    result = self.stop(message['visit'])
                elif op == 'CHECK':
                    result = self.check()
                else:
                    if op == 'ABORT' and self.child:
                        self.stop(self.child['visit'], emergency=True)
                    result = self.check()
                    write_json(self.run / 'bpf-final.json', result['inventory'])
                    self.finished = True
                peer.sendall(canonical(dict(ok=True, result=result)))
            except Exception as error:
                if 'op' in locals() and op == 'START' and self.child and self.child is not previous_child:
                    try:
                        self.stop(self.child['visit'], emergency=True)
                    except Exception as cleanup:
                        write_json(self.run / 'loader-start-cleanup-error.json', dict(error=str(cleanup)))
                try:
                    peer.sendall(canonical(dict(ok=False, error=str(error))))
                except (BrokenPipeError, ConnectionResetError):
                    pass

    def close(self):
        if self.child:
            self.stop(self.child['visit'], emergency=True)
        self.listener.close()
        self.selector.close()
        signal.set_wakeup_fd(-1)
        os.close(self.wake_read)
        os.close(self.wake_write)


def arm(run):
    require(os.getuid() == 0, 'Root privilege is required for this helper')
    common.load_profile(run / 'host-profile.json')
    require(int(os.environ.get('SUDO_UID', '-1')) == UID, 'Sudo invoking UID differs from frozen profile')
    import host_profile
    host_profile.validate_current(HOST)
    require(os.sched_getaffinity(0) == HOUSE_CPUS, 'Root helper must use the frozen housekeeping set')
    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid:
        os.close(write_fd)
        require(select.select([read_fd], [], [], 30)[0], 'Helper did not become ready')
        with os.fdopen(read_fd) as stream:
            result = json.loads(stream.readline())
        require(result.get('ok'), f'Helper startup failed: {result}')
        print(json.dumps(result['result']))
        return
    os.close(read_fd)
    os.setsid()
    log_fd = os.open(run / 'root-helper.log', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    for target in (1, 2):
        os.dup2(log_fd, target)
    os.close(log_fd)
    null_fd = os.open('/dev/null', os.O_RDONLY)
    os.dup2(null_fd, 0)
    os.close(null_fd)
    helper = None
    try:
        helper = Helper(run)
        os.write(write_fd, canonical(dict(ok=True, result=helper.ready())))
        os.close(write_fd)
        write_fd = -1
        helper.serve()
        helper.close()
        os._exit(0)
    except BaseException as error:
        if write_fd >= 0:
            os.write(write_fd, canonical(dict(ok=False, error=str(error))))
            os.close(write_fd)
        print(f'Root helper failure: {error}', file=sys.stderr, flush=True)
        if helper:
            try:
                helper.close()
            except Exception as cleanup:
                print(f'Cleanup failure: {cleanup}', file=sys.stderr, flush=True)
        os._exit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arm', type=Path, required=True)
    args = parser.parse_args()
    arm(args.arm.resolve())
