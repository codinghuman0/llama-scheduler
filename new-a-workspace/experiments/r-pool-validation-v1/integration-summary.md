# R / E / persistent pool 통합 검증

작성 시각: 2026-11-22T08:39:07.234463+00:00

| 구분 | 최종 상태 |
|---|---|
| R | COMPATIBLE_IN_TESTED_SCOPE |
| E-R | COMPATIBLE_IN_TESTED_SCOPE |
| Pool integration | MODEL_VALIDATED |
| Pool pilot | REGRESSION |
| Adoption | REJECT_OR_HOLD |

기능 검증된 R/A를 보존했다. P는 준비된 이식본의 null-padding 호환성 검사만 보완한 revision이다. 이번 작업은 모델·입력·출력·E threshold·연산 커널의 추가 최적화를 하지 않았다. 제한 pilot의 판정은 REGRESSION이며, 원본 대비 5% 성능 목표나 과거 18~22% 결과를 승계하지 않는다. 종료 사유는 이 goal에 정한 단계·고정 pilot·패키징 완료이며, sudo 제약이나 외부 R 작업 대기가 아니다.

## 구성과 이번 변경

- B0: 7a2db1a0cf38e5f4eb278a58c3903d295258d0ea 역사적 원본의 동결 재빌드. 원본 바이너리 그 자체라는 뜻이 아니다.
- B1: 기존 검증 overlay/DSO 조합. E는 기존 Prefill-pressure server/helper이다.
- R: B1의 semantic PREFILL에서만 `newa_q4_try()`가 false를 반환하여 원래 Q4 본문을 실행한다. 적격 Decode/Mixed exact Q4, Q6 phase_batch, scalar phase 연결은 유지했다.
- A: 검증된 R 연산 라이브러리 + byte-identical 기존 E server, donor pool off.
- P: A + 준비된 donor generation5/batch6 소유권·연결·해제 이식 + null-padding guard 호환성 수정. P의 산술 DSO는 A와 동일하다.

AMD Ryzen 5 5500U, Linux 기본 스케줄러, CPU envelope 0,2,4,6,8,10, OpenMP, generation5/batch6, poll50, normal priority, 역할별 mask 없음. HINT ON / TRACE OFF. 기존 HINT OFF `newa_resource` 미선언 build limitation은 남아 있으며 전체 matrix PASS라고 하지 않는다. Intel은 검증하지 않았다.

현재 경로·source pin·전체 hashes는 `identity-map.json`에 있다. 실제 loaded DSO와 model mapping은 각 실행의 `runtime.json`, `model-identity.json`에 있다. 모델 SHA256은 `f3bdf9cf31dee4b57ae4e455a1cb0d01b5c2c1b50d72d3112141c195506c2840`이다.

## R 수치 호환 gate

두 atomic 8-prompt cohort와 진단 singleton(h1 request3, 109 입력 tokens), 기존 pool singleton(single-short, 132)을 서로 구분했다. 각 fixture에서 B0/R/R/B0 순서의 fresh server 4회, 각 warmup/본 실행을 수행했다. 총 16 fresh server, 144 완료 HTTP generation에서 동일 fixture의 B0 token과 정확히 일치했고 runtime 내부 반복도 일치했다.

별도 observer 4 fresh server에서 h1 target request3와 h1 singleton 각각 g0~g3, 총 8 logits checkpoint를 비교했다. 전체 요청 history, batch/physical ubatch, seq/position, 실제 worker profile이 같았다. 모든 logits가 finite, argmax 동일, maxabs=0, byte equality PASS이다. Teacher forcing은 0회다. 일반 답변 품질·모든 shape/모델/ISA의 동등성 증명은 아니다.

실제 모델의 별도 route 진단은 Prefill 기준 Q4 본문 3,935회 호출을 양성 증거로 확인했다. Decode/Mixed exact Q4와 Q6 호출도 양수였다. 작은 분리 probe는 UNKNOWN/PREFILL/DECODE/MIXED의 eligible/guarded routing을 검사했다. candidate counter가 0이라는 것만으로 fallback 실행을 주장하지 않았다. 진단 시간은 성능 표본이 아니다. 증거: `evidence/R-checkpoint.json`, `evidence/R-numeric-summary.json`, `evidence/R-route-summary.json`.

