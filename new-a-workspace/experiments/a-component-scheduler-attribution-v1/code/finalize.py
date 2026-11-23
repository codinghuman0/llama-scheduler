"""Report frozen results, preservation and a model-free review archive."""
import argparse,gzip,json,os,shutil,subprocess,tempfile,zipfile
from pathlib import Path
from common import *
from check import protection
from analyze import analyze,validate_raw
from recalculate import recalculate

def main():
 p=argparse.ArgumentParser();p.add_argument('--name',default='attribution-v1');a=p.parse_args()
 no_model_process();guard();verify_inputs();report=analyze(a.name);independent=recalculate(a.name);save(D/'evidence/independent-recalculation.json',independent)
 preserved=protection();save(D/'evidence/protection-after.json',preserved);assert preserved['status']=='PASS'
 smokes=[]
 for root in [D/'results/scheduler-admission-v1',D/'results/linux-smoke-v1']:
  state=read(root/'campaigns.json')
  for s in state['completed']:
   spec={k:v for k,v in s.items() if k not in ['path','status']};v=validate_raw(D/s['path'],spec);smokes.append(dict(arm=spec['arm'],cohort=spec['cohort'],raw=s['path'],status='PASS',E_epochs=v['E_epochs']))
 save(D/'evidence/final-functional-audit.json',dict(status='PASS',visits=smokes))
 prior=read(D/'inputs/prior-direct-comparison-summary.json')
 lines=['# A 구성 요소 기여 검증','',f"상태: **{report['status']}**. 이번 구성 요소 캠페인은 **1개**이며, 이전 A/B0 독립 확인 2개와 구분합니다.",'','## 보존된 A와 이번 변경','',f"기존 파일 {preserved['protected_files']:,}개의 내용과 mode를 확인했습니다. B0/R/A/P, 모델, 소스, 과거 원시 결과와 실패 기록은 변경하지 않았습니다. 새 최적화나 빌드는 없으며 신규 코드는 실행·검증·분석 도구뿐입니다.",'','기존 A/B0: ambient +16.55%, +16.33%; cpu25 +25.97%, +26.17% (각 캠페인 조건별 8 pairs). 이 결과는 기본 Linux에서의 누적 runtime 효과입니다. 이번 결과와 합산하지 않습니다.','', 'B0_L은 역사적 원본 소스의 보존된 재빌드입니다. F6_L/A_L은 동일 A binary/DSO와 센서·guard를 유지하며 적격 multi-token Decode 선택만 fixed6/pressure로 다릅니다. A_S는 A_L에 기존 observe 스케줄러를 추가합니다. pool off, 같은 모델/입력/자원/정상 요청 내부 KV만 사용합니다.','','## 직접 측정','', '| 조건 | 비교 | 평균 paired gain | bootstrap 95% 구간 | faster blocks | paired wall 감소 |','|---|---|---:|---|---:|---:|']
 for c in report['cells']:
  for label,v in c['contrasts'].items():
   lo,hi=v['bootstrap_95_pct'];lines.append(f"| {c['condition']} | {label} | {v['mean_paired_gain_pct']:+.3f}% | [{lo:+.3f}, {hi:+.3f}]% | {v['faster_blocks']}/{c['planned_blocks']} | {v['mean_paired_wall_reduction_pct']:+.3f}% |")
 lines+=['','| 조건 | arm | tokens/s 평균 | cohort wall s 평균 | process CPU s 평균 |','|---|---|---:|---:|---:|']
 for c in report['cells']:
  for arm,m in c.get('absolute',{}).items():lines.append(f"| {c['condition']} | {arm} | {m['tokens_per_second']:.4f} | {m['wall_s']:.4f} | {m['cpu_s']:.4f} |")
 lines+=['','완결된 block 내 직접 비율의 평균입니다. 절대값 평균의 비율과는 다릅니다. cohort별 4 blocks, 50:50 stratified paired bootstrap 10,000회(seed 20261122); 같은 resample에 모든 arm을 유지했습니다. cohort별 결과와 모든 block은 component-summary.json에 있습니다. 보조 비교의 CI는 다중 비교 오류율 보장이 아닙니다.','','## E의 적격 Decode 선택 기여','']
 contribution={}
 for c in report['cells']:
  sels=c.get('E_selections',{});dec={}
  for arm,visits in sels.items():
   counts=[sum(e['eligible'][size][j] for v in visits for e in v['epochs'] for size in range(2,9)) for j in range(2)]
   dec[arm]=dict(eligible_multitoken_5_6=counts,shadow_choices=sorted({e['shadow'] for v in visits for e in v['epochs']}),locked_epochs=sum(e['locked'] for v in visits for e in v['epochs']))
  if 'A_L/F6_L' not in c['contrasts']:continue
  v=c['contrasts']['A_L/F6_L'];same=dec['A_L']['eligible_multitoken_5_6']==dec['F6_L']['eligible_multitoken_5_6'];effect='inconclusive (동일한 실제 선택)' if same else v['sign'];contribution[c['condition']]=dict(E_selection_effect=effect,observed=dec,scheduler_same_aggregate_choices=dec.get('A_S',{}).get('eligible_multitoken_5_6')==dec['A_L']['eligible_multitoken_5_6'])
  lines += [f"- {c['condition']}: **{effect}**. A_L/F6_L {v['mean_paired_gain_pct']:+.3f}%. 적격 multi-token 선택 [5,6] 횟수: F6_L {dec['F6_L']['eligible_multitoken_5_6']}, A_L {dec['A_L']['eligible_multitoken_5_6']}. F6_L shadow choices {dec['F6_L']['shadow_choices']}." ]
  if same:lines+=['  실제 선택이 같으므로 이 조건의 작은 성능 차이를 adaptive worker-choice 이득으로 해석하지 않습니다.']
 lines+=['','센서 raw counter, threshold=.125, margin=.02, epoch/task 연속성 및 invalidation은 독립 재계산했습니다. fixed6은 센서와 검사를 끄지 않습니다. 단일 token Decode의 5-worker 예외 및 Mixed/UNKNOWN 6-worker fallback은 소스에 보존되어 있으며, 본 8-request fixture가 모든 fallback을 따로 유발한 검증은 아닙니다. submitted 선택과 실제 OpenMP 팀 로그를 함께 확인했습니다.','','## S의 추가 효과와 최종 조합','']
 for c in report['cells']:
  for label in ['A_S/A_L','A_S/B0_L']:
   if label not in c['contrasts']:continue
   v=c['contrasts'][label];lines += [f"- {c['condition']} {label}: {v['mean_paired_gain_pct']:+.3f}%, {v['sign']}; " + (f"system gate={v['target_pass']}, CI 하한 >=5%={v['strong_evidence']}." if label=='A_S/B0_L' else '동일 userspace 정책에 S를 추가한 효과입니다.')]
  if c['condition'] in contribution:
   dec=contribution[c['condition']];lines += [f"  A_S 실제 선택: {dec['observed'].get('A_S')}. A_L과 aggregate 선택 일치: {dec['scheduler_same_aggregate_choices']}. 선택이 다르면 scheduler와 E의 매개 효과를 포함합니다."]
 lines+=['','S는 보존된 **observe**, FULL diagnostics, partial switching, fixed affinity 구성입니다. phase 상태와 Decode shadow attempts를 기록하지만 실제 phase 기반 배치 변경은 하지 않습니다. 따라서 이 결과를 새로운 phase-aware kernel dispatch 정책의 증명으로 부르지 않습니다. loader/launcher와 부하 generator는 Linux, 선택 server/worker는 SCHED_EXT; matching marker ELF/PID, actual ops/BPF IDs/tags, phase bits, zero mask/tracking failure, zero handoff moves, 일정 enable_seq/무 bypass 증가, 정상 cleanup을 확인했습니다. 안전 진단 비용을 제거하거나 성능에서 빼지 않았습니다.','','기존 A는 기본 실사용 구성으로 보존합니다. 스케줄러 조합은 본 캠페인의 기여 분석 연구 구성입니다. S 효과가 음수라면 원본 대비 최종 조합 gain과 별도로 그대로 보고합니다.','','## 정확성·실패·범위','',f"기능 smoke {len(smokes)} fresh servers; 유효 measured visits {report['counts']['valid_visits']}. 모든 유효 warmup/measurement에서 실제 128 tokens/request, 8 distinct requests, cache_n=0, 기존 B0 oracle exact tokens를 확인했습니다. 한 요청의 token이나 여덟 요청을 독립 반복으로 세지 않았습니다.",f"실제 measured cpu25 소비 범위: {report['actual_cpu25_cores_range']} core. 동일 CPU10 affinity와 정상 정책, .0125 CPU seconds/.05 seconds 부하입니다. 총 CPU seconds는 arm의 wall time에 따라 달라도 평균 core 소비를 검증했습니다.",f"실패/미실행: {len(report['invalid_or_missing'])} planned visits; results/{a.name}/campaigns.json 참조. 본 측정 전 분석기에서 load policy를 SCHED_EXT로 잘못 기대한 검사를 수정했습니다. 실제 runner는 처음부터 load policy 0을 검증했습니다. 모델 방문을 대체하지 않았고 수정 기록을 보존했습니다.",'','같은 AMD·모델·기존 두 cohort·고정 부하 범위입니다. Intel, 일반 품질, 모든 입력/길이, 변동 부하, 모든 static 정책에 대한 우월성을 입증하지 않습니다. fixed6_S/fixed5가 없으므로 완전한 요인 상호작용 분해가 아닙니다. 이번 결과는 한 캠페인이며 A_S 또는 E가 두 번 독립 재현된 결과가 아닙니다. throughput 증가와 wall 감소를 구분하며 CPU seconds는 에너지가 아닙니다. nonstream TTFT/p95 token latency는 측정하지 않았습니다. 과거 dynamic-affinity 실패는 해결되지 않았습니다.','','## 재현과 다음 단계 하나','','```bash','./reproduce.sh verify',f'./reproduce.sh recalculate --name {a.name}',f'./reproduce.sh analyze --name {a.name}','```','','다음 단계: 동결된 네 arm 구성 요소 캠페인을 별도로 독립 재현합니다. 현재 goal에서는 반복을 추가하지 않습니다. 실행 명령과 권한/cleanup 범위는 README.md와 reproduce.sh에 있습니다.']
 save(D/'component-interpretation.json',contribution);(D/'component-summary.md').write_text('\n'.join(lines)+'\n')
 finalenv=guard();save(D/'evidence/final-cleanup.json',dict(status='PASS',environment=finalenv,owned_processes_running=False,sched_ext='disabled',old_protection=preserved['status']))
 (D/'GOAL_STATE.md').write_text('# Frozen A component attribution\n\nWork status: COMPLETE_REGISTERED_SCOPE. Scientific status: '+report['status']+'\nOne campaign; no extra repetitions. A and all prior evidence preserved.\nRaw: results/'+a.name+'; component-summary.md/json; component-interpretation.json.\nVerification: ./reproduce.sh verify; ./reproduce.sh recalculate --name '+a.name+'\nNext separate task: independent reproduction of this frozen component campaign, commands in README.md.\nNo new runtime optimization; current goal stops after fixed protocol and verified review package.\n')
 event('scope-complete',status=report['status'],planned_visits=64,valid_visits=report['counts']['valid_visits'],next='independent component replication')
 save(D/'completion-audit.json',dict(work_status='COMPLETE_REGISTERED_SCOPE',scientific_status=report['status'],campaigns=1,raw_recalculation=independent['status'],protected=preserved,smoke_visits=len(smokes),counts=report['counts'],scheduler_disabled=True,extra_repetitions=0))
 archive=D/'a-component-scheduler-attribution-v1-review.zip';assert not archive.exists()
 excluded={'review-manifest.json','review-zip.json',archive.name,archive.name+'.sha256','package-validation.json'}
 members={}
 for f in sorted(D.rglob('*')):
  if f.is_file() and f.name not in excluded and '__pycache__' not in f.parts and not f.name.endswith('.zip'):
   members[str(f.relative_to(D))]=dict(sha256=sha(f),size=f.stat().st_size)
 manifest=dict(schema=1,archive_members=members,excludes='model/runtime/full build and archive sidecars; original workspace content referenced by hashes')
 save(D/'review-manifest.json',manifest)
 with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for rel in members:z.write(D/rel,rel)
  z.writestr('REVIEW_MANIFEST.json',json.dumps(manifest,indent=2)+'\n')
 with zipfile.ZipFile(archive) as z:
  assert z.testzip() is None and set(z.namelist())==set(members)|{'REVIEW_MANIFEST.json'}
  import hashlib
  for rel,row in members.items():assert hashlib.sha256(z.read(rel)).hexdigest()==row['sha256']
  with tempfile.TemporaryDirectory(prefix='newa-component-review-',dir='/tmp') as td:
   z.extractall(td)
   r=subprocess.run(['python3','-B',str(Path(td)/'code/recalculate.py'),'--name',a.name],capture_output=True,text=True,timeout=60)
   assert r.returncode==0,r.stderr
   off=json.loads(r.stdout);assert off['status']=='PASS'
 digest=sha(archive);(D/(archive.name+'.sha256')).write_text(digest+'  '+archive.name+'\n')
 save(D/'review-zip.json',dict(path=archive.name,sha256=digest,bytes=archive.stat().st_size,members=len(members)+1))
 save(D/'package-validation.json',dict(status='PASS',crc='PASS',membership='PASS',hashes='PASS',offline_model_free_recalculation=off,sha256=digest))
 print(json.dumps(read(D/'review-zip.json'),indent=2));print('FINAL '+report['status'])
if __name__=='__main__':main()
