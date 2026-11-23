"""Render paths, diagrams and tables from audited evidence."""
import collections,json
from pathlib import Path
D=Path(__file__).resolve().parents[1];W=D.parents[1]
def read(p):return json.loads((D/p).read_text())
anchors={x['id']:x for x in read('evidence/source-anchors.json')}
def loc(group,key):
 x=anchors[group];a=next(a for a in x['anchors'] if a['name']==key)
 return f"`{str(Path(x['path']).relative_to(W))}:{a['line']}` ({key}); SHA256 `{x['sha256']}`; [source]({x['excerpt']})"
edges=[
 ('L1','token origin → actual view semantic classifier','semantic-origin','classification','semantic-origin','retry-view','원래 decode-origin541/prompt-origin3615; split3902. 실제 epoch phase counts. Mixed는 token origin이 아니라 view의 합성 판정.'),
 ('L2','semantic phase → E select','semantic-origin','profile-selection','E','select','observed-usage measured epoch: phase, task/position guard, sample validity, actual choice.'),
 ('L3','E choice → options/API','E','select','semantic-origin','decode-api','A server ELF unresolved llama_decode_with_options + libllama export; raw decisions5/6.'),
 ('L4','decode API → graph compute/profile resolve','profile-engine','api','profile-engine','graph','base59와 final llama-context byte identity; archived compile/link + loaded libllama dcd9ba…; graph 호출마다 직접 tracing한 것은 아님.'),
 ('L5','graph profile → CPU setter/OpenMP','profile-engine','threads-setter','CPU-graph','team','CPU setter256, registry655; 실제 libgomp NEED + team 보고. pool setter2471은 off여도 thread setter를 막지 않음.'),
 ('L6','semantic phase → transition scalar','semantic-origin','transition','phase-classifier','transition-state','HINT define/TRACE 미정의; 최종 server에 llama_scx_phase_v1 export. 동일 phase 재방출 생략.'),
 ('L7','scalar → registry/CPU phase setter','phase-bridge','setter-lookup','CPU-registry','registry','CPU phase setter481과 registry653. ELF export 및 별도 R route 진단으로 경로 사용 확인.'),
 ('L8','CPU phase → Q4 eligibility','CPU-graph','phase-setter','Q4-R','eligibility','R 진단 reference Prefill3935, exact Decode167201/Mixed2656. final timing 자체의 per-call trace는 없음.'),
 ('L9','CPU phase → Q6 graph phase/eligibility','CPU-graph','phase-load','Q6-policy','phase','R 진단 Q6 worker0 chunks Prefill15739/Decode462873/Mixed14003.'),
 ('S1','scalar marker ELF → selected uprobe','phase-bridge','marker','scheduler-lifecycle','uprobe','동결 marker ELF9204b0…; selected-child registration/loaded BPF identity. 기존 runtime/scheduler raw.'),
 ('S2','uprobe → observed phase state/counters','scheduler','uprobe','scheduler','handoff','phase_seen bitmap14; Decode attempt 누적. NEW_A_IDLE_HANDOFF 미정의, moved0.'),
 ('S3','selected worker → scheduler callbacks','selected-child','policy','scheduler','select','selected server/workers policy7 + fixed mask, 일반 launcher/load policy0; partial struct_ops 연결.'),
 ('S4','frozen topology → idle CPU tier','scheduler-loader','topology','scheduler','tier','각 loader log enabled1 tiers6/0/0; frozen topology identity; phase 입력 없이 idle/allowed/online 검사.'),
 ('S5','idle select / enqueue → local/shared DSQ','scheduler','select','scheduler','enqueue','tier/fallback selected counters, running/stopping; idle local DSQ, otherwise shared vtime queue.'),
 ('S6','shared DSQ → dispatch / weighted vtime','scheduler','dispatch','scheduler','weight','DSQ callbacks 소스와 FULL counters; used slice*100/weight, Linux scx_simple 공통 기반.'),
]
md='''# 최종 source-to-runtime 통합 경로

각 화살표의 L/S 번호는 아래 표의 **원본 경로:행번호·전체 SHA256·실행 증거**에 대응한다. 선택 source 발췌의 행번호도 원본 기준이다. “실행 증거”는 source, build, loaded ELF, epoch/진단을 결합한 근거이며 모든 함수에 연속 tracing을 했다는 뜻은 아니다.

## A_L: Linux에서의 runtime 연결

텍스트 경로: token-origin → 실제 제출 view의 semantic phase → E의 Prefill 관측/Decode 선택 → explicit profile → libllama graph → CPU setter/OpenMP. 별도 가지는 같은 semantic phase → transition scalar → CPU backend phase setter → Q4/Q6 eligibility다. kernel scheduler가 없어도 두 runtime 가지는 동작한다.

```mermaid
flowchart TD
 T["token origin / actual batch view"] -->|L1| P["semantic phase"]
 P -->|L2| E["E: Prefill sample / eligible Decode choice"]
 E -->|L3| A["options / llama_decode_with_options"]
 A -->|L4| G["libllama graph_compute / profile"]
 G -->|L5| O["CPU setter / OpenMP 5 or 6"]
 P -->|L6| H["transition scalar HINT"]
 H -->|L7| C["CPU phase setter"]
 C -->|L8| Q4["R Q4 eligibility"]
 C -->|L9| Q6["Q6 graph phase / eligibility"]
```

## A_S: 동일 runtime과 kernel 실행·관측

텍스트 경로: A_L의 L1~L9를 그대로 사용한다. scalar marker를 selected uprobe가 받아 관측 state/bitmap/counter에 기록한다. 별도로 선택 child만 SCHED_EXT에 들어가 frozen topology, idle tier, local/shared DSQ, weighted-vtime 정책으로 실행된다. phase 관측에서 placement로 가는 화살표나 kernel→E feedback 화살표는 없다.

```mermaid
flowchart TD
 T["token origin / actual batch view"] -->|L1| P["semantic phase"]
 P -->|L2| E["E resource choice"]
 E -->|L3| A["explicit profile API"]
 A -->|L4| G["libllama graph"]
 G -->|L5| O["CPU / OpenMP workers"]
 P -->|L6| H["scalar HINT"]
 H -->|L7| C["CPU phase setter"]
 C -->|L8| Q4["R Q4 eligibility"]
 C -->|L9| Q6["Q6 eligibility"]
 H -->|S1| U["selected uprobe"]
 U -->|S2| V["observed phase / counters"]
 CHILD["selected child and workers"] -->|S3| SELECT["phase-independent idle selection"]
 TOPO["frozen topology 6/0/0"] -->|S4| SELECT
 SELECT -->|S5| QUEUE["local or shared DSQ"]
 QUEUE -->|S6| DISPATCH["dispatch / weighted vtime"]
```

## 화살표별 근거

'''
for eid,name,g1,k1,g2,k2,evidence in edges:
 md+=f'### {eid}: {name}\n\n- 출발: {loc(g1,k1)}\n- 도착: {loc(g2,k2)}\n- 실행 연결: {evidence}\n\n'
