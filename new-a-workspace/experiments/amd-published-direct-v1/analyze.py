#!/usr/bin/env python3
"""Recompute paired performance and token validity from the saved raw evidence."""

from collections import Counter
import itertools
from pathlib import Path
import random
from statistics import fmean

from study import CPUS, DATA, P, TOKENS, read, require, runner, schedule, sha, validate_body


CONTRASTS = (P['analysis']['primary_contrast'], *P['analysis']['secondary_contrasts'])


def read_arm(path, spec, fixture):
    launch = read(path / 'launch.json')
    require(launch['payload']['prompt'] == [request['prompt'] for request in fixture['requests']], 'Input arrays differ')
    cleanup = read(path / 'cleanup.json')
    require(cleanup['returncode'] == 0 and not cleanup['forced_leader_kill'], 'Cleanup failed')
    data = {}
    for stage in ('warmup', 'measured'):
        response = validate_body(read(path / f'{stage}-response.json'), fixture, TOKENS)
        window = read(path / f'{stage}-window.json')
        elapsed = (window['end_ns'] - window['start_ns']) / 1e9
        require(elapsed > 0, 'Nonpositive measurement window')
        before, after = window['server_before'], window['server_after']
        require(before['affinity'] == after['affinity'] == CPUS and before['policy'] == after['policy'] == 0 and
                before['starttime'] == after['starttime'], 'Unexpected CPU envelope or PID identity')
        count = sum(len(row['tokens']) for row in response)
        require(count == P['request_count'] * TOKENS, 'Incomplete generation count')
        metrics = {'clock_ns': [window['start_ns'], window['end_ns']], 'tokens_per_s': count / elapsed,
                   'server_cpu_s': (after['cpu_ticks'] - before['cpu_ticks']) / before['tick_hz'],
                   'sample_cpu_temperature_c': [window[key]['temperature_c'] for key in ('environment_before', 'environment_after')],
                   'outputs': [row['tokens'] for row in response]}
        if spec['condition'] == 'cpu25':
            a, b = window['load_before'], window['load_after']
            ranges = P['cpu25']
            require(a['affinity'] == b['affinity'] == [ranges['cpu']] and a['policy'] == b['policy'] == 0 and
                    a['starttime'] == b['starttime'], 'Wrong load envelope')
            load_rate = (b['cpu_ticks'] - a['cpu_ticks']) / a['tick_hz'] / elapsed
            if stage == 'measured':
                require(ranges['minimum'] <= load_rate <= ranges['maximum'], 'Incorrect external CPU demand')
            metrics['cpu25_cores'] = load_rate
        data[stage] = metrics
    return data


def collect(campaign, fixtures):
    rows = []
    for spec in schedule(campaign):
        folder = DATA / f'confirm-{campaign}' / f'{spec["condition"]}-{spec["block"]:02d}'
        result = read(folder / 'result.json')
        require(result['spec'] == spec, 'Observed block order differs')
        row = {'spec': spec, 'status': result['status'], 'recorded_arms': result['arms'], 'timings': {}, 'comparisons': {}}
        last_ns = None
        for arm in spec['order']:
            if result['arms'].get(arm) != 'ok':
                continue
            visit = read_arm(folder / arm, spec, fixtures[spec['cohort']])
            if last_ns is not None:
                require(last_ns < visit['warmup']['clock_ns'][0], 'Overlapping visits in a block')
            last_ns = visit['measured']['clock_ns'][1]
            row['timings'][arm] = visit
        for numerator, denominator in CONTRASTS:
            if not {numerator, denominator} <= row['timings'].keys():
                continue
            a, b = (row['timings'][arm] for arm in (numerator, denominator))
            diffs = {window: [i for i, (left, right) in enumerate(zip(a[window]['outputs'], b[window]['outputs'], strict=True))
                              if left != right] for window in ('warmup', 'measured')}
            gain = 100 * (a['measured']['tokens_per_s'] / b['measured']['tokens_per_s'] - 1)
            row['comparisons'][f'{numerator}/{denominator}'] = {'gain_pct': gain, 'valid': not any(diffs.values()),
                                                              'mismatched_requests': diffs}
        for visit in row['timings'].values():
            for stage in visit.values():
                del stage['outputs']
        rows.append(row)
    return rows


