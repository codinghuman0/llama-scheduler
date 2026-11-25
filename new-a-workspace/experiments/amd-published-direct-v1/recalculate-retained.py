#!/usr/bin/env python3
"""Verify the saved AMD throughput results using only this checkout."""

from pathlib import Path
import sys


WORKSPACE = Path(__file__).resolve().parents[2]
RELATIVE_HELPERS = Path('experiments/a-b0-direct-confirmation-v1/code')
HELPERS = WORKSPACE / RELATIVE_HELPERS
sys.path.append(str(HELPERS))

from analyze import CONTRASTS, collect, compare
from study import DATA, contention, read, require, sha


def main():
    require(Path(contention.__file__).resolve().parent == HELPERS, 'Expected the retained in-repository helper')
    old_helpers = WORKSPACE.parents[1] / 'new-a-workspace' / RELATIVE_HELPERS
    helper_aliases = {old_helpers / name: HELPERS / name for name in ('contention.py', 'load.py')}
    for filename, digest in read(DATA / 'frozen.json')['files'].items():
        original = Path(filename)
        path = helper_aliases.get(original, original)
        require(path.is_relative_to(WORKSPACE) and sha(path) == digest, f'Frozen file mismatch: {path}')

    fixtures = read(DATA / 'fixtures.json')
    results = read(DATA / 'final-analysis.json')
    for campaign in (1, 2):
        rows = collect(campaign, fixtures)
        for cell in (cell for cell in results['cells'] if cell['campaign'] == campaign):
            subset = [row for row in rows if row['spec']['condition'] == cell['condition']]
            recalculated = [compare(subset, contrast) for contrast in CONTRASTS]
            require(recalculated == cell['comparisons'], f'Unexpected result: {campaign} {cell["condition"]}')
            primary = recalculated[0]['eligible']['mean_gain_pct']
            print(f'{campaign} {cell["condition"]}: {primary:+.2f}% I/B0')
    print('PASS: all saved paired results reproduced from retained raw responses and clocks')


if __name__ == '__main__':
    main()
