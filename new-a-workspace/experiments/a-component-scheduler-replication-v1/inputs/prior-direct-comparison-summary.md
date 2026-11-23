# A/B0 직접 확인 결과

성과 상태: **CONFIRMED_SCOPED_A_OVER_B0**. 작업 범위: 두 Linux-only 확인 캠페인, 분석·보존·재현 검사 및 검토 패키지. 이는 기존 원본 대비 런타임 전체 효과이며 kernel scheduler 단독 효과나 E worker 선택 단독 효과가 아니다.

| 캠페인 | 조건 | B0 tokens/s | A tokens/s | 평균 paired gain | 층화 bootstrap 95% | 빠른 pair | 목표 |
|---|---|---:|---:|---:|---|---:|---|
| 1 | ambient | 49.1255 | 57.2566 | +16.5521% | [+16.3497%, +16.7530%] | 8/8 | PASS |
| 1 | cpu25 | 41.0812 | 51.7483 | +25.9706% | [+25.5901%, +26.3341%] | 8/8 | PASS |
| 2 | ambient | 49.2763 | 57.3228 | +16.3304% | [+16.0038%, +16.6822%] | 8/8 | PASS |
| 2 | cpu25 | 40.9864 | 51.7081 | +26.1730% | [+25.2377%, +27.1494%] | 8/8 | PASS |

Primary는 동일 atomic 8-prompt cohort의 실제 생성 1024 tokens / 전체 HTTP wall time이다. 위 절대값은 visit 처리량의 산술 평균이고 gain은 block별 A/B0 비율의 평균이므로 두 열의 평균 비율과 같다고 가정하지 않는다. 각 cell마다 paired block 8개, h1/h2 각 4개, cohort 안에서 각각 4개를 복원추출하는 층화 bootstrap 10,000회, seed 20261122, `(n-1)*p` 선형보간 95% percentile이다. 요청 8개를 독립 표본으로 세지 않았다. 네 cell 모두 mean>=5%, lower>0%, faster>=6/8일 때만 목표 충족이다. 평균 5%는 최소 5% 보장이 아니다. CI 하한까지 5% 이상인지도 JSON의 strong_evidence에 별도로 기록했다.

## 정체와 변경 범위

B0는 source `7a2db1a0cf38e5f4eb278a58c3903d295258d0ea`의 보존 재빌드다. 잃어버린 원본 binary와 byte identity는 주장하지 않는다. A는 기존 B1 overlay에 semantic Prefill Q4 기준 본문 fallback R을 적용한 연산 DSO와 기존 Prefill-pressure E 서버의 조합이다. Decode/Mixed exact Q4, Q6, phase bridge는 유지된 검증본이다. 이번에는 source/runtime/DSO/모델을 수정하거나 재빌드하지 않았다. donor pool P는 포함하지 않았다.

실제 경로·hash·inode는 identity.json, 기존 compiler/options/overlay 출처는 inputs/previous/identity-map.json과 R/A identity 및 checkpoint에 있다. actual argv/env와 loaded ELF는 각 server/runtime.json, ELF 별칭은 loaded-ELF-aliases.json에 있다. 모델 SHA256은 `f3bdf9cf31dee4b57ae4e455a1cb0d01b5c2c1b50d72d3112141c195506c2840`이다. 진단 R-diagnostic/P 라이브러리는 사용하지 않았다.

AMD Ryzen 5 5500U의 physical cores 6개에 대응하는 CPU [0,2,4,6,8,10], controller CPU11, OpenMP, threads5/batch6/http8, parallel8, context8192, batch512/ubatch256, CPU-only, FA on, no-kv-unified, speculation none이다. B0에 fork-only profile 옵션은 전달하지 않는다. A는 phase/pressure, Q4/Q6 phase_batch, Prefill attention off, repack huge, pool off를 유지한다. B0와 A의 실제 worker 선택 차이는 treatment 일부이며 동등한 CPU envelope를 유지했다. 환경 allowlist가 부모 LLAMA_ARG/LD_PRELOAD/OMP/GOMP/KMP 설정을 차단한다.

## 실행과 출력

두 cohort는 이전에 사용한 heldout-1/2라는 역사적 이름이며 새로운 미관측 입력이 아니다. 원문, numeric prompt 배열, seed424242, temperature0, nonstream, request당128tokens, ignore_eos, atomic 도착 방식은 그대로다. 모든 유효 warmup/측정 출력은 같은 fixture의 검증된 B0 oracle과 정확히 일치하고 timings.cache_n=0이다. 정상 요청 내부의 autoregressive KV는 유지한다. tokens_cached 필드를 재사용 판정 근거로 삼지 않았다. 새 logits/lifecycle 검사를 반복하지 않고 기존 R/A checkpoint의 모든 참조 hash를 다시 확인했다.

