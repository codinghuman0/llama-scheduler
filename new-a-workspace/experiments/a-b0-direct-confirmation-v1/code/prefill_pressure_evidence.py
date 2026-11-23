"""Recalculate Prefill CPU pressure and submitted profiles from bounded raw evidence."""
import json
import math

def require(value, message):
    if not value: raise ValueError(message)

def close(a, b):
    require(math.isfinite(a) and math.isclose(a, b, rel_tol=1e-11, abs_tol=1e-10), 'Derived pressure value differs')

def validate(log, mode):
    records = [json.loads(line.split('NEWA_PREFILL_POLICY ', 1)[1])
               for line in log.splitlines() if line.startswith('NEWA_PREFILL_POLICY ')]
    if mode == 'off':
        require(not records, 'Disabled pressure policy emitted evidence')
        return dict(status='DISABLED', mode=mode)
    require(len(records) == 1, 'Missing/duplicate pressure evidence')
    value = records[0]
    require(mode in ['pressure', 'fixed6', 'fixed5'] and value['mode'] == mode, 'Pressure mode differs')
    require(value['failures'] == value['read_errors'] == value['reports_dropped'] == 0, 'Pressure instrumentation failure')
    require(value['cpus'] == [0, 2, 4, 6, 8, 10] and value['ticks_per_second'] == 100, 'Frozen sensor topology/USER_HZ differs')
    require(value['threshold'] == .125 and value['accounting_margin_cores'] == .02, 'Pressure constants differ')
    require(0 < len(value['epochs']) <= 16, 'Missing epoch evidence')
    for epoch in value['epochs']:
        decisions = epoch['decisions_5_6']
        require(len(decisions) == 4 and all(len(row) == 2 for row in decisions), 'Decision schema differs')
        require(all(type(x) is int and x >= 0 for row in decisions for x in row), 'Invalid decision count')
        require(all(decisions[p][0] == 0 for p in [0, 1, 3]), 'Unsafe fallback profile')
        require(sum(map(sum, decisions)) == epoch['calls'], 'Decision call count differs')
        members = epoch['members']
        require(0 <= len(members) <= 8 and len({x['task'] for x in members}) == len(members) and
                len({x['slot'] for x in members}) == len(members), 'Epoch identity is not distinct')
        require(all(x['task'] >= 0 and x['slot'] >= 0 and x['first_position'] in [-1, 0] and
                    x['last_position'] >= x['first_position'] for x in members), 'Invalid epoch member metadata')
        sample = epoch['sample']
        choice = 6
        if sample['captured']:
            before, after = sample['before'], sample['after']
            require(sample['n_tokens'] >= 32, 'Sample outside eligible Prefill')
            for snap in [before, after]:
                require(snap['ok'] and 0 <= snap['wall_last'] - snap['wall_first'] <= 20000000 and
                        0 <= snap['cpu_first'] <= snap['cpu_last'], 'Invalid raw counter snapshot')
                require(len(snap['fields']) == 6 and all(len(row) == 3 for row in snap['fields']) and
                        all(type(x) is int and x >= 0 for row in snap['fields'] for x in row), 'Raw CPU field schema differs')
                require(sum(map(sum, snap['fields'])) == snap['task_ticks'], 'CPU fields do not sum to recorded total')
            require(all(b >= a for xs, ys in zip(before['fields'], after['fields']) for a, b in zip(xs, ys)), 'CPU counter reversed')
            require(before['wall_last'] <= sample['model_start'] <= sample['model_end'] <= after['wall_first'] and
                    before['cpu_last'] <= after['cpu_first'], 'Clock bracket order differs')
            wall = (after['wall_last'] - before['wall_first']) / 1e9
            task = (after['task_ticks'] - before['task_ticks']) / value['ticks_per_second']
            own = (after['cpu_last'] - before['cpu_first']) / 1e9
            rounding = 18 / value['ticks_per_second']
            require(wall > 0 and 0 <= own <= 6 * wall + rounding and 0 <= task <= 6 * wall + rounding,
                    'Implausible process/selected CPU accounting')
            skew = 6 * (before['wall_last'] - before['wall_first'] + after['wall_last'] - after['wall_first']) / 1e9
            require(task + rounding + skew + .02 * wall >= own, 'Implausibly negative CPU residual')
            usable = sample['model_end'] - sample['model_start'] >= 1000000000
            score = (task - own - rounding) / wall - .02
            for field, expected in [('wall_s', wall), ('task_cpu_s', task), ('own_cpu_upper_s', own),
                                    ('rounding_cpu_s', rounding), ('score', score)]:
                close(sample[field], expected)
            choice = 5 if usable and score > .125 else 6
            require(sample['counters_valid'] and sample['usable'] == usable and sample['shadow_choice'] == choice,
                    'Pressure decision differs from raw counters')
        else:
            require(not sample['counters_valid'] and not sample['usable'] and sample['shadow_choice'] == 6,
                    'Unsampled epoch contains a pressure decision')
        counts = epoch['eligible_by_size_5_6']
        require(len(counts) == 9 and all(len(row) == 2 for row in counts) and counts[0] == [0, 0] and
                all(type(x) is int and x >= 0 for row in counts for x in row), 'Eligible profile schema differs')
        require(sum(map(sum, counts)) == epoch['eligible_calls'] <= 256, 'Eligible call count differs')
        for size, row in enumerate(counts[1:], 1):
            expected = 5 if size == 1 else 6 if mode == 'fixed6' else 5 if mode == 'fixed5' else choice
            require(row[1 if expected == 5 else 0] == 0, 'Submitted profile differs from declared decision')
        require(all(sum(row[i] for row in counts) <= decisions[2][i] for i in range(2)), 'Eligible counts exceed Decode calls')
        if epoch['locked']:
            require(sample['captured'] and sample['usable'] and len(members) == 8 and
                    all(x['prefill_seen'] and x['first_position'] == 0 for x in members), 'Locked epoch lacks Prefill8 provenance')
            age = epoch['first_decode_ns'] - sample['after']['wall_last']
            require(0 <= age <= 10000000000 and age == epoch['sample_age_ns'], 'First Decode used stale pressure')
            require(0 < epoch['active_mask'] <= 255 and sum(counts[8]) > 0, 'Locked epoch lacks full8 first decision')
        else:
            require(epoch['eligible_calls'] == 0, 'Unlocked epoch made adaptive decisions')
        require(epoch['invalidated'] == (epoch['reason'] != 0), 'Invalidation evidence differs')
    return dict(status='RAW_DECISIONS_RECOMPUTED', **value,
        limitation='Operational accounting margin is not a statistical confidence bound. Submitted profiles are checked against actual OpenMP teams separately; pressure can change after Prefill.')
