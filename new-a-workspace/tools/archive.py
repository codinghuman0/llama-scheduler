#!/usr/bin/env python3
"""Read verified historical files from the standalone solid archive."""
from pathlib import Path, PurePosixPath
import argparse, hashlib, json, tarfile
ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
sub = p.add_subparsers(dest='action', required=True)
a = sub.add_parser('list'); a.add_argument('prefix', nargs='?', default='')
a = sub.add_parser('get'); a.add_argument('path'); a.add_argument('output', type=Path)
a = sub.add_parser('extract'); a.add_argument('prefix'); a.add_argument('output', type=Path)
sub.add_parser('verify')
args = p.parse_args()
package = json.loads((ROOT/'config/package-manifest.json').read_text())
archive = ROOT/package['archive_path']
with tarfile.open(archive, 'r|xz') as tar:
    first = next(iter(tar))
    assert first.name == 'manifest.json'
    entries = json.load(tar.extractfile(first))['entries']
    needed = {}; omitted = []; count = 0
    def queue(key, output):
        entry = entries[key]
        if entry['type'] == 'hardlink':
            return queue(entry['target'], output)
        if entry['type'] != 'file':
            raise ValueError('Not a retained regular file: '+entry['type'])
        assert not output.exists() and not output.is_symlink()
        needed.setdefault(entry['sha256'], []).append((output, entry['mode']))
    if args.action == 'list':
        for key, value in entries.items():
            if key.startswith(args.prefix):
                print(value['type'], value.get('size', '-'), key)
    else:
        if args.action == 'get':
            queue(args.path, args.output)
        elif args.action == 'extract':
            assert args.prefix and not args.output.exists()
            prefix = args.prefix.rstrip('/')+'/'
            args.output.mkdir(parents=True)
            for key, value in entries.items():
                if not key.startswith(prefix): continue
                rel = PurePosixPath(key[len(prefix):])
                assert not rel.is_absolute() and '..' not in rel.parts
                if value['type'] in ['file', 'hardlink']:
                    queue(key, args.output/str(rel))
                else:
                    omitted.append({'path':str(rel), **value})
        expected = {v['sha256'] for v in entries.values() if v['type']=='file'}
        seen = set()
        # One sequential pass avoids repeated decompression and unsafe extractall.
        while True:
            info = tar.next()
            if info is None: break
            assert info.isfile() and info.name.startswith('blobs/')
            digest = info.name.split('/')[1]
            if args.action != 'verify' and digest not in needed: continue
            outputs = needed.pop(digest, [])
            handles = []
            try:
                for out, mode in outputs:
                    out.parent.mkdir(parents=True, exist_ok=True)
                    handles.append(out.open('xb'))
                h = hashlib.sha256()
                src = tar.extractfile(info)
                for block in iter(lambda:src.read(1024*1024), b''):
                    h.update(block)
                    for dst in handles: dst.write(block)
                assert h.hexdigest() == digest
            finally:
                for dst in handles: dst.close()
            for out, mode in outputs: out.chmod(mode & 0o777)
            seen.add(digest); count += len(outputs)
            if args.action != 'verify' and not needed: break
        assert not needed, 'Archive missing requested blobs'
        if args.action == 'verify':
            assert seen == expected
            print(json.dumps({'status':'PASS', 'unique_blobs':len(seen), 'entries':len(entries)}))
        elif args.action == 'extract':
            (args.output/'ARCHIVE_EXTRACTION.json').write_text(json.dumps({'files':count,'links_expanded_containers_and_removed_caches_not_materialized':omitted},indent=2)+'\n')
            print('Restored regular files:',count)
