# SPDX-License-Identifier: GPL-2.0
"""Bounded selected-child sessions; never alter the frozen root helper."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import identity, require, same_process, signal_exact, state, write_json

CHILD = HERE.parent / 'scheduler/llama_scx_child'


def active_experiments():
    found = []
    runners = {'runtime.py', 'compare.py', 'linux_smoke.py', 'step10.py', 'root_helper.py'}
    for path in Path('/proc').glob('[0-9]*'):
        if int(path.name) == os.getpid():
            continue
        try:
            name = (path / 'comm').read_text().strip()
            try:
                argv = (path / 'cmdline').read_bytes().decode(errors='replace').rstrip('\0').split('\0')
            except OSError:
                argv = []
            try:
                is_ext = os.sched_getscheduler(int(path.name)) == 7
            except (PermissionError, ProcessLookupError):
                is_ext = False
            is_runner = name.startswith('python') and any(Path(arg).name in runners for arg in argv[1:])
            if name.startswith(('llama_new_a', 'llama_scx', 'llama-server', 'wake_probe')) or is_runner or is_ext:
                found.append(dict(pid=int(path.name), comm=name, argv=argv))
        except (OSError, ProcessLookupError):
            pass
    return found


def check_privileges():
    require(os.getuid() != 0 and os.sched_getscheduler(0) == os.SCHED_OTHER,
            'Run this tool as the normal repository owner under Linux scheduling')
    result = subprocess.run(['sudo', '-n', 'true'], capture_output=True, text=True)
    require(result.returncode == 0, 'Runtime requires a terminal sudo credential: run sudo -v first. ' + result.stderr.strip())
    require(state() == 'disabled', 'Another sched_ext scheduler is active')
    require(not active_experiments(), 'Another project runtime/experiment is active; inspect it before loading sched_ext')


def wait_until(predicate, seconds, message):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise RuntimeError(message)


class Session:
    def __init__(self, path, argv, cpus, housekeeping, *, policy='C', topology=None, env=None,
                 diagnostics=False, pass_fds=(), marker=None, loader_binary=None, child_binary=None):
        self.path, self.argv = Path(path), list(map(str, argv))
        self.cpus, self.housekeeping = set(cpus), set(housekeeping)
        self.policy, self.topology = policy, topology
        self.env, self.diagnostics, self.pass_fds = env, diagnostics, pass_fds
        self.marker = marker or self.argv[0]
        self.loader_binary, self.child_binary = loader_binary, child_binary
        self.process = self.loader = None
        self.server = self.loader_identity = None
        self.logs = []
        self.socket = '@llama-new-a-' + uuid.uuid4().hex

    def log(self, name):
        output = (self.path / name).open('xb')
        self.logs.append(output)
        return output

    def start(self):
        self.path.mkdir(parents=True, exist_ok=True)
        require(state() == 'disabled', 'sched_ext must be disabled at session start')
        argv = self.argv
        if self.policy != 'C':
            if self.policy == 'D':
                loader = HERE.parent / 'build/bin/llama_scx'
                prefix = []
            else:
                loader = self.loader_binary or HERE / ('build/bin/llama_new_a_diag' if self.diagnostics else 'build/bin/llama_new_a')
                prefix = ['--topology', str(self.topology)]
                if self.diagnostics:
                    prefix += ['--diagnostics-output', str(self.path / 'scheduler-stats.json')]
            loader_argv = ['sudo', '-n', 'taskset', '-c', ','.join(map(str, sorted(self.housekeeping))), str(loader), *prefix,
                           '--phase-uid', str(os.getuid()), '--phase-register-socket', self.socket,
                           '--server-exe', argv[0], '--marker-elf', str(self.marker)]
            write_json(self.path / 'loader-command.json', loader_argv)
            self.loader = subprocess.Popen(loader_argv, stdin=subprocess.DEVNULL,
                                           stdout=self.log('loader.stdout.log'), stderr=self.log('loader.log'))
            self.loader_identity = identity(self.loader.pid)
            def attached():
                require(self.loader.poll() is None, 'Loader failed; preserve and inspect loader.log (including verifier output)')
                return state() == 'enabled' and 'waiting for selected child' in (self.path / 'loader.log').read_text()
            wait_until(attached, 20, 'Scheduler attach deadline exceeded')
            argv = [str(self.child_binary or CHILD), '--phase-register-socket', self.socket, '--', *argv]
        write_json(self.path / 'command.json', dict(argv=argv, cpus=sorted(self.cpus), policy=self.policy))
        self.process = subprocess.Popen(argv, env=self.env, stdin=subprocess.DEVNULL,
                                        stdout=self.log('server.stdout.log'), stderr=self.log('server.stderr.log'),
                                        pass_fds=self.pass_fds, preexec_fn=lambda: os.sched_setaffinity(0, self.cpus))
        if self.policy == 'C':
            self.server = identity(self.process.pid)
        else:
            import re
            def registered():
                require(self.process.poll() is None and self.loader.poll() is None, 'Selected child or loader exited before registration')
                output = (self.path / 'server.stdout.log').read_text()
                match = re.search(r'phase_uprobe_registered_tgid=(\d+)', output)
                if not match:
                    # Retain a child identity for cleanup even if registration fails.
                    child = re.search(r'child_pid=(\d+)', output)
                    if child:
                        self.server = identity(int(child.group(1)))
                    return False
                self.server = identity(int(match.group(1)))
                return True
            wait_until(registered, 30, 'Selected-child registration deadline exceeded')
            os.sched_setaffinity(self.process.pid, self.housekeeping)
        require(self.server['uid'] == os.getuid(), 'Selected UID differs')
        require(self.server['policy'] == (0 if self.policy == 'C' else 7), 'Selected policy differs')
        require(set(self.server['affinity']) == self.cpus, 'Selected affinity differs')
        write_json(self.path / 'processes.json', dict(server=self.server, parent=identity(self.process.pid),
                                                   sudo=self.loader_identity))
        return self

    def close(self, *, natural=False):
        errors = []
        if self.process and self.server is None:
            import re
            output = self.path / 'server.stdout.log'
            match = re.search(r'child_pid=(\d+)', output.read_text()) if output.exists() else None
            if match:
                try:
                    child = identity(int(match.group(1)))
                    if child['ppid'] == self.process.pid and child['uid'] == os.getuid():
                        self.server = child
                except ProcessLookupError:
                    pass
        if self.process:
            try:
                if not natural and self.server and same_process(self.server):
                    signal_exact(self.server, signal.SIGTERM)
                code = self.process.wait(timeout=15)
                require(code == 0, f'Server/launcher exit={code}')
            except Exception as error:
                errors.append(str(error))
                if self.server and same_process(self.server):
                    signal_exact(self.server, signal.SIGKILL)
                if self.process.poll() is None:
                    self.process.terminate()
                    self.process.wait(timeout=10)
        if self.loader:
            try:
                if errors or self.server is None:
                    if self.loader.poll() is None and same_process(self.loader_identity):
                        # sudo relays the signal to the command it owns.
                        subprocess.run(['sudo', '-n', 'kill', '-TERM', str(self.loader.pid)], check=True, capture_output=True)
                require(self.loader.wait(timeout=15) == 0, 'Loader failed; see complete verifier/exit log')
            except Exception as error:
                errors.append(str(error))
                if self.loader.poll() is None and same_process(self.loader_identity):
                    subprocess.run(['sudo', '-n', 'kill', '-TERM', str(self.loader.pid)], check=True, capture_output=True)
                    self.loader.wait(timeout=15)
        for output in self.logs:
            output.close()
        require(state() == 'disabled', 'Scheduler did not detach')
        write_json(self.path / 'cleanup.json', dict(status='FAILED' if errors else 'PASS', errors=errors, sched_ext=state()))
        require(not errors, '; '.join(errors))

    def __enter__(self):
        try:
            return self.start()
        except BaseException:
            self.close()
            raise

    def __exit__(self, kind, value, traceback):
        self.close(natural=bool(getattr(self, 'natural', False) and kind is None))
