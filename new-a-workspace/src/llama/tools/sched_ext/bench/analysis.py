# SPDX-License-Identifier: GPL-2.0
"""Offline, frozen descriptive statistics and paired-block bootstrap."""
import csv
import math
import random
import statistics

from common import require, write_json

METRICS = ('prefill_tps', 'decode_tps', 'request_wall_ms')
PAIRS = (('A', 'B'), ('B', 'C'), ('C', 'D'))


def percentile(values, fraction):
    values = sorted(values)
    position = (len(values) - 1) * fraction
    low = int(position)
    high = min(low + 1, len(values) - 1)
    return values[low] + (values[high] - values[low]) * (position - low)


def slowdown(reference, candidate, metric):
    return 100 * ((candidate / reference if metric == 'request_wall_ms' else reference / candidate) - 1)


def describe(values):
    median = statistics.median(values)
    q1, q3 = percentile(values, 0.25), percentile(values, 0.75)
    return dict(n=len(values), median=median, minimum=min(values), maximum=max(values),
                q1=q1, q3=q3, iqr=q3-q1, mad=statistics.median(abs(v-median) for v in values))


def summarize(rows):
    require(len(rows) == 40 and len({(r['block'], r['config']) for r in rows}) == 40, 'Expected 40 distinct block/config samples')
    table = {(r['block'], r['config']): r for r in rows}
    require(set(table) == {(block, cfg) for block in range(1, 11) for cfg in 'ABCD'}, 'Incomplete blocks')
    require(all(isinstance(r[m], (int, float)) and math.isfinite(r[m]) and r[m] > 0 for r in rows for m in METRICS), 'Nonfinite/nonpositive metric')
    configs = {cfg: {metric: describe([table[block, cfg][metric] for block in range(1, 11)]) for metric in METRICS} for cfg in 'ABCD'}
    rng = random.Random(20261006)
    draws = [[rng.randrange(1, 11) for _ in range(10)] for _ in range(10000)]
    pairs = {}
    for reference, candidate in PAIRS:
        metrics = {}
        for metric in METRICS:
            ref, cand = configs[reference][metric]['median'], configs[candidate][metric]['median']
            boot = [slowdown(statistics.median(table[b, reference][metric] for b in draw),
                             statistics.median(table[b, candidate][metric] for b in draw), metric) for draw in draws]
            interval = [percentile(boot, 0.025), percentile(boot, 0.975)]
            metrics[metric] = dict(raw_delta_pct=100*(cand-ref)/ref, slowdown_pct=slowdown(ref, cand, metric),
                                   bootstrap_95_pct=interval, precision_inconclusive=interval[0] <= 0.5 and interval[1] > 1,
                                   paired_block_slowdowns=[slowdown(table[b, reference][metric], table[b, candidate][metric], metric) for b in range(1, 11)])
        worst = max(m['slowdown_pct'] for m in metrics.values())
        gate = 'acceptable' if worst <= 0.5 else 'repeat_variance_investigation' if worst <= 1 else 'mandatory_overhead_investigation'
        if worst <= 1 and any(m['precision_inconclusive'] for m in metrics.values()):
            gate = 'precision_inconclusive'
        if reference == 'A':
            gate = 'reference_only'
        pairs[reference + '->' + candidate] = dict(metrics=metrics, worst_median_slowdown_pct=worst, gate=gate)
    return dict(configurations=configs, pairs=pairs, bootstrap=dict(seed=20261006, draws=10000, method='whole-block paired percentile', rng='Python random.Random; randrange(1,11)'),
                interpretation={'A->B': 'fork/base implementation delta', 'B->C': 'phase-hint transport delta', 'C->D': 'neutral sched_ext-base delta; includes weighted-vtime semantics'})


def csv_file(path, rows):
    with open(path, 'w', newline='') as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def export(run, rows, summary):
    csv_file(run / 'raw-runs.csv', rows)
    csv_file(run / 'summary.csv', [dict(config=cfg, metric=metric, **data) for cfg, metrics in summary['configurations'].items() for metric, data in metrics.items()])
    write_json(run / 'summary.json', summary)
    lines = ['# Step 10 campaign report', '', 'Protocol validation: PASS. All 40 samples are retained. Warm-ups are excluded.', '',
             '| Configuration | Metric | Median | Min | Max | IQR | MAD |', '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for cfg, metrics in summary['configurations'].items():
        for metric, data in metrics.items():
            lines.append(f"| {cfg} | {metric} | {data['median']:.6f} | {data['minimum']:.6f} | {data['maximum']:.6f} | {data['iqr']:.6f} | {data['mad']:.6f} |")
    lines += ['', '| Pair / metric | Raw delta % | Slowdown % | Bootstrap 95% interval % | Gate |', '| --- | ---: | ---: | --- | --- |']
    for pair, data in summary['pairs'].items():
        for metric, value in data['metrics'].items():
            lines.append(f"| {pair} / {metric} | {value['raw_delta_pct']:.6f} | {value['slowdown_pct']:.6f} | {value['bootstrap_95_pct']} | {data['gate']} |")
    lines += ['', 'C->D is the neutral sched_ext-base delta, including weighted-vtime scheduling semantics. It is not pure framework overhead.',
              'Positive slowdown always means slower. Positive raw throughput delta means faster; positive raw duration delta means slower.',
              'Decision gates apply separately to B->C and C->D; improvements cannot offset regressions in another metric.',
              'No samples or outliers were discarded. See summary.json for paired-block deltas, variability and bootstrap parameters.', '']
    (run / 'final-report.md').write_text('\n'.join(lines))