md+='''## 실행 의미와 안전 경계

`server_batch::token`은 slot/task/position과 Prefill/Decode origin을 보유한다. `off .. off+batch_view.n_tokens`를 집계하므로 논리 batch 전체가 아니라 이번 제출 view를 판별한다. split/retry는 새 view로 다시 호출한다. n_unknown이 있으면 Unknown, 두 origin이 있으면 Mixed다. AUTO의 physical ubatch token-count 선택과 semantic phase 선택은 별개다.

E는 선택 CPU의 `/proc/stat` user/nice/system 증가량에서 process CPU upper bound와 tick rounding을 보정하고 0.02 core margin을 뺀 score를 0.125와 비교한다. 순수 Prefill >=32 tokens, model call >=1초, counter read <=20ms가 필요하다. 첫 Decode의 표본 age<=10초, 8-task/slot/seq/position 연속성, 이후 active subset tail, 최대256 eligible calls 조건을 검증한다. 적격 multi-token Decode만 pressure/fixed6 차이가 생기고 single-token Decode는5, Unknown/Mixed와 보수적 fallback은6이다. 실패 결과는 proposed epoch에 commit하지 않고 idle/reset한다. E idle reset은 scalar last-emitted phase에 v2 idle 이벤트를 추가하는 것이 아니다.

E의 센서는 매 Decode 재측정하지 않는다. source에 ambient/cpu25 조건명이나 답변 token 내용으로 선택하는 경로가 없다. [bounded search](evidence/feedback-search.json)의 대상은 server/context, E helper, scalar bridge, libllama context, CPU C/C++와 정적 ELF dependency다. 결과는 NOT_FOUND_IN_SCOPE이지 모든 파일·미래 구현의 부재 증명은 아니다.

R Q4는 semantic Prefill에서 false를 반환해 기준 body로 간다. Decode/Mixed exact tile은 phase_batch와 원래의 shape 경계를 만족할 때 유지된다. Q6는 graph 시작 시 CPU phase를 읽는다. HINT는 kernel uprobe 외에도 이 eligibility를 전달하므로 HINT OFF 비교는 순수 scheduler off가 아니다. final HINT ON/TRACE OFF에서는 80-byte begin/end TRACE와 worker 진단 경로가 활성화되지 않는다. v2의 32-byte active/idle ABI와 혼동하지 않는다.

observe는 FULL 진단에서 phase를 읽고 attempt를 셀 수 있지만 이동 분기는 compile되지 않았다. `FG_GUARD` macro가 없더라도 selected-child/fixed-affinity loader monitor는 실제 활성이다. dynamic-affinity 문제를 해결했다고 주장하지 않는다. tier6/0/0은 AMD에서 여섯 physical CPU를 하나의 tier에 넣은 구성으로 Intel P/E 성과가 아니다.

## source → build → binary → loaded chain

| 부분 | source/build 근거 | 실제 binary/loaded 연결 |
|---|---|---|
| B0 | historical commit7a2db1a0, 보존 rebuild identity | cases의 B0 server32a3cc…/CPU927db1…/libllama4bf5f8…와 raw loaded 기록 |
| shared libllama | base59의 llama-context/header가 final과 byte-identical; archived compile_commands, link.txt/flags.make | libllama dcd9ba… 유지. prefill-attention overlay가 다른 graph 파일에 있으므로 전체 libllama가 base59 무수정이라는 뜻은 아님 |
| E server | 보존 pressure identity에 context85a965…/helper944b2b…/bridge655e62…, HINT compile/link 및 parent relink identity | server-impl9204b0… 그대로 A/F6/S에 로드; API symbol과 scalar marker 확인 |
| R CPU | pre-R CPU compilation/header input match, archived O3/native/OpenMP options + R policy014ec3… | CPU45ddfa…를 A/F6/S가 로드; diag variant의 별도 route proof를 timing으로 쓰지 않음 |
| scheduler | 보존 observe compile.log의 FULL defines, workspace loader 재링크 기록과 source identities | loaderbb3e08…/BPFcb63e7…/childac4d0b…와 실제 A_S raw attachment/정리 |
| P | donor header61a61c… + P context378d0f… + padding patch; full server link/parent byte-identical relink | P server250671…와 A server9204b0…는 다름. arithmetic DSO는 동일; P lifecycle만 donor owner 사용 |

전체 hash는 [release map](evidence/preserved/a-component-scheduler-replication-v1/frozen-release-map.json), [static ELF](evidence/static-elf.json), [314개 source/artifact/loaded 재확인](evidence/identity-recheck.json)에 있다. 정적 symbol은 포함 증거이고, raw loaded/epoch/route/lifecycle 자료가 실행 근거를 보강한다. `nm`에서 함수가 없다는 한 가지 사실만으로 donor 부재를 판정하지 않고, source와 compile identity도 대조했다.

단일 폴더에는 여러 역사적 overlay/DSO가 모여 있다. `src/llama`의 Q4 policy는 pre-R이므로 R 설명에 그 파일을 대신 쓰지 않았다. R overlay 경로를 사용했다. 최신 HEAD를 과거 measured source로 대체하지 않았다. clean 단일 commit 재빌드는 이번 감사에서 하지 않았고 가능 여부를 확정하지 않는다.
'''
(D/'runtime-integration-map.md').write_text(md+'\n추가 attachment/tag 증거: [36개 기존 visit 재확인](evidence/scheduler-attachments.json). 새 sudo/BPF 실행 없음.\n')
perf=read('evidence/performance-recalculation.json');data=read('evidence/performance-blocks.json');usage=read('observed-usage.json')
md='''# 기존 성능의 직접 재계산과 기여 해석

이번 감사의 새 성능 측정은0회다. 원본 attribution과 후속 replication을 각각 유지했다. `code/collect_usage.py`는 기존 read-only recalculate.py로 실제 token array·oracle·prompt count/cache_n·seed·worker policy/affinity·background load·planned order·완결 block을 확인했다. 두 캠페인 각각128 raw cohorts(warmup64+measured64),10 comparisons가 PASS다. 작은 검토 패키지의 timestamp/token-count 발췌는 `python3 -B code/recalculate_packaged.py`로 다시 계산할 수 있다.

## 고정된 지표와 범위

primary는 실제 generated tokens / cohort HTTP 전체 wall seconds다. atomic 8 distinct prompt 배열, 요청당128, cohort당1024 tokens. queueing/prefill/decode/policy/응답 완료를 포함하고, loading과 fresh server당 warmup 한 cohort를 제외한다. 비stream 응답이라 별도 TTFT를 측정하지 않았다. 두 fixture는 historical heldout-1/2이며 새 unseen population 검증이 아니다.

각 캠페인은4 arms ×2조건 ×8blocks =64 timed visits. 각 조건에서 cohort당4 blocks, 순서 균형 교차, 장비 내 직렬 실행이었다. gain_i=100*(candidate_tps_i/baseline_tps_i-1), 표에는 그8개 비율의 산술평균을 쓴다. 10,000회 cohort-stratified paired-block bootstrap, seed20261122, 선형 percentile95% CI다. 요청8개를 독립 n=8로 세지 않는다. 서로 다른 campaign을 합치거나 개선율을 더하지 않는다.

같은 AMD Ryzen5 5500U, 같은 model hash, CPU0,2,4,6,8,10, controller11, threads5/batch6, OpenMP, GPU0/specnone. CPU25는 CPU10에서 약0.25 core이며 장비 전체25%가 아니다. 실제 부하는 original0.251161~0.252916, replication0.250549~0.252892 core. 모든 arm의 measured 부하가 보존된0.22~0.28 범위였다.

## 절대 성능

아래 t/s는8 cohort t/s의 산술평균이다. 평균 t/s의 비율은 아래 primary mean paired gain과 같은 집계가 아니다.

| 캠페인 | 조건 | arm | mean t/s | mean cohort wall s |
|---|---|---|---:|---:|
'''
for x in data['absolute']:md+=f"| {x['campaign']} | {x['condition']} | {x['arm']} | {x['mean_tps']:.4f} | {x['cohort_wall_mean_s']:.4f} |\n"
md+='\n## 각 캠페인의 다섯 직접 비교\n\n| 캠페인 | 조건 | 비교 | mean paired gain % | bootstrap95% CI % | faster/8 |\n|---|---|---|---:|---|---:|\n'
for campaign in perf['component_campaigns']:
 for x in campaign['result']['contrasts']:md+=f"| {campaign['campaign']} | {x['condition']} | {x['contrast']} | {x['mean']:+.6f} | [{x['ci'][0]:+.6f}, {x['ci'][1]:+.6f}] | {x['faster']}/8 |\n"