## E 연결, 서버 링크와 실제 lifecycle

A와 수정 P 각각 두 8요청 cohort와 두 singleton을 fresh server에서 warmup/본 실행했다. 모든 출력은 R/B0 oracle과 같았다. P 전체 server DSO를 실제 링크했으며, 변경 없는 E parent를 먼저 재링크한 결과가 frozen E와 byte 단위로 같았다. 실제 R DSO에서 ownership/ABI, 5/6 graph 재사용, abort recovery, phase/chunk 초기화 단위 검사를 다시 통과했다. 과거 B1 DSO 단위 결과만 재사용한 것이 아니다.

실제 모델에서 cancellation 후 정상 요청, 잘못된 grammar가 발생시키는 sampler 예외와 복구, 모델 unmap을 확인한 sleep/resume 2회, 이후 exact output, 정상 종료와 파일 부재 load-error cleanup을 검사했다. observer v2 기준 A/P 모두 PASS이다. load-error 검사는 모델 할당 전 오류 경로이며, 로딩된 모델의 예외·복구·해제는 별도 lifecycle 검사에서 확인했다.

| steady-state 진단 | A | P |
|---|---:|---:|
| 검사 graph | 512 | 512 |
| disposable pool graph | 512 | 0 |
| persistent API 생성/해제 (초기+resume 2회) | 0/0 | 6/6 |

P의 startup/common warmup과 resume 초기 graph의 disposable pool은 steady-state와 구분했다. 연결된 generation5/batch6 pool을 실제로 재사용했고, 각 sleep 때 2개, 최종 종료 때 2개가 해제됐다. OpenMP pause/resume은 native pthread 대기/깨우기 제어가 아니며, GGML pool과 OS worker 생성을 혼동하지 않는다. 증거: `evidence/AP-functional-checkpoint.json`, `evidence/AP-lifecycle-summary.json`.

## 보존한 실패와 보완

1. 원래 준비된 P는 model load/warmup 뒤 초기 설정 guard에서 거부됐다. 실제 parser는 override 미지정 상태에서도 null 항목 4,096개를 채우므로 `.empty()`가 잘못된 판정이었다. 원본 P와 실패 raw를 보존했다. `P-padding-compatibility.patch`는 실제 pattern/buft가 하나라도 있는 경우만 거부하도록 바꾼 최소 연결 수정이다. 실제 override가 계속 거부됨을 실제 parser로 검사했다. 모델·요청·E 정책·pool 설정은 바꾸지 않았다.
2. observer v1은 헤더에 선언만 있고 실제 R DSO에는 없는 `ggml_threadpool_get_n_threads` 조회 때문에 P 진단에서 abort했다. 일반 P 모델 실행과 분리한 계측 실패다. 후보 DSO는 바꾸지 않고 observer v2가 지원되는 new/free/graph API와 생성 인자만 관측하도록 수정했다. 원래 실패를 남기고 A/P lifecycle을 새 suffix로 반복했다.
3. 빌드 후 헤더 검사는 통합 workspace의 pressure header에 대한 과거 경로 alias 하나가 빠져 일시 중단됐다. 내용 hash 일치를 확인해 대응만 보완했으며, 이를 이유로 runtime을 다시 바꾸지 않았다.

모든 이력은 `ledger.jsonl`, `gate-results.json`의 attempts 및 해당 실패 디렉터리에 있다. 실패를 성능 표본으로 대체하거나 숨기지 않았다.

## 사전 고정 P/A pilot

primary = 실제 완료한 generated tokens / cohort 전체 HTTP wall time. 각 cohort는 동일한 atomic 8-prompt 요청, 요청당 128 tokens, cache_prompt=false이며 실제 cache_n=0을 확인했다. 모델 로딩과 동일 warmup은 양 arm에서 제외했다. ambient와 cpu25 각각 정확히 4 paired blocks, A/P-P/A-A/P-P/A, h1-h2-h1-h2. 총 8 pairs, 16 측정 cohort, 추가 pair 0. 빌드·무거운 observer는 timing과 분리했다.

