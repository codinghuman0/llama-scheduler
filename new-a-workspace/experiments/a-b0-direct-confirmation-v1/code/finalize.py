"""Post-timing protection audit, requirement audit and scoped Korean report."""
import argparse,fcntl,gzip,json,os,stat,statistics
from pathlib import Path
from common import *
def main(name):
 root=D/'results'/name;summary=read(root/'analysis.json');state=read(root/'campaigns.json')
 with (W/'state/.measurement.lock').open('r') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);no_model_process();verify_inputs()
  before=read(D/'evidence/protection-before.json');cache={}
  for rel,row in before['files'].items():
   p=W/rel;st=p.stat();key=(st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns)
   if key not in cache:cache[key]=sha(p)
   assert cache[key]==row['sha256'] and st.st_mode&0o777==row['mode'],rel
   assert (os.readlink(p) if p.is_symlink() else None)==row['symlink'],rel
  assert (W/'models/model.gguf').stat().st_ino==before['model_inode']
  originals=read_gzip(W/'maintenance/compact-20261122/originals-preserved.json.gz')
  for row in originals:
   p=Path(row['path']);st=p.stat();key=(st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns)
   if key not in cache:cache[key]=sha(p)
   assert cache[key]==row['sha256'],str(p)
  leftovers=[]
  for p in D.glob('results/**/server/process.json'):
   pid=read(p)['pid']
   if Path(f'/proc/{pid}').exists():
    # A reused PID is not ours; compare current command path before reporting it.
    cmd=Path(f'/proc/{pid}/cmdline').read_bytes()
    if b'llama-server' in cmd:leftovers.append(dict(pid=pid,record=str(p)))
  for p in D.glob('results/**/controlled-load/identity.json'):
   v=read(p);proc=Path(f'/proc/{v["pid"]}')
   if proc.exists():
    fields=(proc/'stat').read_text().rsplit(')',1)[1].split()
    if int(fields[19])==v['starttime']:leftovers.append(dict(pid=v['pid'],record=str(p)))
  assert not leftovers
  protection=dict(status='PASS',time=now(),protected_workspace_files=len(before['files']),outside_original_files=len(originals),model_inode_unchanged=True,migration_manifest_unchanged=sha(W/'config/package-manifest.json')==before['migration_manifest_sha256'],no_protected_deletion=True)
  save(D/'evidence/protection-after.json',protection)
  save(D/'cleanup.json',dict(status='PASS',owned_processes_remaining=leftovers,measurement_lock_available=True,lock_inode=os.fstat(lock.fileno()).st_ino,uid=os.getuid(),sudo=False,BPF=False,system_changes=False,environment=environment()))
 counts={'server_launch_attempts':len(list(D.glob('results/**/server/process.json'))),'confirmation':summary['counts'],'all_completed_response_generations':0,'all_completed_tokens':0,'smoke_completed_generations':0,'smoke_completed_tokens':0}
 for p in D.glob('results/**/server/*-responses.json'):
  rows=read(p);n=len(rows);t=sum(len(v['tokens']) for v in rows)
  counts['all_completed_response_generations']+=n;counts['all_completed_tokens']+=t
  if root not in p.parents:counts['smoke_completed_generations']+=n;counts['smoke_completed_tokens']+=t
 save(D/'evidence/execution-counts.json',counts)
 requirements=[]
 def audit(name,passed,evidence): requirements.append(dict(requirement=name,status='PASS' if passed else 'INCOMPLETE',evidence=evidence))
 audit('Immutable B0/A source/binary/model and prior evidence',protection['status']=='PASS' and protection['migration_manifest_unchanged'],'evidence/protection-after.json; identity.json; prior checkpoints; per-visit runtime.json')
 audit('Protocol/analysis/order frozen before first timing',all(sha(D/rel)==h for rel,h in read(D/'seal.json')['files'].items()),'seal.json; ledger.jsonl; preregistration revision2 before admission-v2; pre-smoke-v1 retained')
 audit('New harness four fresh-server smoke outputs/DSO/cleanup',read(D/'evidence/smoke-admission.json')['status']=='PASS','results/admission-v2')
 audit('Two full campaigns, 8 pairs each condition, no extra visits',state['status']=='COMPLETE' and len(state['completed'])==64 and all(c['completed_pairs']==8 for c in summary['cells']),'order.json; results/'+name+'/campaigns.json')
 audit('Within-cohort balanced arm orders',all(sum(1 for p in c['pairs'] if p['cohort']==f and p['arm_order'][0]==a)==2 for c in summary['cells'] for f in ['heldout-1','heldout-2'] for a in ['B0','A']),'order.json; analysis cell pairs')
 audit('All warmup/measured outputs exact and caches zero',len(summary['visits'])==64 and not summary['invalid_or_missing'],'analyze.validate_raw re-read response arrays/oracle/cache_n for all visits')
 audit('Controlled CPU load and E policy raw audit',all(.22<=v['measured']['background_cores']<=.28 for v in summary['visits'] if v['spec']['condition']=='cpu25'),'per-visit process/load counters and pressure logs')
 audit('Raw independent recalculation agrees',read(root/'independent-recalculation.json')['status']=='PASS','code/recalculate.py; results/'+name+'/independent-recalculation.json')
 audit('All expected timing count retained, no original/P/smoke inclusion',len(summary['visits'])==64 and all(v['spec']['campaign'] in [1,2] for v in summary['visits']),'code/analyze.py; results namespace; counts')
 audit('Protected payloads and owned process cleanup',not leftovers,'cleanup.json; evidence/protection-after.json')
 audit('Reproduction verify/analyze/smoke/full available',all(x in (D/'code/reproduce.py').read_text() for x in ["'verify'","'analyze'","'smoke'","'full'"]),'reproduce.sh; actually used for smoke/full/analyze; fresh names required')
 save(D/'completion-audit.json',dict(status='PASS' if all(x['status']=='PASS' for x in requirements) else 'INCOMPLETE',requirements=requirements,packaging='review-zip.json is checked separately after this report is packaged'))
 table=['| 캠페인 | 조건 | B0 tokens/s | A tokens/s | 평균 paired gain | 층화 bootstrap 95% | 빠른 pair | 목표 |','|---|---|---:|---:|---:|---|---:|---|']
 for c in summary['cells']:
  if not c['valid']:table.append(f'| {c["campaign"]} | {c["condition"]} | - | - | - | INCOMPLETE | - | 미완료 |');continue
  a=c['absolute'];lo,hi=c['paired_stratified_bootstrap_95_pct'];table.append(f'| {c["campaign"]} | {c["condition"]} | {a["B0"]["tokens_per_second"]:.4f} | {a["A"]["tokens_per_second"]:.4f} | {c["mean_paired_gain_pct"]:+.4f}% | [{lo:+.4f}%, {hi:+.4f}%] | {c["faster_pairs"]}/8 | {"PASS" if c["target_pass"] else "FAIL"} |')
 body=f'''# A/B0 직접 확인 결과

성과 상태: **{summary['status']}**. 작업 범위: 두 Linux-only 확인 캠페인, 분석·보존·재현 검사 및 검토 패키지. 이는 기존 원본 대비 런타임 전체 효과이며 kernel scheduler 단독 효과나 E worker 선택 단독 효과가 아니다.

{chr(10).join(table)}

Primary는 동일 atomic 8-prompt cohort의 실제 생성 1024 tokens / 전체 HTTP wall time이다. 위 절대값은 visit 처리량의 산술 평균이고 gain은 block별 A/B0 비율의 평균이므로 두 열의 평균 비율과 같다고 가정하지 않는다. 각 cell마다 paired block 8개, h1/h2 각 4개, cohort 안에서 각각 4개를 복원추출하는 층화 bootstrap 10,000회, seed 20261122, `(n-1)*p` 선형보간 95% percentile이다. 요청 8개를 독립 표본으로 세지 않았다. 네 cell 모두 mean>=5%, lower>0%, faster>=6/8일 때만 목표 충족이다. 평균 5%는 최소 5% 보장이 아니다. CI 하한까지 5% 이상인지도 JSON의 strong_evidence에 별도로 기록했다.

## 정체와 변경 범위

B0는 source `7a2db1a0cf38e5f4eb278a58c3903d295258d0ea`의 보존 재빌드다. 잃어버린 원본 binary와 byte identity는 주장하지 않는다. A는 기존 B1 overlay에 semantic Prefill Q4 기준 본문 fallback R을 적용한 연산 DSO와 기존 Prefill-pressure E 서버의 조합이다. Decode/Mixed exact Q4, Q6, phase bridge는 유지된 검증본이다. 이번에는 source/runtime/DSO/모델을 수정하거나 재빌드하지 않았다. donor pool P는 포함하지 않았다.

실제 경로·hash·inode는 identity.json, 기존 compiler/options/overlay 출처는 inputs/previous/identity-map.json과 R/A identity 및 checkpoint에 있다. actual argv/env와 loaded ELF는 각 server/runtime.json, ELF 별칭은 loaded-ELF-aliases.json에 있다. 모델 SHA256은 `{read(D/'protocol.json')['model_sha256']}`이다. 진단 R-diagnostic/P 라이브러리는 사용하지 않았다.

AMD Ryzen 5 5500U의 physical cores 6개에 대응하는 CPU [0,2,4,6,8,10], controller CPU11, OpenMP, threads5/batch6/http8, parallel8, context8192, batch512/ubatch256, CPU-only, FA on, no-kv-unified, speculation none이다. B0에 fork-only profile 옵션은 전달하지 않는다. A는 phase/pressure, Q4/Q6 phase_batch, Prefill attention off, repack huge, pool off를 유지한다. B0와 A의 실제 worker 선택 차이는 treatment 일부이며 동등한 CPU envelope를 유지했다. 환경 allowlist가 부모 LLAMA_ARG/LD_PRELOAD/OMP/GOMP/KMP 설정을 차단한다.

## 실행과 출력

두 cohort는 이전에 사용한 heldout-1/2라는 역사적 이름이며 새로운 미관측 입력이 아니다. 원문, numeric prompt 배열, seed424242, temperature0, nonstream, request당128tokens, ignore_eos, atomic 도착 방식은 그대로다. 모든 유효 warmup/측정 출력은 같은 fixture의 검증된 B0 oracle과 정확히 일치하고 timings.cache_n=0이다. 정상 요청 내부의 autoregressive KV는 유지한다. tokens_cached 필드를 재사용 판정 근거로 삼지 않았다. 새 logits/lifecycle 검사를 반복하지 않고 기존 R/A checkpoint의 모든 참조 hash를 다시 확인했다.

계획과 완료 수: `{json.dumps(counts,ensure_ascii=False)}`. 이전 546 generation이나 P/A pilot, 과거 correctness 시간은 이번 성능 표본에 넣지 않았다. 각 visit은 fresh server, 동일 한 warmup, 한 measured cohort, 정상 owned cleanup으로 이루어졌다. loading/warmup/identity/proc 검사는 primary clock 밖이며 정책 비용과 queueing/prefill/decode/응답 완료는 포함한다. TTFT는 NOT_MEASURED다.

cpu25 실측 CPU 소비 범위: **{summary['actual_cpu25_cores_range']} core**. CPU10, normal priority, 12.5ms CPU/50ms, 양 arm 동일 시작/0.5초 안정화/warmup/종료 규칙이다. 모든 per-arm window 값과 raw counter는 JSON에 있다. CPU seconds와 CPU seconds/token은 보조 자료이며 에너지 절감으로 해석하지 않는다. 온도/주파수/전원/governor와 E pressure 원시 epoch·선택·actual OpenMP teams도 실행별 보존했다. E의 정상 fallback/선택 변화는 결과에 포함하고 sensor 실패만 admission 위반으로 처리했다.

## 사전 등록과 실패 이력

두 campaign의 전체 순서·코드·분석은 timing 전에 seal.json으로 고정했다. 각 cohort 안에서도 arm 순서가 두 번씩 교차하며 campaign2는 condition과 arm 순서를 뒤집었다. 캠페인 사이 튜닝, pair 추가·교체, workload/metric 사후 선택은 없다.

첫 smoke admission-v1은 loaded library의 hardlink 별칭을 문자열로 비교한 runner 오류로 HTTP generation 이전에 중단했다. 기존 inode/hash 검증을 사용하도록 wrapper와 raw auditor를 수정했고 실패 기록 함수의 중복 timestamp도 고쳤다. battery Charging/Full 표시는 관찰값으로 남기고 실제 AC online/type은 고정했다. 원래 동결본은 registrations/pre-smoke-v1, 실패 raw는 results/admission-v1, 수정 명세는 evidence/pre-timing-amendment.json에 있다. 모델/runtime/workload 변경 및 소비된 timing은 0이었다. admission-v2의 네 fresh smoke를 완료한 뒤 확인 캠페인을 시작했다.

## 해석, 보존, 재현

이번 결과의 적용 범위는 같은 AMD 장비, 같은 두 distinct cohort, parallel8, 지정 입력/출력 길이와 ambient/cpu25다. 두 독립 실행 캠페인은 다른 CPU나 새로운 workload의 일반화를 뜻하지 않는다. 모든 모델/shape/ISA, 의미적 답변 품질, 단일 chat 속도, 에너지, Intel 효과는 검증하지 않았다. A-fixed6 ablation과 연구용 kernel scheduler 비교도 수행하지 않았다. E의 독립 기여는 **not-isolated**다. 원 프로젝트의 scheduler 포함 최종 구성 검증을 이 Linux-only 비교로 대체하지 않는다.

검증된 보호 파일 {protection['protected_workspace_files']}개와 원래 외부 파일 {protection['outside_original_files']}개, 모델 inode/hash를 유지했다. 기존 archive/실험/ZIP을 수정하지 않았고 sudo/BPF/전역 설정 변경/Git commit/push를 하지 않았다. cleanup.json에서 자신이 시작한 server/load 종료와 measurement lock을 확인했다.

```bash
cd {D}
./reproduce.sh verify
./reproduce.sh analyze --name {name}
./reproduce.sh smoke --name my-new-smoke
./reproduce.sh full --name my-new-confirmation
```

full은 사전 정의된 두 캠페인 모두를 새 namespace에 실행하며 기존 이름을 덮어쓰지 않는다. 원시 재계산은 analyze.py가 응답/clock/counter/pressure를 직접 검증하고 recalculate.py가 별도 산술 경로로 gain/CI를 재계산한다. review ZIP은 source/input/raw/분석/문서 중심이며 모델, runtime, object/archive 복제본을 포함하지 않는다. 내부 및 sidecar에서 동일한 `REVIEW_MANIFEST.json` 이름을 사용한다. ZIP 크기와 SHA256은 review-zip.json에 기록한다.

종료 사유: 이번 고정 비교 범위 완료(완결성 감사는 completion-audit.json과 ZIP 검사 결과 참조). 새 최적화·정책 탐색은 수행하지 않는다.
'''
 (D/'direct-comparison-summary.md').write_text(body)
 (D/'README.md').write_text('# A/B0 직접 비교\n\n결과: direct-comparison-summary.md/json. 사전 명세: protocol.json, order.json, seal.json. 원본 runtime 변경 patch 없음. 실제 실행에는 기존 통합 workspace와 original model이 필요하다. 검토 ZIP은 실행용 전체 복제본이 아니다.\n\n일반 계정에서 ./reproduce.sh verify, ./reproduce.sh analyze --name '+name+', ./reproduce.sh smoke --name NEW, ./reproduce.sh full --name NEW. sudo 불필요.\n')
 (D/'GOAL_STATE.md').write_text('# A/B0 direct confirmation\n\nMeasurement status: '+state['status']+'; scientific status: '+summary['status']+'.\nLast block: campaign2 ambient block8, subject to full plan audit.\nSeal SHA256: '+sha(D/'seal.json')+'\nRaw: results/'+name+'; report: direct-comparison-summary.md.\nNext command: ./reproduce.sh verify; ./reproduce.sh analyze --name '+name+'\nStop reason: fixed scope completed, no optimization/tuning authorized. Packaging evidence: review-zip.json; completion-audit.json.\n')
 event('report-and-protection-complete',run=name,status=summary['status'],protected_files=len(before['files']))
 print(json.dumps(dict(status=summary['status'],audit=read(D/'completion-audit.json')['status'],counts=counts),indent=2))
def read_gzip(p):
 with gzip.open(p,'rt') as f:return json.load(f)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--name',required=True);main(p.parse_args().name)
