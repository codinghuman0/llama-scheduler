#!/usr/bin/env python3
"""Tokenize declared workloads on frozen B1, without completion or policy tuning."""
import argparse
import copy
import fcntl
import os
from pathlib import Path
import socket
from types import SimpleNamespace

import study
import sealing


def definitions(kind):
    if kind == 'confirmation':
        document = study.read(study.STUDY / 'heldout-prompts.json')
        return [dict(id='heldout-' + str(index + 1), items=items, concurrency=8,
                     input_token_cap=document['input_token_cap'], n_predict=document['n_predict'])
                for index, items in enumerate(document['cohorts'])]
    original = study.read(study.REPO / 'experiments/phase_generalization/workloads.json')
    return [
        dict(id='single-short', items=original['short'][:1], concurrency=1, input_token_cap=256, n_predict=128),
        dict(id='single-longer-input', items=original['long'][:1], concurrency=1, input_token_cap=512, n_predict=128),
        dict(id='batch8-shorter-output', items=original['short'][:8], concurrency=8, input_token_cap=256, n_predict=64),
    ]


def main(args):
    freeze = None
    if args.kind == 'confirmation':
        freeze = study.read(study.STUDY / 'selection-freeze.json')
        study.require(freeze['status'] == 'FROZEN_BEFORE_HELDOUT_COMPLETIONS', 'Candidate is not frozen')
        study.check_hashes(freeze['protected'])
        study.require(str(Path(__file__).resolve()) in freeze['protected'], 'Fixture preparer was not frozen')
    declaration_path = (study.STUDY / 'heldout-prompts.json' if args.kind == 'confirmation' else
                        study.REPO / 'experiments/phase_generalization/workloads.json')
    if freeze:
        study.require(freeze['heldout_declaration'] == dict(path=str(declaration_path), sha256=study.sha(declaration_path)),
                      'Frozen heldout declaration differs')
    items = definitions(args.kind)
    root, setup, _ = study.prepare(SimpleNamespace(name=args.name, arms=['B1'], conditions=['ambient'],
                                                   stage='smoke', reference=None))
    setup['protected'].update({str(path.resolve()): study.sha(path)
                              for path in [Path(__file__), Path(sealing.__file__), declaration_path]})
    if freeze:
        setup['protected'].update(freeze['protected'])
        setup['protected'][str(study.STUDY / 'selection-freeze.json')] = study.sha(study.STUDY / 'selection-freeze.json')
    study.save(root / 'setup.json', setup)
    case = setup['cases']['B1']
    command = list(case['server_argv'])
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    command[command.index('--port') + 1] = str(port)
    result = dict(status='RUNNING', kind=args.kind, fixtures=[], completion_requests=0,
                  declaration=dict(path=str(declaration_path), sha256=study.sha(declaration_path)),
                  preparation_source=dict(path=str(Path(__file__).resolve()), sha256=study.sha(__file__)),
                  freeze_sha256=study.sha(study.STUDY / 'selection-freeze.json') if freeze else None,
                  tokenizer_identity_sha256=study.sha(study.STUDY / 'identity/B1.json'),
                  tokenizer_artifacts=case['artifacts'],
                  purpose='Tokenization only; no heldout generation output or timing used to tune a policy')
    try:
        with study.m.Session(root / 'tokenizer', command, setup['cpus'], setup['housekeeping'],
                             policy='C', env=case['server_env']) as session:
            study.m.ready(session, port)
            pid = session.server['pid']
            mapped = {line.split()[-1] for line in Path(f'/proc/{pid}/maps').read_text().splitlines() if '/' in line}
            study.require(set(case['artifacts']).issubset(mapped), 'Tokenizer loaded different runtime libraries')
            study.save(root / 'tokenizer-runtime.json', dict(pid=pid, mapped=sorted(mapped),
                        loaded_sha256={p: study.sha(p) for p in mapped if Path(p).is_file()}))
            for definition in items:
                fixture = copy.deepcopy(definition)
                requests = []
                for index, item in enumerate(definition['items']):
                    tokenized, _, _ = study.m.http(port, '/tokenize', dict(content=item['prompt'], add_special=True))
                    tokens = tokenized['tokens'][:definition['input_token_cap']]
                    study.require(len(tokens) >= 40, 'Declared fixture unexpectedly short')
                    if definition['id'] == 'single-longer-input':
                        study.require(len(tokens) == 512, 'Longer-input regression did not reach declared length')
                    requests.append(dict(prompt=tokens, n_predict=definition['n_predict'], temperature=0,
                        seed=424242, stream=False, cache_prompt=False, ignore_eos=True,
                        id_slot=index, n_cache_reuse=0, stop=[], return_tokens=True))
                study.require(len({tuple(r['prompt']) for r in requests}) == len(requests), 'Requests are not distinct')
                fixture['requests'] = requests
                fixture['actual_input_lengths'] = [len(r['prompt']) for r in requests]
                result['fixtures'].append(fixture)
        study.require(study.read(root / 'tokenizer/cleanup.json')['status'] == 'PASS', 'Tokenizer cleanup failed')
        study.check_hashes(setup['protected'])
        result['status'] = 'TOKENIZED_NO_COMPLETIONS'
    except BaseException as error:
        result.update(status='FAILED', error=repr(error))
        raise
    finally:
        study.save(root / 'fixtures.json', result)
        manifest = sealing.seal(root)
        study.record(args.name, result['status'], dict(path=str(root), kind=args.kind, completion_requests=0,
                                                     raw_manifest_sha256=manifest))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kind', choices=['regression', 'confirmation'], required=True)
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    study.require(os.getuid() != 0, 'Use ordinary account')
    study.require(study.re.fullmatch('[a-zA-Z0-9_-]+', args.name), 'Invalid attempt name')
    with (study.WORKSPACE / 'new-a-runs/.measurement.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        main(args)
