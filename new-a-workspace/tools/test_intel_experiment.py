#!/usr/bin/env python3
"""Admission/regression tests; no model, root, network, or inference needed."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest

import intel_experiment as runner
from intel_policy_evidence import validate as validate_policy


def hybrid():
    rows = []
    for core in range(4):
        for cpu in (core*2, core*2+1):
            rows.append(dict(cpu=cpu, package=0, core=core, siblings=[core*2, core*2+1]))
    rows += [dict(cpu=8+i, package=0, core=4+i, siblings=[8+i]) for i in range(8)]
    return rows


class IntelRunnerTests(unittest.TestCase):
    def test_hybrid_uses_physical_cores_and_spare_controller(self):
        cpus, controller = runner.choose_cpus(hybrid())
        self.assertEqual(cpus, [0, 2, 4, 6, 8, 9])
        self.assertEqual(controller, 10)

    def test_noncontiguous_cpuset_preserves_allowed_siblings(self):
        rows = [r for r in hybrid() if r['cpu'] in {1, 3, 5, 7, 10, 12, 14}]
        cpus, controller = runner.choose_cpus(rows)
        self.assertEqual(cpus, [1, 3, 5, 7, 10, 12])
        self.assertEqual(controller, 14)

    def test_reject_smt_alias_or_outside_cpuset_or_too_few(self):
        for cpus in ([0, 1, 4, 6, 8, 9], [0, 2, 4, 6, 8, 99], [0, 2, 4, 6, 8]):
            with self.assertRaises(RuntimeError):
                runner.choose_cpus(hybrid(), cpus)
        with self.assertRaises(RuntimeError):
            runner.choose_cpus(hybrid()[:8])
        with self.assertRaises(RuntimeError):
            runner.cpu_list('0-2,2')

    def test_real_fixture_payload_is_atomic_distinct_and_uncached(self):
        fixture = runner.read(runner.FIXTURES)[0]
        before = copy.deepcopy(fixture)
        payload = runner.payload_for(fixture, 16)
        self.assertEqual(fixture, before)
        self.assertEqual(len({tuple(v) for v in payload['prompt']}), 8)
        self.assertEqual(payload['n_predict'], 16)
        self.assertIs(payload['cache_prompt'], False)
        self.assertEqual(payload['n_cache_reuse'], 0)
        self.assertNotIn('id_slot', payload)

    def test_stale_cache_or_missing_outputs_are_not_accepted(self):
        fixture = runner.read(runner.FIXTURES)[2]
        response = dict(index=0, tokens=[1]*16, tokens_predicted=16,
                        tokens_evaluated=len(fixture['requests'][0]['prompt']),
                        timings=dict(prompt_n=len(fixture['requests'][0]['prompt']), cache_n=1),
                        generation_settings=dict(temperature=0, seed=424242))
        with self.assertRaises(RuntimeError):
            runner.validate_body(response, fixture, 16)
        response['timings']['cache_n'] = 0
        self.assertEqual(len(runner.validate_body(response, fixture, 16)), 1)
        with self.assertRaises(RuntimeError):
            runner.validate_body([response, response], fixture, 16)

    def test_owned_process_cleanup(self):
        process = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(30)'], start_new_session=True)
        try:
            runner.stop_owned(process)
            self.assertIsNotNone(process.poll())
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()

    def test_cpu25_pair_with_unequal_delivered_load_is_invalid(self):
        rows = [dict(condition='cpu25', block=1, arm=arm, policy_exercised=False,
                     measured_multi_decode_5_6=[0, 0], metrics=dict(throughput=100, load_mean_cpu_cores=load))
                for arm, load in zip(runner.ARMS, [.22, .25, .28])]
        with self.assertRaises(RuntimeError):
            runner.analyze(rows, ['cpu25'])

    def test_paired_analysis_uses_blocks_and_preserves_pilot_scope(self):
        rows = [dict(condition='ambient', block=block, arm=arm, policy_exercised=True,
                     measured_multi_decode_5_6=[15, 0], metrics=dict(throughput=rate*block))
                for block in (1, 2) for arm, rate in zip(runner.ARMS, (100, 110, 121))]
        report = runner.analyze(rows, ['ambient'])
        self.assertEqual(report['status'], 'PILOT_ONLY_NOT_CONFIRMATION')
        contrast = report['comparisons']['ambient']['A_L/F6_L']
        self.assertEqual(contrast['blocks'], 2)
        self.assertAlmostEqual(contrast['mean_gain_pct'], 10)
        for endpoint in contrast['bootstrap_95_pct']:
            self.assertAlmostEqual(endpoint, 10)
        self.assertEqual(contrast['faster_pair_fraction'], 1)

    def test_pressure_validator_preserves_raw_evidence_checks(self):
        files = sorted((runner.ROOT/'experiments/a-component-scheduler-replication-v1').rglob('policy-recomputed.json'))
        policies = [runner.read(p) for p in files]
        policies = [v for v in policies if v.get('mode') == 'pressure' and v.get('epochs')]
        self.assertTrue(policies, 'Preserved raw policy evidence is required')
        value = {k: v for k, v in policies[0].items() if k not in ('status', 'limitation')}
        raw = 'NEWA_PREFILL_POLICY ' + json.dumps(value)
        self.assertEqual(validate_policy(raw, 'pressure', value['cpus'], value['ticks_per_second'])['mode'], 'pressure')
        with self.assertRaises(ValueError):
            validate_policy(raw, 'pressure', [0, 1, 2, 3, 4, 5], value['ticks_per_second'])
        value = copy.deepcopy(value)
        value['failures'] = 1
        with self.assertRaises(ValueError):
            validate_policy('NEWA_PREFILL_POLICY '+json.dumps(value), 'pressure', value['cpus'], value['ticks_per_second'])


if __name__ == '__main__':
    unittest.main()