| 조건 | A tokens/s | P tokens/s | 평균 paired gain | paired bootstrap 95% | 빠른 pair |
|---|---:|---:|---:|---|---:|
| ambient | 57.9401 | 56.9675 | -1.6546% | [-3.304312%, -0.004986%] | 1/4 |
| cpu25 | 51.5319 | 52.0724 | +1.0511% | [+0.177626%, +2.266769%] | 3/4 |

| 조건 | A wall s | P wall s | A CPU s | P CPU s |
|---|---:|---:|---:|---:|
| ambient | 17.6773 | 17.9757 | 105.7275 | 107.5275 |
| cpu25 | 19.8718 | 19.6669 | 104.0850 | 103.0750 |

신뢰구간은 paired block 단위 bootstrap 10,000회, seed 20261122, percentile 95%다. n=4의 제한 pilot이며 독립 confirmation이나 동등성 증명이 아니다. 상한이 0에 매우 가까운 경우 부호를 반올림해 숨기지 않도록 6자리로 표시했다. 모든 계획 pair의 원시값과 유효성은 `results/pilot-v1/analysis.json`에 있다. CPU seconds는 에너지가 아니다. nonstream 프로토콜을 유지했으므로 별도 TTFT는 측정하지 않았다.

cpu25는 기존 일반 계정 generator의 12.5ms process CPU / 50ms period, CPU10을 유지했다. 실제 측정 범위는 0.251769~0.252945 core다. 허용 범위는 사전 고정한 0.22~0.28이다. E raw pressure/worker 선택을 재계산했다. A/P worker 선택이 다른 pair: `[]`. 선택이 다른 경우 E+pool 통합 효과로 해석하며 순수 allocation 감소로 단정하지 않는다. 이번 goal은 E-off ablation을 수행하지 않아 E의 독립 기여를 새로 입증하지 않는다.

프로토콜 변경은 `protocol-changes.md`와 `protocol-AP-padding-amendment.json`에 먼저 기록했다. 이전 미실행 초안의 개별 동시 요청 설명은 보존된 실제 실험의 atomic 도착 방식에 맞췄다. 고정된 metric·반복 수·판정 기준은 timing 중 바꾸지 않았다. B0 correctness 시간을 B0 성능 비교로 승격하지 않았다.

## 실행 수, 보존과 재현

총 server 시작 시도 54회, 완료 HTTP generation 546개 / 69888 tokens다. 여기에는 warmup·진단·독립 script smoke가 포함된다. 취소 stream 3개(수신 tokens 24, 서버의 추가 계산 token 수는 단정하지 않음), 예상 grammar HTTP400 3회는 별도다. 내부 empty graph warmup을 HTTP generation 수로 세지 않았다. 상세 계산은 `evidence/execution-counts.json`에 있다.

`evidence/protection-after.json`과 `cleanup.json`에서 최신 migration manifest 기준 B0/B1/E·원본 source/model·archive·이전 prepared pool 파일 보존, ordinary UID, 기본 Linux, measurement lock과 owned process 정리를 확인했다. sudo/BPF/시스템 설정 변경/Git push는 하지 않았다.

```bash
cd /home/codinghuman/projects/new-a-workspace/experiments/r-pool-validation-v1
./reproduce.sh verify
./reproduce.sh smoke             # 새 correctness 실행, 성능 pair 아님
./reproduce.sh pilot --campaign my-independent-pilot
./reproduce.sh build-r           # 별도 sibling 디렉터리에 CPU 최소 재빌드
./reproduce.sh build-p           # 검증 R/A를 재사용하고 server 최소 재빌드
```

빌드·명령 manifest: `build-cpu/commands.json`, `build-server/commands.json`, `results/pool-padding-fix/commands.json`. 분리 patch는 `patches/`에 있다. 검토 ZIP은 source/patch/protocol/핵심 raw/results 중심이며 모델 가중치·전체 runtime·object/archive 빌드 복사본을 제외한다. 멤버 manifest와 크기/SHA256은 `review-members.json`, `review-zip.json`에 있다.

다음 단계 하나: 기능 검증된 **A/B0 직접 성능 비교**의 별도 protocol을 먼저 고정한다. 이번 goal에서 원본 대비 성능 비교나 장기 confirmation을 자동 실행하지 않는다.