def interval(rows, contrast):
    groups = [[row['comparisons'][contrast]['gain_pct'] for row in rows if row['spec']['cohort'] == cohort]
              for cohort in P['new_cohorts']]
    groups = [group for group in groups if group]
    cfg = P['analysis']
    rng = random.Random(cfg['bootstrap_seed'])
    estimates = sorted(fmean(itertools.chain.from_iterable(rng.choices(group, k=len(group)) for group in groups))
                       for _ in range(cfg['bootstrap_resamples']))
    quantiles = []
    for fraction in (0.025, 0.975):
        offset = (len(estimates) - 1) * fraction
        index = int(offset)
        quantiles.append(estimates[index] + (estimates[index + 1] - estimates[index]) * (offset - index))
    return quantiles


def compare(rows, arms):
    contrast = '/'.join(arms)
    complete = [row for row in rows if contrast in row['comparisons']]
    valid = [row for row in complete if row['comparisons'][contrast]['valid']]
    report = {'contrast': contrast, 'scheduled': len(rows), 'complete_timings': len(complete), 'valid_pairs': len(valid),
              'gates_pass': False, 'status_counts': dict(Counter(row['status'] for row in rows))}
    for label, sample in (('all_timings', complete), ('eligible', valid)):
        if sample:
            gains = [row['comparisons'][contrast]['gain_pct'] for row in sample]
            report[label] = {'mean_gain_pct': fmean(gains), 'range_pct': [min(gains), max(gains)],
                             'faster_pairs': sum(gain > 0 for gain in gains),
                             'absolute_tps': {arm: fmean(row['timings'][arm]['measured']['tokens_per_s'] for row in sample)
                                              for arm in arms},
                             'server_cpu_s': {arm: fmean(row['timings'][arm]['measured']['server_cpu_s'] for row in sample)
                                              for arm in arms}}
    if valid:
        eligible = report['eligible']
        eligible['ci95_pct'] = interval(valid, contrast)
        gate = P['analysis']
        report['gates_pass'] = (len(valid) == gate['required_valid_pairs'] and
                                eligible['mean_gain_pct'] >= gate['minimum_mean_gain_pct'] and
                                eligible['ci95_pct'][0] > gate['minimum_ci_lower_pct_exclusive'] and
                                eligible['faster_pairs'] >= gate['minimum_fast_pairs'])
        report['strong_evidence'] = report['gates_pass'] and eligible['ci95_pct'][0] >= gate['minimum_mean_gain_pct']
    return report


def main():
    frozen = read(DATA / 'frozen.json')
    require(all(sha(Path(path)) == digest for path, digest in frozen['files'].items()), 'Frozen inputs or code differ')
    fixtures = read(DATA / 'fixtures.json')
    cells = []
    for campaign in (1, 2):
        rows = collect(campaign, fixtures)
        runner.write_json(DATA / f'confirm-{campaign}/audited-blocks.json', rows)
        for condition in ('ambient', 'cpu25'):
            cell = [row for row in rows if row['spec']['condition'] == condition]
            metrics = [compare(cell, contrast) for contrast in CONTRASTS]
            loads = [visit['measured']['cpu25_cores'] for row in cell for visit in row['timings'].values()
                     if 'cpu25_cores' in visit['measured']]
            cells.append({'campaign': campaign, 'condition': condition, 'comparisons': metrics,
                          'observed_cpu25_core_range': [min(loads), max(loads)] if loads else None})
    primary = [cell['comparisons'][0] for cell in cells]
    if all(cell['gates_pass'] for cell in primary):
        status = 'CONFIRMED_SYSTEM_GAIN'
    elif any(cell['gates_pass'] for cell in primary):
        status = 'INCONCLUSIVE_PARTIAL'
    elif all(cell['valid_pairs'] == 8 and cell['eligible']['ci95_pct'][1] < P['analysis']['minimum_mean_gain_pct']
             for cell in primary):
        status = 'BELOW_TARGET'
    else:
        status = 'INCONCLUSIVE'
    report = {'status': status, 'scope': 'published integration-v2 userspace runtime on AMD under SCHED_OTHER', 'cells': cells}
    runner.write_json(DATA / 'final-analysis.json', report)


if __name__ == '__main__':
    main()
