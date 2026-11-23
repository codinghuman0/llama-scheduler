# SPDX-License-Identifier: GPL-2.0
"""Synthetic and non-workload checks; never load BPF or send HTTP."""
import hashlib
import json
from contextlib import ExitStack
import os
from pathlib import Path
import signal
import socket
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import analysis
import common
import machine
import root_helper
import step10


def synthetic_host():
    common.HOST.clear()
    common.HOST.update(allocation=dict(status='PASS', reason=None), capabilities=dict(temperature_sensor='unavailable'))
    common.SERVER_CPUS.clear()
    common.SERVER_CPUS.update({3, 9})
    common.HOUSE_CPUS.clear()
    common.HOUSE_CPUS.update({17})
    common.THREADS.update(compute=2, batch=2, http=2)


def response():
    return dict(content='synthetic fixture', truncated=False, stop_type='limit', tokens_evaluated=900,
                tokens_predicted=128, timings=dict(cache_n=0, prompt_n=900, predicted_n=128,
                prompt_per_second=100.0, predicted_per_second=20.0, prompt_ms=9000.0, predicted_ms=6400.0))


class CampaignTests(unittest.TestCase):
    def setUp(self):
        synthetic_host()

    def test_all_phases_require_closed_apps_before_work(self):
        for phase in ('prepare', 'arm', 'campaign', 'finalize'):
            with self.subTest(phase=phase), patch.object(machine, 'stop_codex_daemons', return_value=[]) as stop, \
                 patch.object(machine, 'reject_interactive_apps', side_effect=RuntimeError('application active')), \
                 patch.object(step10, phase) as execute:
                with self.assertRaisesRegex(RuntimeError, 'application active'):
                    step10.run_phase(phase)
                execute.assert_not_called()
                self.assertEqual(stop.call_count, int(phase == 'prepare'))

    def test_quiet_preparation_reaps_daemons_before_reuse(self):
        events = []
        with patch.object(machine, 'stop_codex_daemons', side_effect=lambda: events.append('stop') or []), \
             patch.object(machine, 'reject_interactive_apps', side_effect=lambda: events.append('check')), \
             patch.object(step10, 'prepare', side_effect=lambda **_: events.append('prepare')) as execute:
            step10.run_phase('prepare', reuse_artifacts=True)
        self.assertEqual(events, ['stop', 'check', 'prepare'])
        execute.assert_called_once_with(reuse_artifacts=True)

    def test_hangup_handler_requests_normal_phase_cleanup(self):
        handlers = {}
        with patch.object(sys, 'argv', ['step10.py', 'prepare']), \
             patch.object(step10.signal, 'signal', side_effect=lambda sig, handler: handlers.__setitem__(sig, handler)), \
             patch.object(step10, 'run_phase') as execute:
            with patch.object(common, 'load_profile'), patch.object(step10.host_profile, 'validate_current'), \
                 patch.object(step10.os, 'sched_setaffinity'), patch.object(step10.os, 'sched_getaffinity', return_value=common.HOUSE_CPUS):
                step10.main()
            execute.assert_called_once_with('prepare', reuse_artifacts=False)
        self.assertEqual(set(handlers), {signal.SIGHUP, signal.SIGINT, signal.SIGTERM})
        with self.assertRaisesRegex(RuntimeError, 'interrupted by signal'):
            handlers[signal.SIGHUP](signal.SIGHUP, None)

    def test_unused_preparation_replacement_refuses_any_runtime_or_request(self):
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp)
            (run / 'raw').mkdir()
            common.write_json(run / 'manifest.json', dict(status='PREPARED'))
            self.assertTrue(step10.replaceable_campaign(run))
            for path in (run / 'armed.json', run / 'raw/01-A', run / 'CAMPAIGN_COMPLETE'):
                path.write_text('evidence')
                self.assertFalse(step10.replaceable_campaign(run))
                path.unlink()
            for status in ('ARMED', 'RUNNING', 'CAMPAIGN_COMPLETE', 'PREPARING'):
                common.write_json(run / 'manifest.json', dict(status=status))
                self.assertFalse(step10.replaceable_campaign(run))
            common.write_json(run / 'manifest.json', dict(status='FAILED'))
            self.assertTrue(step10.replaceable_campaign(run))

    def test_reuse_preparation_supersedes_only_unused_run_and_preserves_evidence(self):
        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            root = Path(temp)
            results = root / 'results'
            previous = results / '20261006T010203Z'
            (previous / 'raw').mkdir(parents=True)
            (previous / 'evidence.txt').write_text('retain original preparation')
            common.write_json(previous / 'manifest.json', dict(status='PREPARED'))
            (results / '.active-run').write_text(previous.name)
            protocol = root / 'tools/sched_ext/BENCHMARK_PROTOCOL.md'
            protocol.parent.mkdir(parents=True)
            protocol.write_text('synthetic protocol')
            cache = dict(option[2:].split('=', 1) for option in step10.CMAKE_OPTIONS if option.startswith('-D'))
            artifacts = {cfg: dict(cache_subset=cache, files={}) for cfg in 'ABC'}
            for module in (common, step10):
                stack.enter_context(patch.object(module, 'RESULTS', results))
            stack.enter_context(patch.object(step10, 'REPO', root))
            stack.enter_context(patch.object(step10, 'repo_check', return_value='fixture'))
            stack.enter_context(patch.object(step10, 'scheduler_check'))
            stack.enter_context(patch.object(step10, 'state', return_value='disabled'))
            stack.enter_context(patch.object(step10, 'live_project_processes', return_value=[]))
            stack.enter_context(patch.object(step10, 'topology', return_value={}))
            stack.enter_context(patch.object(step10, 'model_identity', return_value={}))
            stack.enter_context(patch.object(step10, 'toolchain', return_value={}))
            profile = root / 'host-profile.json'
            common.write_json(profile, common.HOST)
            stack.enter_context(patch.object(step10, 'PROFILE_PATH', profile))
            stack.enter_context(patch.object(step10.host_profile, 'validate_current'))
            stack.enter_context(patch.object(step10, 'validate_entry_points'))
            stack.enter_context(patch.object(step10, 'require_no_helper'))
            stack.enter_context(patch.object(step10, 'sources', return_value={}))
            stack.enter_context(patch.object(step10, 'sha', return_value='fixture'))
            stack.enter_context(patch.object(step10, 'protocol_identity', return_value={}))
            stack.enter_context(patch.object(step10, 'validate_artifacts'))
            reuse = stack.enter_context(patch.object(step10, 'reuse_bundles', return_value=artifacts))
            build = stack.enter_context(patch.object(step10, 'build_bundle'))
            stack.enter_context(patch('builtins.print'))
            step10.prepare(reuse_artifacts=True)
            new = common.active_run()
            old = common.read_json(previous / 'manifest.json')
            self.assertNotEqual(new, previous)
            self.assertEqual(old['status'], 'SUPERSEDED')
            self.assertEqual(old['replacement'], new.name)
            self.assertEqual((previous / 'evidence.txt').read_text(), 'retain original preparation')
            self.assertEqual(common.read_json(new / 'manifest.json')['status'], 'PREPARED')
            self.assertTrue(common.read_json(new / 'manifest.json')['quiet_all_phases'])
            self.assertEqual(list((new / 'raw').iterdir()), [])
            reuse.assert_called_once_with(new, previous, {})
            build.assert_not_called()

    def test_command_streams_large_output_and_preserves_failure_log(self):
        with tempfile.TemporaryDirectory() as temp:
            log = Path(temp) / 'build.log'
            result = common.command([sys.executable, '-c', 'print("fixture" * 100000)'], log=log, capture=False)
            self.assertEqual(result, '')
            self.assertEqual(log.stat().st_size, 700001)
            with self.assertRaisesRegex(RuntimeError, 'Full log:') as caught:
                common.command([sys.executable, '-c', 'print("failure" * 100000); raise SystemExit(2)'], log=log, capture=False)
            self.assertEqual(log.stat().st_size, 700001)
            self.assertLess(len(str(caught.exception)), 9000)

    def test_interrupted_streaming_command_reaps_only_owned_process_group(self):
        process = subprocess.Popen(['/usr/bin/sleep', '30'], start_new_session=True)
        wait = process.wait
        calls = [0]
        def interrupted_wait(*args, **kwargs):
            calls[0] += 1
            if calls[0] == 1:
                raise RuntimeError('synthetic hangup')
            return wait(*args, **kwargs)
        try:
            with tempfile.TemporaryDirectory() as temp, patch.object(common.subprocess, 'Popen', return_value=process), \
                 patch.object(process, 'wait', side_effect=interrupted_wait):
                with self.assertRaisesRegex(RuntimeError, 'synthetic hangup'):
                    common.command(['/usr/bin/sleep', '30'], log=Path(temp) / 'build.log', capture=False)
            self.assertEqual(process.poll(), -signal.SIGTERM)
        finally:
            if process.poll() is None:
                process.kill()
                wait()

    def test_port_check_rejects_a_live_listener(self):
        with socket.socket() as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(('127.0.0.1', 0))
            listener.listen(1)
            with patch.object(common, 'PORT', listener.getsockname()[1]):
                with self.assertRaises(OSError):
                    common.port_free()

    def test_port_check_accepts_closed_connections_in_time_wait(self):
        with socket.socket() as listener, socket.socket() as client:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(('127.0.0.1', 0))
            address = listener.getsockname()
            listener.listen(1)
            client.settimeout(2)
            client.connect(address)
            accepted, _ = listener.accept()
            accepted.close()
            self.assertEqual(client.recv(1), b'')
        # The old plain bind must fail, proving this fixture exercises TIME_WAIT.
        with socket.socket() as old_probe:
            with self.assertRaises(OSError):
                old_probe.bind(address)
        with patch.object(common, 'PORT', address[1]):
            common.port_free()

    def test_codex_gate_does_not_exempt_managed_daemons(self):
        daemon = str(Path.home() / '.codex/packages/app-server-daemon/releases/fixture/bin/codex')
        argv = [daemon, 'app-server', '--listen', 'unix://', '--managed-daemon']
        self.assertTrue(machine.managed_codex_daemon(argv))
        for other in ([daemon], ['/usr/bin/codex', *argv[1:]], [daemon, *argv[1:], '--extra'], ['/bin/sleep', '30']):
            self.assertFalse(machine.managed_codex_daemon(other))
        with patch.object(machine, 'command', return_value='123 codex 0.0 ' + ' '.join(argv)):
            with self.assertRaisesRegex(RuntimeError, 'stop-codex-daemons'):
                machine.reject_interactive_apps()

    def test_daemon_shutdown_refuses_an_active_cli_before_any_signal(self):
        with patch.object(machine, 'interactive_apps', return_value=([], ['123 codex 0.0 /usr/bin/codex'])), \
             patch.object(Path, 'read_bytes', return_value=b'/usr/bin/codex\0'), \
             patch.object(machine, 'identity', return_value=dict(pid=123, uids=[common.UID]*4)), \
             patch.object(machine, 'signal_exact') as send:
            with self.assertRaisesRegex(RuntimeError, 'Exit interactive'):
                machine.stop_codex_daemons()
            send.assert_not_called()

    def test_daemon_shutdown_uses_only_verified_identity_and_sigterm(self):
        daemon = str(Path.home() / '.codex/packages/app-server-daemon/releases/fixture/bin/codex')
        argv = [daemon, 'app-server', '--listen', 'unix://', '--managed-daemon']
        saved = dict(pid=123, starttime='fixture', uids=[common.UID]*4)
        alive = [True]
        with patch.object(machine, 'interactive_apps', return_value=([], ['123 codex 0.0 ' + ' '.join(argv)])), \
             patch.object(Path, 'read_bytes', return_value=('\0'.join(argv)+'\0').encode()), \
             patch.object(machine, 'identity', return_value=saved), \
             patch.object(machine, 'same_process', side_effect=lambda _: alive[0]), \
             patch.object(machine, 'reject_interactive_apps'), \
             patch.object(machine, 'signal_exact', side_effect=lambda *_: alive.__setitem__(0, False)) as send:
            self.assertEqual(machine.stop_codex_daemons(), [saved])
            send.assert_called_once_with(saved, signal.SIGTERM)

    def test_registration_waits_for_asynchronously_written_loader_log(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            bundle = path / 'bundle'
            server = dict(pid=123, ppid=122, uids=[common.UID]*4)
            (path / 'server.stdout.log').write_text('phase_uprobe_registered_tgid=123\n')
            original_resolve = Path.resolve
            def resolve(value, *args, **kwargs):
                return bundle / 'bin/llama-server' if str(value) == '/proc/123/exe' else original_resolve(value, *args, **kwargs)
            with patch.object(step10, 'identity', return_value=server), patch.object(Path, 'resolve', resolve):
                self.assertEqual(step10.registered_child(path, dict(pid=122), bundle), (server, False))
                (path / 'loader.log').write_text(f'llama_scx: registered tgid=123 uid={common.UID}\n')
                self.assertEqual(step10.registered_child(path, dict(pid=122), bundle), (server, True))

    def test_failed_loader_start_is_rolled_back_before_error_response(self):
        helper = root_helper.Helper.__new__(root_helper.Helper)
        helper.child, helper.token = None, 'fixture'
        for existing in (False, True):
            server, client = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
            try:
                helper.child = dict(visit=4) if existing else None
                helper.listener = Mock()
                helper.listener.accept.return_value = (server, None)
                def failing_start(_visit):
                    if not existing:
                        helper.child = dict(visit=4)
                    raise RuntimeError('synthetic startup failure')
                helper.start = Mock(side_effect=failing_start)
                helper.stop = Mock(side_effect=lambda *_args, **_kwargs: setattr(helper, 'child', None))
                client.sendall(common.canonical(dict(op='START', token='fixture', visit=4)))
                helper.handle_peer()
                result = json.loads(client.recv(4096))
                self.assertFalse(result['ok'])
                if existing:
                    helper.stop.assert_not_called()
                else:
                    helper.stop.assert_called_once_with(4, emergency=True)
            finally:
                server.close()
                client.close()

    def test_loader_identity_failure_reaps_our_direct_child(self):
        process = subprocess.Popen(['/usr/bin/sleep','30'], stderr=subprocess.PIPE)
        try:
            with tempfile.TemporaryDirectory() as temp:
                run = Path(temp)
                (run/'artifacts/C/bin').mkdir(parents=True)
                (run/'artifacts/C/bin/llama-server').write_text('fixture')
                (run/'raw/04-D').mkdir(parents=True)
                helper = root_helper.Helper.__new__(root_helper.Helper)
                helper.run, helper.child, helper.last = run, None, None
                helper.c_artifact = dict(files={'bin/llama-server':'fixture'})
                with patch.object(root_helper,'state',return_value='disabled'), patch.object(root_helper,'scheduler_check'), \
                     patch.object(root_helper,'sha',return_value='fixture'), patch.object(root_helper.subprocess,'Popen',return_value=process), \
                     patch.object(root_helper,'identity',side_effect=RuntimeError('synthetic identity failure')):
                    with self.assertRaisesRegex(RuntimeError,'synthetic identity failure'):
                        helper.start(4)
                self.assertIsNotNone(process.poll())
                self.assertTrue((run/'raw/04-D/loader.log').exists())
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            process.stderr.close()

    def simulate_campaign(self, run, *, fail_visit=None, fail_order=False, blocked=False):
        common.write_json(run / 'manifest.json', dict(status='ARMED', head='fixture', btf_sha256='fixture'))
        common.write_json(run / 'machine.json', dict(before={}))
        common.write_json(run / 'armed.json', dict(helper={}))
        visits, operations, alive = [], [], [True]
        def helper(_run, operation):
            operations.append(operation)
            if operation in {'FINISH', 'ABORT'}:
                alive[0] = False
            return dict(helper=dict(policy=0, affinity=sorted(common.HOUSE_CPUS)))
        def visit(_run, plan, _baseline, _count):
            visits.append(plan['visit'])
            if plan['visit'] == fail_visit:
                raise RuntimeError('synthetic visit failure')
            return 900
        with ExitStack() as stack:
            for name, value in dict(active_run=lambda: run, require_status=lambda *_: common.read_json(run/'manifest.json'),
                                    validate_artifacts=lambda *_a, **_k: None, live_project_processes=lambda: [], state=lambda: 'disabled',
                                    helper_request=helper, visit=visit, sha=lambda _: 'fixture', repo_check=lambda: 'fixture',
                                    model_identity=lambda: {}, port_free=lambda: None, wait_gone=lambda _: None,
                                    same_process=lambda _: alive[0]).items():
                stack.enter_context(patch.object(step10, name, value))
            stack.enter_context(patch.object(step10.os, 'sched_getaffinity', return_value=common.HOUSE_CPUS))
            stack.enter_context(patch.object(step10.os, 'sched_getscheduler', return_value=0))
            stack.enter_context(patch.object(machine, 'snapshot', return_value={}))
            stack.enter_context(patch.object(machine, 'validate'))
            stack.enter_context(patch.object(machine, 'readiness'))
            stack.enter_context(patch.object(machine, 'reject_interactive_apps', side_effect=RuntimeError('synthetic app blocker') if blocked else None, return_value=[]))
            if fail_order:
                stack.enter_context(patch.object(step10, 'order', side_effect=RuntimeError('synthetic order failure')))
            if blocked or fail_visit or fail_order:
                with self.assertRaisesRegex(RuntimeError, 'synthetic'):
                    step10.campaign()
            else:
                step10.campaign()
        return visits, operations

    def test_all_40_campaign_visits_and_final_cleanup(self):
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp)
            visits, operations = self.simulate_campaign(run)
            self.assertEqual(visits, list(range(1, 41)))
            self.assertEqual(operations, ['HELLO', 'FINISH'])
            self.assertEqual(common.read_json(run/'manifest.json')['status'], 'CAMPAIGN_COMPLETE')
            self.assertTrue((run/'CAMPAIGN_COMPLETE').exists())

    def test_campaign_failure_aborts_without_replacing_sample(self):
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp)
            visits, operations = self.simulate_campaign(run, fail_visit=4)
            self.assertEqual(visits, [1, 2, 3, 4])
            self.assertEqual(operations, ['HELLO', 'ABORT'])
            self.assertEqual(common.read_json(run/'manifest.json')['status'], 'FAILED')
            self.assertFalse((run/'CAMPAIGN_COMPLETE').exists())

    def test_failure_before_first_visit_preserves_original_error(self):
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp)
            self.simulate_campaign(run, fail_order=True)
            value = common.read_json(run/'manifest.json')
            self.assertEqual(value['error'], 'synthetic order failure')
            self.assertIsNone(value['invalid_block'])

    def test_app_refusal_before_requests_leaves_campaign_armed(self):
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp)
            visits, operations = self.simulate_campaign(run, blocked=True)
            self.assertEqual((visits, operations), ([], []))
            self.assertEqual(common.read_json(run/'manifest.json')['status'], 'ARMED')

    def test_arming_handshake_failure_disarms_helper_and_records_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp)
            common.write_json(run/'manifest.json', dict(status='PREPARED', kernel='fixture', boot_id='fixture', btf_sha256='fixture'))
            ready = dict(helper=dict(uid=0, policy=0, affinity=sorted(common.HOUSE_CPUS)))
            calls = []
            def request(_run, op):
                calls.append(op)
                if op == 'CHECK':
                    raise RuntimeError('synthetic handshake failure')
                return {}
            with patch.object(step10, 'active_run', return_value=run), \
                 patch.object(step10, 'require_status', side_effect=lambda *_: common.read_json(run/'manifest.json')), \
                 patch.object(step10, 'validate_artifacts'), patch.object(step10, 'state', return_value='disabled'), \
                 patch.object(step10, 'live_project_processes', return_value=[]), patch.object(step10, 'require_no_helper'), \
                 patch.object(step10, 'port_free'), patch.object(machine, 'snapshot', return_value=dict(kernel='fixture', boot_id='fixture')), \
                 patch.object(machine, 'validate'), patch.object(step10, 'sha', return_value='fixture'), \
                 patch.object(step10, 'audit_command', return_value=json.dumps(ready)), \
                 patch.object(step10, 'helper_request', side_effect=request), patch.object(step10, 'wait_gone') as gone:
                with self.assertRaisesRegex(RuntimeError, 'handshake failure'):
                    step10.arm()
                self.assertEqual(calls, ['HELLO', 'CHECK', 'ABORT'])
                gone.assert_called_once_with(ready['helper'])
                self.assertEqual(common.read_json(run/'manifest.json')['status'], 'FAILED')

    def test_visit_cleans_child_even_if_saving_failure_evidence_fails(self):
        process = subprocess.Popen(['/usr/bin/sleep', '30'])
        try:
            saved = common.identity(process.pid)
            with tempfile.TemporaryDirectory() as temp:
                run = Path(temp)
                (run/'raw').mkdir()
                def save(path, value):
                    if path.name=='visit.json' and value.get('status')=='INVALID':
                        raise OSError('synthetic disk full')
                    common.write_json(path, value)
                with patch.object(step10.subprocess, 'Popen', return_value=process), \
                     patch.object(step10, 'helper_request', return_value={}), patch.object(step10, 'port_free'), \
                     patch.object(step10, 'health', side_effect=RuntimeError('synthetic startup error')), \
                     patch.object(step10, 'live_project_processes', return_value=[]), patch.object(step10, 'state', return_value='disabled'), \
                     patch.object(step10, 'write_json', side_effect=save):
                    with self.assertRaisesRegex(RuntimeError, 'synthetic startup error'):
                        step10.visit(run,common.order()[0],{},None)
                self.assertIsNotNone(process.poll())
                self.assertFalse(common.same_process(saved))
                cleanup=common.read_json(run/'raw/01-A/cleanup.json')
                self.assertEqual(cleanup['status'],'FAILED')
                self.assertIn('disk full',cleanup['errors'][0])
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()

    def test_reuse_build_bundles_preserves_bytes_and_never_reuses_samples(self):
        with tempfile.TemporaryDirectory() as temp:
            previous, run = Path(temp)/'old', Path(temp)/'new'
            previous.mkdir()
            run.mkdir()
            tools = dict(versions=dict(make='GNU Make 4.3\nOriginal localized license'), compiler_hashes={'cc':'fixture'})
            current_tools = tools | dict(versions=dict(make='GNU Make 4.3\nDifferent localized license'))
            (previous/'protocol.md').write_text('saved protocol with the previous workflow')
            old_manifest = dict(status='FAILED', head='fixture', toolchain=tools, tags=common.TAGS, topology={},
                                protocol={'sha256':common.sha(previous/'protocol.md')}, request_sha256=common.REQUEST_SHA,
                                prompt_sha256=common.PROMPT_SHA, metrics=list(analysis.METRICS), warmups_per_visit=2,
                                measured_per_config=10, bootstrap_seed=20261006, bootstrap_draws=10000,
                                order=common.order(), scheduler_hashes=common.SCHED_HASHES, uid=common.UID)
            common.write_json(previous/'manifest.json', old_manifest)
            artifacts = {}
            for cfg in 'ABC':
                bundle, metadata = previous/'artifacts'/cfg, previous/'builds'/cfg
                (bundle/'bin').mkdir(parents=True)
                metadata.mkdir(parents=True)
                (bundle/'bin/llama-server').write_bytes(b'synthetic runtime')
                hint = 'absent' if cfg=='A' else 'ON' if cfg=='C' else 'OFF'
                options = step10.CMAKE_OPTIONS + ([] if cfg=='A' else ['-DLLAMA_SCX_PHASE_HINT='+hint, '-DLLAMA_SCX_PHASE_TRACE=OFF'])
                cache = dict(option[2:].split('=', 1) for option in options if option.startswith('-D'))
                cache['CMAKE_CXX_FLAGS_RELEASE'] = '-O3 -DNDEBUG'
                record = dict(hint=hint, trace='absent' if cfg=='A' else 'OFF', cache_subset=cache, configure_argv=['cmake','-S','source','-B','build']+options,
                              files={'bin/llama-server':common.sha(bundle/'bin/llama-server')}, version='fixture')
                artifacts[cfg] = record
                common.write_json(metadata/'identity.json', record)
            (previous/'raw').mkdir()
            (previous/'raw/failed-sample.json').write_text('must stay in old campaign')
            with patch.object(step10, 'topology', return_value={}), patch.object(step10, 'protocol_identity', return_value={'sha256':'workflow-only amendment'}), \
                 patch.object(step10, 'validate_artifacts', return_value=artifacts), \
                 patch.object(step10, 'dependencies', return_value=('synthetic dependency resolution', [])), \
                 patch.object(step10, 'audit_command', return_value='fixture') as commands:
                step10.reuse_bundles(run, previous, current_tools)
                self.assertEqual(commands.call_count, 3)
                self.assertTrue(all(c.args[1][-1]=='--version' for c in commands.call_args_list))
                for cfg in 'ABC':
                    old, new = previous/'artifacts'/cfg/'bin/llama-server', run/'artifacts'/cfg/'bin/llama-server'
                    self.assertEqual((old.stat().st_ino, old.stat().st_dev), (new.stat().st_ino, new.stat().st_dev))
                self.assertFalse((run/'raw').exists())
                self.assertEqual((previous/'raw/failed-sample.json').read_text(), 'must stay in old campaign')
                self.assertEqual(common.read_json(run/'reused-artifacts.json')['source_protocol'], old_manifest['protocol'])
                old_manifest['request_sha256'] = 'different workload'
                common.write_json(previous/'manifest.json', old_manifest)
                with self.assertRaisesRegex(RuntimeError, 'measurement identity differs'):
                    step10.reuse_bundles(Path(temp)/'changed-request', previous, current_tools)
                old_manifest['request_sha256'] = common.REQUEST_SHA
                common.write_json(previous/'manifest.json', old_manifest)
                damaged = artifacts['B']['cache_subset']
                damaged['GGML_CUDA'] = 'ON'
                another = Path(temp)/'invalid'
                another.mkdir()
                with self.assertRaisesRegex(RuntimeError, 'build option differs'):
                    step10.reuse_bundles(another, previous, current_tools)

    def test_large_slowdown_gate_is_not_downgraded_by_wide_interval(self):
        rows = [plan | dict(prefill_tps=100, decode_tps=20, request_wall_ms=1000*(1.1 if plan['config']=='D' else 1)) for plan in common.order()]
        with patch.object(analysis, 'percentile', side_effect=lambda _values, fraction: 0 if fraction==0.025 else 2):
            pair = analysis.summarize(rows)['pairs']['C->D']
        self.assertTrue(pair['metrics']['request_wall_ms']['precision_inconclusive'])
        self.assertEqual(pair['gate'], 'mandatory_overhead_investigation')

    def test_request_identity_and_order(self):
        self.assertEqual(len(common.PROMPT.encode()), 5023)
        self.assertEqual(hashlib.sha256(common.PROMPT.encode()).hexdigest(), common.PROMPT_SHA)
        self.assertEqual(hashlib.sha256(common.canonical(common.REQUEST)).hexdigest(), common.REQUEST_SHA)
        plans = common.order()
        self.assertEqual(len(plans), 40)
        self.assertEqual([''.join(p['config'] for p in plans[i:i+4]) for i in range(0,40,4)],
                         ['ABCD','BCDA','CDAB','DABC','ABCD','BCDA','CDAB','DABC','ABCD','BCDA'])
        for config in 'ABCD':
            self.assertEqual(sum(p['config'] == config for p in plans), 10)

    def test_affinity_and_d_bundle_identity(self):
        self.assertEqual(common.parse_cpus('0-2,4,6,8,10-11'), {0,1,2,4,6,8,10,11})
        self.assertEqual(len(common.SERVER_CPUS), common.THREADS['compute'])
        self.assertFalse(common.SERVER_CPUS & common.HOUSE_CPUS)
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp)
            c, c_bundle = step10.server_argv(run, 'C')
            d, d_bundle = step10.server_argv(run, 'D')
            self.assertEqual(c, d)
            self.assertEqual(c_bundle, d_bundle)
            self.assertEqual(c[c.index('--threads')+1], str(common.THREADS['compute']))
            self.assertEqual(c[c.index('--threads-batch')+1], str(common.THREADS['batch']))
            a, _ = step10.server_argv(run, 'A')
            self.assertNotIn('--server-compute-profile-mode', a)

    def test_sanitized_environment(self):
        with patch.dict(os.environ, {'OMP_NUM_THREADS': '99', 'GOMP_CPU_AFFINITY': '1', 'LD_PRELOAD': 'bad', 'CMAKE_TOOLCHAIN_FILE': 'bad', 'CC': 'bad'}):
            env = common.bundle_env(Path('/tmp/fixture'))
            self.assertEqual(env['OMP_NUM_THREADS'], str(common.THREADS['compute']))
            self.assertEqual(env['LD_LIBRARY_PATH'], '/tmp/fixture/bin')
            for key in ('LD_PRELOAD', 'GOMP_CPU_AFFINITY', 'CMAKE_TOOLCHAIN_FILE', 'CC'):
                self.assertNotIn(key, env)

    def test_bundle_extraction_precedes_owned_build_removal(self):
        for config in 'ABC':
            with self.subTest(config=config), tempfile.TemporaryDirectory() as temp:
                run = Path(temp)
                events = []
                revision = common.REVISIONS[config]
                def fake_command(argv, **_kwargs):
                    if argv[:2] == ['git', 'rev-parse']:
                        return revision[:9] if '--short' in argv else revision
                    if argv[0] == 'nm':
                        return '00000001 T llama_scx_phase_v1'
                    return 'synthetic ELF identity'
                def fake_audit(_run, argv, **_kwargs):
                    events.append([str(a) for a in argv])
                    if argv[0] == 'cmake':
                        self.assertFalse(_kwargs['capture'])
                        self.assertIn('log', _kwargs)
                        if '--build' in argv:
                            self.assertEqual(argv[argv.index('--parallel')+1], '2')
                    if argv[:3] == ['git','worktree','add']:
                        source = Path(argv[4])
                        (source / 'common').mkdir(parents=True)
                    elif argv[:3] == ['git','worktree','remove']:
                        shutil.rmtree(argv[4])
                    elif argv[0] == 'cmake' and '-S' in argv:
                        build = Path(argv[argv.index('-B')+1])
                        (build / 'bin').mkdir(parents=True)
                        (build / 'common').mkdir()
                        (build / 'common/build-info.cpp').write_text(revision[:9])
                        cache = '\n'.join(a[2:].split('=')[0]+':STRING='+a.split('=',1)[1] for a in argv if a.startswith('-D'))
                        (build / 'CMakeCache.txt').write_text(cache+'\nCMAKE_CXX_FLAGS_RELEASE:STRING=-O3 -DNDEBUG\n')
                        (build / 'compile_commands.json').write_text('["-march=native -O3 -DNDEBUG"]')
                        for name in ('llama-server','libllama-server-impl.so'):
                            (build / 'bin' / name).write_bytes(b'synthetic runtime bytes')
                        (build / 'bin/libllama.so.0.0.1').write_bytes(b'synthetic versioned library')
                        (build / 'bin/libllama.so.0').symlink_to('libllama.so.0.0.1')
                        (build / 'bin/libllama.so').symlink_to('libllama.so.0')
                    elif '--version' in argv:
                        self.assertTrue(Path(argv[-2]).exists())
                        self.assertEqual(argv[:3], ['/usr/bin/taskset', '-c', ','.join(map(str, sorted(common.SERVER_CPUS)))])
                        self.assertTrue((run / '.prepare' / config / 'build').exists())
                        return revision[:9]
                    return ''
                def fake_dependencies(server, _env):
                    return 'synthetic ldd', [Path(server).parent / 'libllama-server-impl.so', Path(server).parent / 'libllama.so.0.0.1']
                with patch.object(step10,'audit_command',side_effect=fake_audit), patch.object(step10,'command',side_effect=fake_command), patch.object(step10,'dependencies',side_effect=fake_dependencies):
                    record = step10.build_bundle(run, config)
                self.assertEqual(record['revision'], revision)
                self.assertEqual(len(record['files']), 5)
                self.assertEqual(record['symlinks']['bin/libllama.so.0'], 'libllama.so.0.0.1')
                self.assertEqual((run / 'artifacts' / config / 'bin/libllama.so').read_bytes(), b'synthetic versioned library')
                self.assertFalse((run / '.prepare' / config).exists())
                version_index = next(i for i, e in enumerate(events) if '--version' in e)
                removal_index = next(i for i, e in enumerate(events) if e[:3] == ['git','worktree','remove'])
                self.assertLess(version_index, removal_index)

    def test_pointer_and_state_preserve_evidence(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(common, 'RESULTS', Path(temp)):
            root = Path(temp)
            run = root / '20261006T010203Z'
            run.mkdir()
            (root / '.active-run').write_text(run.name)
            self.assertEqual(common.active_run(), run)
            common.write_json(run / 'manifest.json', dict(status='PREPARED'))
            step10.change_status(run, 'FAILED', error='synthetic')
            self.assertEqual(common.read_json(run / 'manifest.json')['error'], 'synthetic')
            (run / 'evidence.json').write_text('retained')
            with common.locked(run):
                self.assertTrue((run / 'evidence.json').exists())
            (root / '.active-run').write_text('../../escape')
            with self.assertRaises(RuntimeError):
                common.active_run()

    def test_root_helper_whitelist(self):
        for op in root_helper.OPS:
            message = dict(op=op, token='secret')
            if op in {'START','STOP'}:
                message['visit'] = 4
            self.assertEqual(root_helper.validate_message(message, 'secret'), op)
        bad = [dict(op='EXEC', token='secret', command='id'), dict(op='HELLO', token='wrong'),
               dict(op='START', token='secret', visit=4, server_exe='/bin/sh'),
               dict(op='STOP', token='secret', visit=4, signal=9),
               dict(op='START', token='secret', visit=True), dict(op='START', token='secret', visit=41)]
        for message in bad:
            with self.assertRaises(RuntimeError):
                root_helper.validate_message(message, 'secret')
        helper = root_helper.Helper.__new__(root_helper.Helper)
        helper.child, helper.last, helper.manifest = None, None, dict(order=common.order())
        with patch.object(root_helper, 'state', return_value='disabled'):
            with self.assertRaisesRegex(RuntimeError, 'Only a frozen D visit'):
                helper.start(1)

    def test_bpf_classifier_ignores_unrelated_links(self):
        unrelated = dict(prog=[dict(id=1,name='system',type='kprobe')], map=[dict(id=2,name='system',type='hash')],
                         link=[dict(id=3,type='perf_event',prog_id=1), dict(id=4,type='struct_ops',map_id=2)])
        self.assertEqual(common.project_objects(unrelated), [])
        related = dict(prog=[dict(id=8,name='llama_phase',type='kprobe')], map=[dict(id=9,name='llama_sc.data',type='array')],
                       link=[dict(id=10,type='perf_event',prog_id=8)])
        self.assertEqual({p['id'] for p in common.project_objects(related)}, {8,9,10})

    def test_helper_prefers_natural_loader_exit(self):
        helper = root_helper.Helper.__new__(root_helper.Helper)
        helper.child = dict(visit=4, pidfd=123, identity={}, administrative_stop=False)
        helper.last = dict(visit=4, clean=True)
        with patch.object(root_helper.select, 'select', return_value=([123],[],[])), patch.object(helper, 'reap'), patch.object(root_helper, 'signal_exact') as send:
            result = helper.stop(4)
            send.assert_not_called()
            self.assertTrue(result['clean'])

    def test_snapshot_saved_before_teardown_assertion(self):
        baseline = dict(prog=[],link=[],map=[])
        persistent = dict(prog=[dict(id=8,name='llama_phase',type='kprobe')],link=[],map=[],sched_ext='disabled')
        with tempfile.TemporaryDirectory() as temp, patch.object(common, 'reduced_bpf', return_value=persistent), patch.object(common.time, 'sleep'), patch.object(common, 'state', return_value='disabled'):
            run = Path(temp)
            with self.assertRaisesRegex(RuntimeError, 'did not converge'):
                common.bpf_timeline(run, 'fixture', baseline, 0)
            self.assertEqual(len(list(run.glob('fixture-bpf-T*.json'))), 7)
            self.assertEqual(common.read_json(run / 'fixture-bpf-T0.json')['prog'][0]['id'], 8)

    def test_identity_safe_signal_and_reap(self):
        process = subprocess.Popen(['/usr/bin/sleep', '30'])
        try:
            saved = common.identity(process.pid)
            altered = saved | dict(starttime='wrong')
            with self.assertRaises(RuntimeError):
                common.signal_exact(altered, signal.SIGTERM)
            self.assertIsNone(process.poll())
            result = step10.stop_process(process, saved)
            self.assertEqual(result, -signal.SIGTERM)
            common.wait_gone(saved)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()

    def test_request_validator(self):
        value = response()
        self.assertEqual(common.validate_response(value, 200), 900)
        for field, bad in (('cache_n', 1), ('predicted_n', 127), ('prompt_per_second', float('nan'))):
            altered = response()
            altered['timings'][field] = bad
            with self.assertRaises(RuntimeError):
                common.validate_response(altered, 200)
        with self.assertRaises(RuntimeError):
            common.validate_response(value, 200, 901)

    def test_frozen_statistics_and_reject_incomplete_blocks(self):
        rows = [p | dict(prefill_tps=100, decode_tps=20, request_wall_ms=1000) for p in common.order()]
        summary = analysis.summarize(rows)
        for name, pair in summary['pairs'].items():
            self.assertEqual(pair['gate'], 'reference_only' if name == 'A->B' else 'acceptable')
            for metric in pair['metrics'].values():
                self.assertEqual(metric['bootstrap_95_pct'], [0,0])
        self.assertEqual(analysis.percentile([1,2,3,4], 0.25), 1.75)
        self.assertAlmostEqual(analysis.slowdown(100, 99, 'prefill_tps'), 100/99*100-100)
        with self.assertRaises(RuntimeError):
            analysis.summarize(rows[:-1])

    def test_synthetic_stored_campaign_parser(self):
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp)
            (run / 'raw').mkdir()
            common.write_json(run / 'manifest.json', dict(order=common.order(), prompt_n=900))
            common.write_json(run / 'visit-order.json', common.order())
            artifact = dict(files={'bin/llama-server':'synthetic'}, revision='synthetic')
            common.write_json(run / 'artifacts.json', {c: artifact for c in 'ABC'})
            snapshot = dict(kernel='fixture',boot_id='fixture',topology={},loadavg=[0,0,0],temperature_sensor='unavailable',temperature_c=None,
                            frequency=dict(available=False, policies={}), turbo=dict(available=False, interfaces={}), power_supply=dict(available=False, entries={}))
            common.write_json(run / 'machine.json', dict(before=snapshot))
            ready = dict(first=snapshot, second=snapshot, third=snapshot, busy_pct=0, second_busy_pct=0, ready=True)
            for block in range(1,11):
                common.write_json(run / f'block-{block:02d}-idle.json', [ready])
            for plan in common.order():
                path = run / 'raw' / f"{plan['visit']:02d}-{plan['config']}"
                path.mkdir()
                common.write_json(path / 'readiness.json', [ready])
                common.write_json(path / 'visit.json', plan | dict(status='VALID',artifact_files=artifact['files'],request_sha256=common.REQUEST_SHA))
                common.write_json(path / 'command.json', dict(revision='synthetic',affinity=sorted(common.SERVER_CPUS),compute_threads=common.THREADS['compute'],batch_threads=common.THREADS['batch'],http_threads=2))
                common.write_json(path / 'cleanup.json', dict(status='PASS',server_launcher_exit=0,sched_ext='disabled',port_free=True,
                                                             root=dict(clean=True,loader_exit=0,loader_sigterm_requested=False,timeline=[dict(project_objects=[])])))
                for role in ('warmup-1','warmup-2','measured'):
                    common.write_json(path / f'{role}-response.json', response())
                    common.write_json(path / f'{role}-client.json', dict(role=role,http_status=200,request_sha256=common.REQUEST_SHA,
                                                                       response_sha256=common.sha(path / f'{role}-response.json'),request_wall_ms=1000))
                for name in ('before','pre-measured','after'):
                    common.write_json(path / f'policies-{name}.json', dict(tids=[dict(uid=common.UID,policy=7 if plan['config']=='D' else 0,affinity=sorted(common.SERVER_CPUS))],
                                                                        runner=dict(policy=0,affinity=sorted(common.HOUSE_CPUS)),launcher=dict(policy=0,uid=common.UID,affinity=sorted(common.HOUSE_CPUS)),loader=dict(policy=0,uid=0,affinity=sorted(common.HOUSE_CPUS))))
                for name in ('before','after'):
                    common.write_json(path / f'system-{name}.json', snapshot)
            rows = step10.collect_rows(run)
            self.assertEqual(len(rows), 40)
            analysis.export(run, rows, analysis.summarize(rows))
            self.assertTrue((run / 'final-report.md').exists())
            readiness = run / 'raw/01-A/readiness.json'
            common.write_json(readiness, [ready | dict(busy_pct=20)])
            with self.assertRaisesRegex(RuntimeError, 'CPU busy'):
                step10.collect_rows(run)
            common.write_json(readiness, [ready])
            damaged = run / 'raw/04-D/visit.json'
            common.write_json(damaged, common.read_json(damaged) | dict(status='INVALID'))
            with self.assertRaises(RuntimeError):
                step10.collect_rows(run)


if __name__ == '__main__':
    unittest.main(verbosity=2)
