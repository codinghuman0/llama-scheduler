#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""Compare OpenMP execution and a persistent native execution pool."""
import importlib.util
import json
from pathlib import Path
import re
import sys
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('chunk_study',HERE.parent/'cooperative_scheduling/run.py')
chunk=importlib.util.module_from_spec(spec)
spec.loader.exec_module(chunk)
base,measure=chunk.base,chunk.measure
background_delta=chunk.background_delta
ARMS=['LINUX_BASE','NEW_A_BASE','LINUX_POOL','NEW_A_POOL']
COMPARISONS=[('LINUX_POOL','LINUX_BASE'),('NEW_A_POOL','NEW_A_BASE'),('NEW_A_POOL','LINUX_POOL'),('NEW_A_POOL','LINUX_BASE')]
original_teams=measure.openmp_teams


def teams(text,pid,sizes):
    if 'NEWA_NATIVE_TEAM' not in text:
        return original_teams(text,pid,sizes)
    measure.require(text.count('NEWA_POOL attached=1 ')==1,'Persistent pool attachment missing or repeated')
    text=text.split('NEWA_POOL attached=1 ',1)[1]
    rows=re.findall(r'NEWA_NATIVE_TEAM pid=(\d+) team=(\d+) index=(\d+) tid=(\d+)',text)
    measure.require(rows and all(int(p)==pid and int(n) in sizes for p,n,_,_ in rows),'Unexpected native team')
    result={}
    for size in sizes:
        members={int(i):int(t) for _,n,i,t in rows if int(n)==size}
        measure.require(sorted(members)==list(range(size)) and len(set(members.values()))==size,'Native worker membership incomplete')
        result[str(size)]={str(i):t for i,t in sorted(members.items())}
    return dict(pid=pid,backend='native',teams=result)

measure.openmp_teams=teams
original_snapshot=measure.snapshot

def snapshot(pid,cpus,policy):
    value=original_snapshot(pid,cpus,policy)
    value['mapped_cpu_libraries']=sorted({line.split()[-1] for line in Path('/proc/'+str(pid)+'/maps').read_text().splitlines() if '/libggml-cpu.so' in line})
    return value

measure.snapshot=snapshot


def cases(selection,argv,environment,candidate):
    n=selection['selected_physical_cores'];result={}
    for arm in ARMS:
        pooled=arm.endswith('POOL');command=list(argv);env=dict(environment)
        env['GGML_NEWA_POOL']='on' if pooled else 'off'
        if pooled:
            command[0]=str(candidate)
            env['LD_LIBRARY_PATH']=str(candidate.parent)
        server=Path(command[0])
        result[arm]=dict(server_argv=command,server_env=env,server_cpus=selection['selected_cpus'],
            compute_threads=n,batch_threads=n,expected_teams=[n],cpu_accounting='process_ticks',
            marker_elf=str(measure.marker_for(server,None)),expected_cpu_library=str((server.parent/'libggml-cpu.so').resolve()))
    return result


class Experiment(base.Experiment):
    source_dir=HERE
    dependency_dirs=(chunk.HERE,)
    scope='PERSISTENT_POOL_EXPERIMENT_NOT_SAFETY_APPROVED'
    plan_builder=staticmethod(lambda blocks,linux_only:base.plans(blocks,linux_only,arms=ARMS))
    summarize=staticmethod(lambda rows:base.summarize(rows,arms=ARMS,comparisons=COMPARISONS))

    def configure_parser(self,parser,timestamp):
        super().configure_parser(parser,timestamp)
        parser.description=__doc__
        parser.set_defaults(server=base.REPO.parent/'new-a-lab/build-pool-omp/bin/llama-server',
                            output=base.REPO.parent/'new-a-performance/persistent-pool'/timestamp)
        parser.add_argument('--candidate-server',type=Path,default=base.REPO.parent/'new-a-lab/build-pool-native/bin/llama-server')
        parser.add_argument('--native-source',type=Path,default=base.REPO.parent/'new-a-lab/llama-pool')

    def prepare(self,root,setup,args):
        candidate=args.candidate_server.resolve()
        self.case_builder=lambda selection,argv,env:cases(selection,argv,env,candidate)
        setup=super().prepare(root,setup,args)
        setup['candidate_mode']='persistent_native_pool'
        setup['build_options']={}
        keys=['CMAKE_BUILD_TYPE','GGML_NATIVE','GGML_OPENMP','GGML_BLAS','GGML_CUDA','GGML_VULKAN','LLAMA_SCX_PHASE_HINT','LLAMA_SCX_PHASE_TRACE','LLAMA_BUILD_UI']
        for role,server,openmp in [('baseline',args.server,'ON'),('candidate',candidate,'OFF')]:
            cache=server.parent.parent/'CMakeCache.txt'
            values={line.split(':',1)[0]:line.split('=',1)[1] for line in cache.read_text().splitlines() if '=' in line and ':' in line and not line.startswith(('#','//'))}
            measure.require(values['GGML_OPENMP']==openmp,'Unexpected OpenMP build option')
            measure.require(Path(values['CMAKE_HOME_DIRECTORY']).resolve()==args.native_source.resolve(),'Build source directory differs')
            setup['build_options'][role]={key:values[key] for key in keys}
            target=root/'build-options'/role
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(cache.read_bytes())
        measure.require(all(setup['build_options']['baseline'][key]==setup['build_options']['candidate'][key] for key in keys if key!='GGML_OPENMP'),'CPU build options differ')
        setup['candidate_artifacts']={str(p.resolve()):measure.sha(p) for p in [candidate,*candidate.parent.glob('*.so*')] if p.is_file()}
        setup['native_sources']={}
        for name in ['ggml/src/ggml-cpu/ggml-cpu.c','tools/server/server-context.cpp']:
            path=args.native_source.resolve()/name
            setup['native_sources'][str(path)]=measure.sha(path)
            target=root/'native-source-snapshot'/name
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(path.read_bytes())
        setup['team_evidence']='Native TIDs are logged after attachment and checked against request snapshots; legacy openmp-team.json filename retained'
        return setup

    @staticmethod
    def validate_visit(root,visit,setup,row):
        folder=Path(row['directory']);log=(folder/'server.stderr.log').read_text();pooled=visit['arm'].endswith('POOL')
        measure.require(('NEWA_POOL attached=1 ' in log)==pooled,'Pool mode differs')
        measure.require(('NEWA_NATIVE_TEAM' in log)==pooled,'Execution backend differs')
        measure.require(all(measure.sha(p)==h for p,h in setup['candidate_artifacts'].items()),'Candidate artifact changed')
        measure.require(all(measure.sha(p)==h for p,h in setup['native_sources'].items()),'Native source changed')
        before=json.loads((folder/'counters-before.json').read_text());after=json.loads((folder/'counters-after.json').read_text())
        for value in [before,after]:
            measure.require(value['mapped_cpu_libraries']==[setup['expected_cpu_library']],'Wrong CPU backend library loaded')
        if pooled:
            team=json.loads((folder/'openmp-team.json').read_text())
            tids={str(tid) for members in team['teams'].values() for tid in members.values()}
            measure.require(tids<=before['threads'].keys() and tids<=after['threads'].keys(),'Registered worker TID disappeared')
        row['background']=background_delta(before['background'],after['background'])
        measure.save(folder/'result.json',row)

    @staticmethod
    def analyze(root,summary):
        measure.save(root/'screening.json',dict(status='SCREENING_COMPLETE_NO_CONFIRMATION',comparisons=summary['comparisons']))

if __name__=='__main__':
    measure.main(experiment=Experiment())
