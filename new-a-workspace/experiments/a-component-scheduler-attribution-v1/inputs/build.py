#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""Compile phase-aware idle handoff without loading BPF."""
import argparse
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import importlib.util
spec = importlib.util.spec_from_file_location('idle_handoff_derive', Path(__file__).with_name('derive.py'))
derive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(derive)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.append(str(HERE.parent/'scheduler_quantum'))
import quantum_build as shared
require, sha = shared.require, shared.sha
MODES = derive.MODES

def sections(path):
    result = shared.build_static.elf_sections(path)
    data = Path(path).read_bytes()
    header = struct.unpack_from('<16sHHIQQQIHHHHHH',data)
    entries = [struct.unpack_from('<IIQQQQIIQQ',data,header[6]+i*header[11]) for i in range(header[12])]
    strings = entries[header[13]]
    names = data[strings[4]:strings[4]+strings[5]]
    for entry in entries:
        name = names[entry[0]:].split(b'\0',1)[0].decode()
        result[name].update(type=entry[1],alignment=entry[8])
        # SHT_NOBITS has no file bytes; its memory contents start at zero.
        if entry[1]==8:
            result[name]['raw'] = bytes(entry[5])
    return result


def externals(path):
    return sorted(re.search(r"^FUNC '([^']+)'", value)[1]
                  for value in shared.static_btf.table(path).values()
                  if value.startswith('FUNC ') and 'linkage=extern' in value)


def proof(baseline, candidate, mode):
    old, new = sections(baseline), sections(candidate)
    a = {k:v['raw'] for k,v in old.items() if v['flags'] & 4}
    b = {k:v['raw'] for k,v in new.items() if v['flags'] & 4}
    require(set(a) == set(b), 'Executable entry points changed')
    changed = [name for name in a if a[name] != b[name]]
    require(changed == ['struct_ops/llama_enqueue'], 'Code outside enqueue changed: '+repr(changed))
    growth = (len(b[changed[0]]) - len(a[changed[0]])) // 8
    require(0 < growth <= 320, 'Enqueue instruction budget exceeded')
    for name in ['.data', '.bss', '.rodata', '.struct_ops.link', 'license']:
        require((name in old) == (name in new), 'Data sections changed: '+name)
        if name in old:
            require(old[name]['raw'] == new[name]['raw'], 'Existing control/ops/global ABI changed: '+name)
    before, after = shared.map_schema(baseline), shared.map_schema(candidate)
    require(set(after)-set(before) == {'handoff_stats'} and all(after.get(k)==v for k,v in before.items()), 'Unexpected map schema change')
    added = set(externals(candidate))-set(externals(baseline))
    require(added == ({'scx_bpf_kick_cpu'} if mode=='decode' else set()), 'Unexpected kfunc addition')
    require(not set(externals(baseline))-set(externals(candidate)), 'Existing kfunc removed')
    return dict(status='PASS_ENQUEUE_ONLY', new_instructions=growth, new_maps=1, new_callbacks=0,
                added_kfuncs=sorted(added), changed_sections=changed, ops_flags=8,
                counter_bytes_per_cpu=64, existing_control_and_map_abi_unchanged=True)