md+='''
전체 A_L/B0와 A_S/B0는 두 campaign·두 조건에서 mean>=5%, CI lower>0, faster>=75%를 통과한다. 이 범위에서 lower도5% 이상인 더 강한 증거다. 이를 모든 장비/요청에서 최소5% 보장으로 표현하지 않는다. 기존 scoped system 판정을 재확인한 것이고, 새로운 kernel 우위 판정이 아니다.

F6/B0는 E의 적응 선택을 제외한 runtime 묶음 효과다. F6에도 센서·guard·phase 전달·검증된 연산 경로가 남아 있으므로 Q4 단독 효과나 phase 전체 제거 비교가 아니다. A/F6 CPU25는 fixed6 대비5-worker 선택 효과가 두 번 positive다. ambient는 실제 선택이 같고 두 CI가0을 포함한다. phase label 자체의 고유 가치는 NOT_ISOLATED다.

A_S/A_L는 FULL 관측 비용까지 포함한 scheduler 구성의 순효과다. original 양 조건은 inconclusive, replication ambient는 positive, CPU25는 negative다. 계측 비용을 가정해 빼거나 “scheduler가 불필요하므로 모든 kernel 정책의 가능성도0”으로 확대하지 않는다. fixed6_S가 없어 E×scheduler 상승효과의 완전한 분해는 불가능하다.

## E 사용량: measured와 warmup/기능검사 분리

다음은 measured 정책 select 호출이다. B0에는 E epoch 계측이 없으므로 표의0을 “Decode가0”으로 해석하지 않는다. 전체 graph/physical ubatch 분모는 관측되지 않아 JSON에서null이다. 각 선택이 내부 여러 graph를 포함할 수 있다.

| 캠페인 | 조건 | arm | select calls | all Decode 5/6 | eligible multi 5/6 | Prefill6 / Mixed6 |
|---|---|---|---:|---|---|---|
'''
for x in usage['groups']:
 if x['stage']=='performance' and x['window']=='measured' and x['arm']!='B0_L':
  md+=f"| {x['campaign']} | {x['condition']} | {x['arm']} | {x['calls']} | {x['all_decode_5_6']} | {x['eligible_multi_5_6']} | {x['decisions_by_phase_5_6'][1][1]} / {x['decisions_by_phase_5_6'][3][1]} |\n"