계획과 완료 수: `{"server_launch_attempts": 69, "confirmation": {"valid_measured_visits": 64, "measured_cohorts": 64, "measured_individual_generations": 512, "measured_generated_tokens": 65536, "warmup_cohorts": 64, "warmup_individual_generations": 512, "warmup_tokens": 65536}, "all_completed_response_generations": 1088, "all_completed_tokens": 139264, "smoke_completed_generations": 64, "smoke_completed_tokens": 8192}`. 이전 546 generation이나 P/A pilot, 과거 correctness 시간은 이번 성능 표본에 넣지 않았다. 각 visit은 fresh server, 동일 한 warmup, 한 measured cohort, 정상 owned cleanup으로 이루어졌다. loading/warmup/identity/proc 검사는 primary clock 밖이며 정책 비용과 queueing/prefill/decode/응답 완료는 포함한다. TTFT는 NOT_MEASURED다.

cpu25 실측 CPU 소비 범위: **[0.2509338013591766, 0.25313460174250363] core**. CPU10, normal priority, 12.5ms CPU/50ms, 양 arm 동일 시작/0.5초 안정화/warmup/종료 규칙이다. 모든 per-arm window 값과 raw counter는 JSON에 있다. CPU seconds와 CPU seconds/token은 보조 자료이며 에너지 절감으로 해석하지 않는다. 온도/주파수/전원/governor와 E pressure 원시 epoch·선택·actual OpenMP teams도 실행별 보존했다. E의 정상 fallback/선택 변화는 결과에 포함하고 sensor 실패만 admission 위반으로 처리했다.

## 사전 등록과 실패 이력

두 campaign의 전체 순서·코드·분석은 timing 전에 seal.json으로 고정했다. 각 cohort 안에서도 arm 순서가 두 번씩 교차하며 campaign2는 condition과 arm 순서를 뒤집었다. 캠페인 사이 튜닝, pair 추가·교체, workload/metric 사후 선택은 없다.

첫 smoke admission-v1은 loaded library의 hardlink 별칭을 문자열로 비교한 runner 오류로 HTTP generation 이전에 중단했다. 기존 inode/hash 검증을 사용하도록 wrapper와 raw auditor를 수정했고 실패 기록 함수의 중복 timestamp도 고쳤다. battery Charging/Full 표시는 관찰값으로 남기고 실제 AC online/type은 고정했다. 원래 동결본은 registrations/pre-smoke-v1, 실패 raw는 results/admission-v1, 수정 명세는 evidence/pre-timing-amendment.json에 있다. 모델/runtime/workload 변경 및 소비된 timing은 0이었다. admission-v2의 네 fresh smoke를 완료한 뒤 확인 캠페인을 시작했다.

## 해석, 보존, 재현

이번 결과의 적용 범위는 같은 AMD 장비, 같은 두 distinct cohort, parallel8, 지정 입력/출력 길이와 ambient/cpu25다. 두 독립 실행 캠페인은 다른 CPU나 새로운 workload의 일반화를 뜻하지 않는다. 모든 모델/shape/ISA, 의미적 답변 품질, 단일 chat 속도, 에너지, Intel 효과는 검증하지 않았다. A-fixed6 ablation과 연구용 kernel scheduler 비교도 수행하지 않았다. E의 독립 기여는 **not-isolated**다. 원 프로젝트의 scheduler 포함 최종 구성 검증을 이 Linux-only 비교로 대체하지 않는다.

검증된 보호 파일 4982개와 원래 외부 파일 3265개, 모델 inode/hash를 유지했다. 기존 archive/실험/ZIP을 수정하지 않았고 sudo/BPF/전역 설정 변경/Git commit/push를 하지 않았다. cleanup.json에서 자신이 시작한 server/load 종료와 measurement lock을 확인했다.

```bash
cd /home/codinghuman/projects/new-a-workspace/experiments/a-b0-direct-confirmation-v1
./reproduce.sh verify
./reproduce.sh analyze --name confirmation-v1
./reproduce.sh smoke --name my-new-smoke
./reproduce.sh full --name my-new-confirmation
```

full은 사전 정의된 두 캠페인 모두를 새 namespace에 실행하며 기존 이름을 덮어쓰지 않는다. 원시 재계산은 analyze.py가 응답/clock/counter/pressure를 직접 검증하고 recalculate.py가 별도 산술 경로로 gain/CI를 재계산한다. review ZIP은 source/input/raw/분석/문서 중심이며 모델, runtime, object/archive 복제본을 포함하지 않는다. 내부 및 sidecar에서 동일한 `REVIEW_MANIFEST.json` 이름을 사용한다. ZIP 크기와 SHA256은 review-zip.json에 기록한다.

종료 사유: 이번 고정 비교 범위 완료(완결성 감사는 completion-audit.json과 ZIP 검사 결과 참조). 새 최적화·정책 탐색은 수행하지 않는다.
