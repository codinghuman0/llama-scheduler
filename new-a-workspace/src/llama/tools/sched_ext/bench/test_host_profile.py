# SPDX-License-Identifier: GPL-2.0
"""Synthetic capability and frozen identity regressions; no scheduler activation."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import common
import host_profile
import machine
import step10


class HostProfileTests(unittest.TestCase):
    def test_allocation_preserves_detector_order_and_core_classes(self):
        for selected in ([3, 9, 17, 21], [1, 4, 7, 12, 19, 25]):
            result = host_profile.allocation(dict(physical_core_representatives=selected))
            self.assertEqual(result['server_cpus'], selected[:-1])
            self.assertEqual(result['housekeeping_cpus'], selected[-1:])
            self.assertEqual(result['compute_threads'], len(selected) - 1)
            self.assertEqual(result['batch_threads'], len(selected) - 1)
            self.assertEqual(result['http_threads'], 2)
        self.assertEqual(host_profile.allocation(dict(physical_core_representatives=[7]))['status'], 'BLOCKED')

    def test_missing_optional_interfaces_and_present_state_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            kwargs = dict(cpu=root / 'cpu', hwmon_root=root / 'hwmon', power_root=root / 'power')
            empty = host_profile.capabilities(**kwargs)
            self.assertFalse(empty['frequency']['available'])
            self.assertFalse(empty['turbo']['available'])
            self.assertFalse(empty['power_supply']['available'])
            self.assertEqual(empty['temperature_sensor'], 'unavailable')
            self.assertIsNone(empty['temperature_c'])
            policy = root / 'cpu/cpufreq/policy7'
            policy.mkdir(parents=True)
            for name, value in dict(scaling_driver='fixture-driver', scaling_governor='fixture-governor', scaling_min_freq='100', scaling_max_freq='900', scaling_cur_freq='500').items():
                (policy / name).write_text(value)
            ac = root / 'power/adapter'
            ac.mkdir(parents=True)
            (ac / 'type').write_text('Mains')
            (ac / 'online').write_text('1')
            initial = host_profile.capabilities(**kwargs)
            (policy / 'scaling_cur_freq').write_text('700')
            self.assertEqual(host_profile.execution_state(initial), host_profile.execution_state(host_profile.capabilities(**kwargs)))
            (policy / 'scaling_governor').write_text('changed')
            self.assertNotEqual(host_profile.execution_state(initial), host_profile.execution_state(host_profile.capabilities(**kwargs)))
            (policy / 'scaling_governor').write_text('fixture-governor')
            (ac / 'online').write_text('0')
            self.assertNotEqual(host_profile.execution_state(initial), host_profile.execution_state(host_profile.capabilities(**kwargs)))

    def test_power_invariants_ignore_battery_status_and_preserve_supply_state(self):
        value = dict(frequency=dict(available=False, policies={}), turbo=dict(available=False, interfaces={}),
                     temperature_sensor='unavailable', power_supply=dict(available=True, entries={
                         'adapter': dict(type='Mains', online='1', present='1'),
                         'BAT0': dict(type='Battery', present='1', status='Charging')}))
        initial = host_profile.execution_state(value)
        full = copy.deepcopy(value)
        full['power_supply']['entries']['BAT0']['status'] = 'Full'
        self.assertEqual(host_profile.execution_state(full), initial)
        for name, field, changed_value in (('adapter', 'online', '0'), ('adapter', 'type', 'USB'),
                                           ('adapter', 'present', '0'), ('BAT0', 'type', 'UPS'), ('BAT0', 'present', '0')):
            with self.subTest(supply=name, field=field):
                changed = copy.deepcopy(value)
                changed['power_supply']['entries'][name][field] = changed_value
                self.assertNotEqual(host_profile.execution_state(changed), initial)
        renamed = copy.deepcopy(value)
        entries = renamed['power_supply']['entries']
        entries['other_adapter'] = entries.pop('adapter')
        self.assertNotEqual(host_profile.execution_state(renamed), initial)
        unavailable = copy.deepcopy(value)
        unavailable['power_supply']['available'] = False
        self.assertNotEqual(host_profile.execution_state(unavailable), initial)
        limited = copy.deepcopy(value)
        limited['power_supply']['entries'] = {'adapter': dict(online='1')}
        self.assertEqual(host_profile.execution_state(limited)['power_supply'],
                         dict(available=True, entries={'adapter': dict(online='1')}))
        limited['power_supply']['entries']['adapter']['online'] = '0'
        self.assertNotEqual(host_profile.execution_state(limited)['power_supply'],
                            dict(available=True, entries={'adapter': dict(online='1')}))
        self.assertEqual(value['power_supply']['entries']['BAT0']['status'], 'Charging')

    def test_sensor_discovery_has_no_hwmon_index_or_vendor_requirement(self):
        for name, label in (('k10temp', 'Tctl'), ('coretemp', 'Package id 2')):
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                hwmon = root / 'hwmon/hwmon57'
                hwmon.mkdir(parents=True)
                (hwmon / 'name').write_text(name)
                (hwmon / 'temp8_label').write_text(label)
                (hwmon / 'temp8_input').write_text('42000')
                result = host_profile.capabilities(cpu=root / 'cpu', hwmon_root=root / 'hwmon', power_root=root / 'power')
                self.assertEqual(result['temperature_c'], 42)
                self.assertEqual(result['temperature_sensor']['label'], label)

    def test_bounded_readiness_with_and_without_temperature(self):
        absent = dict(temperature_sensor='unavailable', temperature_c=None, loadavg=[0, 0, 0])
        self.assertTrue(machine.thermal_ready([absent] * 3))
        self.assertFalse(machine.thermal_ready([absent | dict(loadavg=[2, 0, 0])] * 3))
        present = absent | dict(temperature_sensor=dict(name='fixture'), temperature_c=40)
        self.assertTrue(machine.thermal_ready([present, present | dict(temperature_c=42), present]))
        self.assertFalse(machine.thermal_ready([present, present | dict(temperature_c=43), present]))
        self.assertFalse(machine.thermal_ready([present | dict(temperature_c=56)] * 3))

    def test_scheduler_path_and_artifact_tampering(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(host_profile, 'SCHED', Path(temp)):
            build = Path(temp)
            (build / 'bin').mkdir()
            (build / 'llama_scx.bpf.o').write_bytes(b'bpf fixture')
            (build / 'bin/llama_scx_child').write_bytes(b'child fixture')
            loader = build / 'bin/llama_scx'
            loader.write_bytes(str(build / 'llama_scx.bpf.o').encode() + b'\0')
            frozen = host_profile.artifact_identity()
            (build / 'llama_scx.bpf.o').write_bytes(b'changed')
            self.assertNotEqual(host_profile.artifact_identity(), frozen)
            loader.write_bytes(b'/other/repository/llama_scx.bpf.o\0')
            with self.assertRaisesRegex(RuntimeError, 'embedded BPF path'):
                host_profile.artifact_identity()

    def test_campaign_profile_bytes_are_frozen(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            profile = root / 'profile.json'
            profile.write_text('{"fixture": true}\n')
            (root / 'host-profile.json').write_bytes(profile.read_bytes())
            manifest = dict(host_profile_sha256=common.sha(profile))
            with patch.object(step10, 'PROFILE_PATH', profile), patch.dict(common.HOST, {'fixture': True}, clear=True), \
                 patch.object(host_profile, 'validate_current'), patch.object(step10, 'scheduler_check'):
                step10.verify_profile(root, manifest)
                profile.write_text('{"fixture": true} \n')
                with self.assertRaisesRegex(RuntimeError, 'Frozen host profile changed'):
                    step10.verify_profile(root, manifest)

    def test_guard_rejects_tag_or_non_portability_change(self):
        def command(argv):
            if argv[:2] == ['git', 'rev-parse']:
                if argv[-1] == '--show-toplevel':
                    return str(common.REPO)
                if argv[-1] == 'HEAD':
                    return common.ACCEPTED_BASE
                tag = argv[-1].removeprefix('refs/tags/').removesuffix('^{commit}')
                return common.REQUIRED_TAGS[tag]
            if argv[:2] == ['git', 'branch']:
                return 'lightweight-base'
            if argv == ['git', 'diff', '--name-only', common.ACCEPTED_BASE]:
                return 'tools/sched_ext/llama_scx.bpf.c'
            return ''
        with patch.object(common, 'command', side_effect=command):
            with self.assertRaisesRegex(RuntimeError, 'outside the explicit portability scope'):
                common.repo_check()
        def moved(argv):
            if argv[-1] == 'refs/tags/neutral-sched-ext-base-v1^{commit}':
                return 'moved'
            return command(argv)
        with patch.object(common, 'command', side_effect=moved):
            with self.assertRaisesRegex(RuntimeError, 'Tag mismatch'):
                common.repo_check()


if __name__ == '__main__':
    unittest.main(verbosity=2)