md+='''
각 measured arm/조건의1,016 eligible multi calls는8cohorts×127calls이며 tokens가 아니다. 이 raw에서는 각 cohort가8-token eligible126calls와4-token tail1call로 끝난다. warmup, functional-check, measured는 [observed-usage.json](observed-usage.json)의48개 group에 따로 기록돼 있다. 총144visits는 timed128 + Linux smoke12 + scheduler admission4이며, 각 visit의 warmup을 성능 반복수로 더하지 않았다. libgomp affinity-format `NEWA_TEAM`은 변화 시점의 team 보고로 전체 graph 계수가 아니다.

## Scheduler 사용량: whole-visit 통계

| 캠페인 | 단계 | 조건 | visits | tier0 / tier1 / tier2 / fallback | Decode attempts | moved |
|---|---|---|---:|---|---:|---:|
'''
for x in read('evidence/scheduler-aggregate.json'):md+=f"| {x['campaign']} | {x['stage']} | {x['condition']} | {x['visits']} | {x['select_tiers']} | {x['handoff_attempts'][2]} | {sum(x['handoff_moved'])} |\n"
md+='''
이는 warmup/startup/teardown을 포함한 서버 수명 전체의 callback/attempt 계수다. timed visit으로 묶었다고 measured-only delta가 되는 것은 아니다. phase_seen14는 Prefill/Decode/Mixed를 관측한 비트마스크이며14회 이벤트가 아니다. phase event count는null이다. topology6/0/0에서 tier1/2가0인 것은 Intel E/SMT 정책 성과가 아니다. 모든36 A_S visit의 mask/tracking/event-drop 검사 오류는0이고 live monitor는 PASS다.

## Pool P/A: 독립 n4 pilot

| 조건 | mean paired gain % | bootstrap95% CI % | faster/4 |
|---|---:|---|---:|
'''
for x in perf['pool_pilot']:md+=f"| {x['condition']} | {x['mean']:+.6f} | [{x['ci'][0]:+.6f}, {x['ci'][1]:+.6f}] | {x['faster']}/4 |\n"
md+='''
P/A는 별도 n4 pilot이며 full confirmation이 아니다. E actual choice는 pair 간 동일했다. P steady512 graphs 모두 persistent attached, A512는 disposable이며 P creation/free 각6회는 초기화와 두 resume/teardown을 포함한다. OpenMP에서 GGML pool allocation과 OS worker creation/parking은 다르다. 따라서 pool이 최종 gain에 기여했다고 말하지 않으며, 결과 방향이 엇갈려 TESTED_NOT_ADOPTED로 남긴다.

## R 경로와 정확성 진단은 timing과 별개

진단 한 서버 수명에서 reference Q4 body의 phase[Unknown,Prefill,Decode,Mixed] 계수는[0,3935,0,2628], retained exact Q4 worker0 calls는[0,0,167201,2656], Q6 worker0 chunks는[0,15739,462873,14003]이다. 서로 다른 단위이며 합쳐 graph 수나 사용 비율을 만들지 않는다. timing과 무거운 route/numeric/lifecycle 진단은 분리돼 있다.

R free-generation과 제한 logits/observer의 후속 PASS는 보존 build identity의 초기 NOT_MODEL_VALIDATED를 소급 변경하지 않는다. 초기 P guard 실패, observer-v1 실패도 보존돼 있다. 일반 품질 동등성은 검증하지 않았다.

## 캠페인간 변동과 금지하는 기여 계산

이전 runtime-only A/B0 CPU25의 B0 약41.08/40.99t/s와 달리 component original은38.68, replication39.96이었다. A는 각각 약51t/s였다. 그 변동 원인은 CAUSE_UNDETERMINED다. runtime 변경이 없으므로 상대 gain이26%에서32%로 커진 것을 새 코드 개선이라고 쓰지 않는다. 유효한 느린 B0 block도 모두 포함했다.

개별 Q4/Q6/API/HINT/메모리, 개인별 몫은 NOT_ISOLATED다. fixed5 대비, phase label만의 효과, fixed6_S interaction도 없다. gain을 더해 전체 성과를 만들지 않았고 단순 캠페인간 평균 비율을 paired gain으로 바꾸지 않았다.
'''
(D/'performance-attribution.md').write_text(md)
print(json.dumps(dict(status='PASS',edges=len(edges),performance_comparisons=20)))