def build(output, baseline_build):
    output,baseline_build = Path(output).resolve(),Path(baseline_build).resolve()
    require(not output.exists(),'Use a new handoff-build directory')
    report = json.loads((baseline_build/'static-report.json').read_text())
    require(report['status']=='PASS' and report['ops_flags']==8,'Invalid baseline build')
    require(report['kernel']==Path('/proc/sys/kernel/osrelease').read_text().strip() and report['btf_sha256']==sha('/sys/kernel/btf/vmlinux'),'Kernel/BTF changed')
    require(sha(report['header'])==report['header_sha256'],'Kernel header changed')
    for key in ['source','full_object','plain_object','loader']:
        require(sha(report[key]['path'])==report[key]['sha256'],'Baseline artifact changed: '+key)
    output.mkdir(parents=True)
    original = Path(report['source']['path']).read_text()
    (output/'original.bpf.c').write_text(original)
    for role in ['full_object','plain_object']:
        shutil.copyfile(report[role]['path'],output/(role+'.bpf.o'))
    commands, variants = [],{}
    def run(command):
        command = list(map(str,command));commands.append(command)
        result = subprocess.run(command,capture_output=True,text=True)
        with (output/'compile.log').open('a') as stream:
            stream.write(repr(command)+'\n'+result.stdout+result.stderr)
        require(result.returncode==0,'Compile/static check failed; inspect compile.log')
    for mode in MODES:
        folder = output/mode;folder.mkdir()
        source = folder/'handoff.bpf.c';source.write_text(derive.bpf(original,mode))
        objects, proofs = {},{}
        for role, diagnostics in [('full_object',True),('plain_object',False)]:
            command = next(list(c) for c in report['commands'] if c[0]=='clang' and ('-DNEW_A_DIAGNOSTICS' in c)==diagnostics)
            obj = folder/(role+'.bpf.o')
            command[command.index('-c')+1] = str(source)
            command[command.index('-o')+1] = str(obj)
            run(command)
            proofs[role] = proof(output/(role+'.bpf.o'),obj,mode)
            objects[role] = dict(path=str(obj),sha256=sha(obj),relative=str(obj.relative_to(output)))
        shared.prepare_build.generate_loader(folder,guard=report['guard'])
        derive.loader(folder)
        loader = folder/'loader'
        obj = objects['full_object']['path']
        run(['cc','-O2','-g','-Wall','-Wextra','-Werror','-std=gnu11',
             '-I'+str(REPO/'tools/sched_ext/new_a'),'-I'+str(REPO/'tools/sched_ext/include'),
             '-DNEW_A_DIAGNOSTICS','-DHANDOFF_MODE=\"'+mode+'\"','-DBPF_OBJECT_PATH="'+obj+'"',folder/'loader.c','-o',loader,'-lbpf','-lelf','-lz'])
        run([loader,'--help'])
        require((obj+'\0').encode() in loader.read_bytes(),'Loader object binding differs')
        variants[mode] = dict(objects=objects,proofs=proofs,source=dict(path=str(source),sha256=sha(source),relative=str(source.relative_to(output))),
                             loader=dict(path=str(loader),sha256=sha(loader),relative=str(loader.relative_to(output))))
    signatures = shared.static_btf.inspect({mode:variant['objects']['full_object']['path'] for mode,variant in variants.items()},'/sys/kernel/btf/vmlinux')
    result = dict(status='PASS_ENQUEUE_ONLY',kernel=report['kernel'],btf_sha256=report['btf_sha256'],baseline_source=report['source'],
                  baseline_objects={role:dict(report[role],relative=role+'.bpf.o') for role in ['full_object','plain_object']},
                  guard=report['guard'],variants=variants,kfunc_signatures=signatures,commands=commands,
                  verifier='NOT_RUN',attach='NOT_RUN',inference='NOT_RUN')
    (output/'handoff-static.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def validate(folder, expected):
    folder = Path(folder)
    report = json.loads((folder/'handoff-static.json').read_text())
    require(report == expected and report['status']=='PASS_ENQUEUE_ONLY', 'Build report changed')
    original = (folder/'original.bpf.c').read_text()
    require(sha(folder/'original.bpf.c')==report['baseline_source']['sha256'], 'Original source snapshot changed')
    for mode, variant in report['variants'].items():
        require((folder/variant['source']['relative']).read_text()==derive.bpf(original,mode), 'Derived policy changed')
        loader = folder/variant['loader']['relative']
        require(sha(loader)==variant['loader']['sha256'], 'Loader changed')
        require((variant['objects']['full_object']['path']+'\0').encode() in loader.read_bytes(), 'Loader binding differs')
        for role, obj in variant['objects'].items():
            base = report['baseline_objects'][role]
            require(sha(folder/base['relative'])==base['sha256'] and sha(folder/obj['relative'])==obj['sha256'], 'BPF object changed')
            require(proof(folder/base['relative'],folder/obj['relative'],mode)==variant['proofs'][role], 'Static proof differs')
    return report


if __name__=='__main__':
    import fcntl
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-build',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    with (REPO.parent/'new-a-runs/.measurement.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
        result=build(args.output,args.baseline_build)
    print(json.dumps({m:v['proofs'] for m,v in result['variants'].items()},indent=2))
