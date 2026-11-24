# SPDX-License-Identifier: GPL-2.0
"""Synthetic topology tests, not teammate hardware or performance validation."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parent))
import collect
import profiles
import build_probe


def fixture(p=4, e=8, vendor='GenuineIntel', hybrid=True, smt=True, groups=None, offline=(), allowed=None, packages=None, cache_width=4):
    groups = groups or [[2*i, 2*i+1] if smt else [i] for i in range(p)] + [[(2*p if smt else p)+i] for i in range(e)]
    all_cpus = sorted(c for group in groups for c in group)
    online = sorted(set(all_cpus) - set(offline))
    allowed = online if allowed is None else sorted(allowed)
    cpus, typed, hardware = {}, {}, {}
    package_counts = {}
    for i, group in enumerate(groups):
        package = packages[i] if packages else 0
        core = package_counts.get(package, 0); package_counts[package] = core+1
        for c in group:
            if c not in online:
                continue
            cpus[str(c)] = dict(package=package, die=0, core=core, siblings_all=sorted(group), core_type_raw='', capacity=None,
                                vendor=vendor, model_name='SYNTHETIC_NOT_HARDWARE', family=6 if vendor == 'GenuineIntel' else 25, model=100, stepping=1)
            typed[c] = 64 if hybrid and i < p else 32 if hybrid else 0
            e_index = i-p
            l2 = group if i < p else [x for g in groups[p+(e_index//cache_width)*cache_width:p+(e_index//cache_width+1)*cache_width] for x in g]
            l3 = [x for j,g in enumerate(groups) if (packages[j] if packages else 0) == package for x in g]
            hardware[str(c)] = dict(caches=[dict(level=2,type='Unified',shared_cpus=sorted(l2),id=str(i//cache_width),size='MOCK'),
                                                   dict(level=3,type='Unified',shared_cpus=sorted(l3),id=str(package),size='MOCK')],
                                    numa_node=package, cpuinfo_max_freq_khz=None, base_frequency_khz=None)
    value = dict(possible_cpus=all_cpus,present_cpus=all_cpus,online_cpus=online,process_allowed_cpus=allowed,allowed_cpus=allowed,
                 usable_cpus=sorted(set(online)&set(allowed)),cpus=cpus)
    evidence = dict(schema=1,max_cpus=1024,affinity_restored=True,cpus=[dict(cpu=c,vendor=vendor,family=cpus[str(c)]['family'],model=100,stepping=1,
                    hybrid=hybrid,core_type=typed[c],native_model=0,amd_leaf26=False,amd_heterogeneous=False) for c in value['usable_cpus']])
    extra = dict(cpus=hardware,cgroup=dict(version='v2',cpuset_cpus_effective=online,cpuset_mems_effective=[0],cpu_max='max 100000',
                 scope='SYNTHETIC',effective_cpu_authority='SCHED_GETAFFINITY_INTERSECT_ONLINE',paths_redacted=True))
    return value,evidence,extra


def detect(*args, **kwargs):
    return collect.detection(*fixture(*args, **kwargs))


def recommend(*args, **kwargs):
    return profiles.recommend(detect(*args, **kwargs))


class Shapes(unittest.TestCase):
    def assert_counts(self, value, compute, batch, p, e):
        self.assertEqual((value['compute_threads'],value['batch_threads'],value['http_threads']),(compute,batch,2))
        self.assertEqual((len(value['p_representatives']),len(value['selected_e_cpus'])),(p,e))
        self.assertEqual(len(value['affinity_cpus']),len(set(value['affinity_cpus'])))
        self.assertEqual(len({(x['package'],x['die'],x['core']) for x in value['cpu_mapping']}),batch)
        self.assertFalse(value['performance_validated']);self.assertFalse(value['execution_admitted'])
    def test_p4_e8_regression(self):
        v=recommend();self.assert_counts(v,4,8,4,4);self.assertEqual(v['affinity_cpus'],[0,2,4,6,8,9,10,11])
    def test_p6_e8(self):self.assert_counts(recommend(6,8),6,10,6,4)
    def test_p8_e8(self):self.assert_counts(recommend(8,8),8,12,8,4)
    def test_p8_e16(self):self.assert_counts(recommend(8,16),8,16,8,8)
    def test_p2_e8(self):self.assert_counts(recommend(2,8),2,6,2,4)
    def test_intel_homogeneous_8c16t(self):
        v=recommend(8,0,hybrid=False);self.assert_counts(v,8,8,0,0);self.assertEqual(v['profile'],'conservative_homogeneous_physical')
    def test_amd_homogeneous_8c16t(self):
        v=recommend(8,0,vendor='AuthenticAMD',hybrid=False);self.assert_counts(v,8,8,0,0);self.assertEqual(v['vendor'],'AMD')
    def test_smt_disabled_hybrid(self):self.assert_counts(recommend(6,8,smt=False),6,10,6,4)
    def test_smt_disabled_homogeneous(self):self.assert_counts(recommend(8,0,hybrid=False,smt=False),8,8,0,0)
    def test_offline_whole_p_core(self):
        v=recommend(offline=[0,1]);self.assert_counts(v,3,7,3,4);self.assertTrue(set(v['affinity_cpus']).isdisjoint({0,1}))
    def test_one_offline_smt_thread(self):
        v=recommend(offline=[0]);self.assert_counts(v,4,8,4,4);self.assertIn(1,v['p_representatives'])
    def test_offline_e_core_odd_available_count(self):
        v=recommend(offline=[15]);self.assert_counts(v,4,7,4,3)
    def test_cpuset_limited_physical_cores(self):
        allowed=[2,3,4,5,6,7,8,9,10,11];v=recommend(allowed=allowed)
        self.assert_counts(v,3,5,3,2);self.assertLessEqual(set(v['affinity_cpus']),set(allowed))
    def test_only_smt_sibling_allowed(self):
        v=recommend(allowed=[1,3,5,7,*range(8,16)]);self.assertEqual(v['p_representatives'],[1,3,5,7]);self.assert_counts(v,4,8,4,4)
    def test_noncontiguous_cpu_ids(self):
        groups=[[2,9],[17,25],[33,44],[55,61]]+[[c] for c in [70,72,75,80,85,90,94,100]]
        v=recommend(groups=groups);self.assertEqual(v['affinity_cpus'],[2,17,33,55,70,72,75,80]);self.assertEqual(int(v['affinity_mask_hex'],16).bit_count(),8)
    def test_package_core_ids_do_not_collide(self):
        packages=[0,0,1,1]+[0]*4+[1]*4
        v=recommend(packages=packages);self.assert_counts(v,4,8,4,4)
        self.assertTrue(any('NUMA' in w for w in v['unverified_assumptions']))
    def test_missing_p_or_e_blocks_formula(self):
        for data in [dict(p=0,e=8),dict(p=4,e=0)]:
            with self.subTest(data=data),self.assertRaises(ValueError):recommend(**data)
    def test_odd_e_one_allows_zero_extra_threads(self):self.assert_counts(recommend(4,1),4,4,4,0)
    def test_zero_effective_cpu_blocked(self):
        with self.assertRaises(ValueError):recommend(allowed=[])


class CachePlacement(unittest.TestCase):
    def test_single_l2_compact(self):
        v=recommend(6,8);self.assertTrue(v['single_e_l2_group']);self.assertEqual(v['e_placement_effective'],'SINGLE_L2_GROUP')
    def test_spread_is_distinct_without_superiority_claim(self):
        d=detect(6,8);a=profiles.recommend(d);b=profiles.recommend(d,'spread')
        self.assertNotEqual(a['selected_e_cpus'],b['selected_e_cpus']);self.assertEqual([len(g['selected_cpus']) for g in b['selected_e_l2_groups']],[2,2]);self.assertFalse(b['performance_validated'])
    def test_cache_group_too_small_is_not_single_group(self):
        v=recommend(8,16);self.assertFalse(v['single_e_l2_group']);self.assertEqual(len(v['selected_e_l2_groups']),2)
    def test_missing_l2_reports_uncertainty(self):
        value,evidence,extra=fixture()
        for cpu in extra['cpus'].values():cpu['caches']=[]
        d=collect.detection(value,evidence,extra);v=profiles.recommend(d)
        self.assertEqual(v['e_placement_effective'],'LOWEST_CPU_IDS_L2_NOT_VERIFIED')
        with self.assertRaises(ValueError):profiles.recommend(d,'spread')
    def test_inconsistent_l2_rejected(self):
        value,evidence,extra=fixture();extra['cpus']['8']['caches'][0]['shared_cpus']=[8,9]
        with self.assertRaises(ValueError):profiles.recommend(collect.detection(value,evidence,extra))
    def test_repeated_generation_deterministic(self):
        d=detect(6,8);self.assertEqual(profiles.recommend(d),profiles.recommend(copy.deepcopy(d)))


class FailClosed(unittest.TestCase):
    def test_unknown_intel_type(self):
        v,e,x=fixture();e['cpus'][0]['core_type']=0
        with self.assertRaises(ValueError):collect.detection(v,e,x)
    def test_conflicting_siblings(self):
        v,e,x=fixture();v['cpus']['1']['siblings_all']=[1]
        with self.assertRaises(ValueError):collect.detection(v,e,x)
    def test_amd_heterogeneous_never_intel_pe(self):
        v,e,x=fixture(8,0,vendor='AuthenticAMD',hybrid=False)
        for row in e['cpus']:row['amd_heterogeneous']=True;row['amd_leaf26']=True
        with self.assertRaises(ValueError):collect.detection(v,e,x)
    def test_amd_unknown_native_models(self):
        v,e,x=fixture(8,0,vendor='AuthenticAMD',hybrid=False);e['cpus'][0]['native_model']=1
        with self.assertRaises(ValueError):collect.detection(v,e,x)
    def test_homogeneous_capacity_conflict(self):
        v,e,x=fixture(8,0,hybrid=False);v['cpus']['0']['capacity']='1024'
        with self.assertRaises(ValueError):collect.detection(v,e,x)
    def test_missing_physical_identity_blocks(self):
        v,e,x=fixture();v['cpus']['0']['package']=-1
        with self.assertRaises(ValueError):collect.detection(v,e,x)
    def test_changed_detection_fingerprint(self):
        d=detect();d['hardware']['cpus']['8']['numa_node']=99
        with self.assertRaises(ValueError):profiles.recommend(d)
    def test_missing_numa_or_cache_coverage(self):
        v,e,x=fixture();x['cpus'].pop('0')
        with self.assertRaises(ValueError):collect.detection(v,e,x)
    def test_effective_cpuset_mismatch(self):
        v,e,x=fixture();x['cgroup']['cpuset_cpus_effective']=[0,1]
        with self.assertRaises(ValueError):collect.detection(v,e,x)
    def test_cpuid_missing_or_duplicate_cpu(self):
        for duplicate in [False,True]:
            v,e,x=fixture();e['cpus'].pop()
            if duplicate:e['cpus'].append(e['cpus'][0])
            with self.assertRaises(ValueError):collect.detection(v,e,x)
    def test_hotplug_no_retry(self):
        v,e,x=fixture();changed=copy.deepcopy(v);changed['online_cpus'].pop()
        with patch.object(build_probe,'verify_probe',return_value='MOCK'),patch.object(collect.portable,'snapshot',side_effect=[v,changed]) as reader,patch.object(collect,'extras',return_value=x),patch.object(collect.portable,'probe',return_value=e):
            with self.assertRaises(ValueError):collect.inspect('MOCK')
            self.assertEqual(reader.call_count,2)


class ValidationAndPlans(unittest.TestCase):
    def test_fresh_same_topology_validation(self):
        d=detect(6,8);self.assertEqual(profiles.validate(profiles.recommend(d),d)['status'],'VALID_CONFIGURATION_ONLY')
    def test_modified_configuration_rejected(self):
        d=detect();v=profiles.recommend(d)
        for key,changed in [('compute_threads',True),('batch_threads',10),('affinity_cpus',[0,1,2]),('performance_validated',True),('affinity_mask_hex','0x1'),('topology_fingerprint','foreign')]:
            candidate=copy.deepcopy(v);candidate[key]=changed
            with self.subTest(key=key),self.assertRaises(ValueError):profiles.validate(candidate,d)
    def test_changed_allowed_scope_rejected(self):
        config=profiles.recommend(detect())
        with self.assertRaises(ValueError):profiles.validate(config,detect(allowed=list(range(2,16))))
    def test_p6e8_plan_a_b_c_d_and_same_mask_control(self):
        plan=profiles.experiments(detect(6,8),6,8)
        self.assertEqual([(x['compute_threads'],x['batch_threads']) for x in plan['candidates'].values()],[(6,6),(6,10),(6,12),(6,14)])
        self.assertEqual(len(plan['FUNCTIONAL']),4);self.assertEqual([x['condition'] for x in plan['EXPLORATION']],['C-B','E-B','E-B','C-B'])
        self.assertEqual(sum(x['warmups']+x['measurements'] for x in plan['EXPLORATION']),12)
        self.assertEqual(len(plan['thread_only_control']['affinity_cpus']),14);self.assertFalse(plan['execution_admitted'])
    def test_expected_p6e8_never_forced_on_p4(self):
        with self.assertRaises(ValueError):profiles.experiments(detect(),6,8)
    def test_e_count_unavailable_or_boolean_rejected(self):
        for n in [True,9,-1]:
            with self.subTest(n=n),self.assertRaises(ValueError):profiles.recommend(detect(),e_count=n)


class CpusetReader(unittest.TestCase):
    def test_namespaced_v2_and_path_redaction(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);cg=root/'cgroup';mount=root/'mounts';point=root/'mount'
            point.mkdir();(point/'cpuset.cpus.effective').write_text('2-5,8-11');(point/'cpuset.mems.effective').write_text('0');(point/'cpu.max').write_text('200000 100000')
            cg.write_text('0::/\n');mount.write_text(f'1 2 0:1 /host/subtree {point} rw - cgroup2 cgroup rw\n')
            data=collect.cgroup_constraints(cg,mount);self.assertEqual(data['cpuset_cpus_effective'],[2,3,4,5,8,9,10,11]);self.assertNotIn(str(root),json.dumps(data))
    def test_v1_inherited_cpuset(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);point=root/'mount';(point/'child').mkdir(parents=True)
            (point/'child/cpuset.cpus').write_text('');(point/'cpuset.cpus').write_text('0-3');cg=root/'cgroup';cg.write_text('4:cpuset:/child\n')
            mount=root/'mountinfo';mount.write_text(f'1 2 0:1 / {point} rw - cgroup cgroup rw,cpuset\n')
            self.assertEqual(collect.cgroup_constraints(cg,mount)['cpuset_cpus_effective'],[0,1,2,3])
    def test_unreadable_cpuset_not_fabricated(self):
        self.assertIsNone(collect.cgroup_constraints(Path('/NONEXISTENT'),Path('/NONEXISTENT'))['cpuset_cpus_effective'])


class ProbeAndCLI(unittest.TestCase):
    def test_actual_helper_compile_integrity_without_bpf(self):
        with tempfile.TemporaryDirectory() as temp:
            binary=build_probe.build(Path(temp)/'new');self.assertEqual(build_probe.verify_probe(binary),build_probe.sha(binary))
            binary.chmod(0o775)
            with self.assertRaises(ValueError):build_probe.verify_probe(binary)
            binary.chmod(0o755);binary.write_bytes(binary.read_bytes()+b'CHANGED')
            with self.assertRaises(ValueError):build_probe.verify_probe(binary)
    def test_build_existing_output_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(FileExistsError):build_probe.build(temp)
    def test_no_execute_or_sudo_option(self):
        cli=Path(__file__).with_name('new-a-topology-config')
        result=subprocess.run([sys.executable,'-B',str(cli),'recommend','--probe','NO_HELPER','--execute'],capture_output=True,text=True)
        self.assertEqual(result.returncode,2);self.assertIn('unrecognized arguments',result.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
