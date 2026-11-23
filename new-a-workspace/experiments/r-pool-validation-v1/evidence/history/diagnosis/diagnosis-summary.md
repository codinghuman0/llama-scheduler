# B0 / NEW_A B1 최초 출력 분기 진단

## 결론

**Root-cause 상태: LOCALIZED.** 원래 heldout-1의 최초 token 분기를 기존 NEW_A의 **Q4 Prefill `newa_q4_candidate` 경로**에 재현 가능하게 연결했다. Q4off에서 B0 logits와 출력을 복원했고, Prefill-only 및 full 재활성화에서 B1 차이가 돌아왔다. Q6와 exact Decode Q4는 조사한 h1 차이를 설명하지 않는다.

이는 특정 실행 경로의 인과 격리다. 모델 내부 최초로 다른 부동소수점 bit가 생긴 layer/node, 전 층의 수치 오차 전파, 의미적 품질 동등성까지 증명한 것은 아니다. 수학적 결함이 확인된 것도, 차이가 무해하다고 확인된 것도 아니다. 기존 E 정책과 scheduler는 변경하지 않았다.

## 1. 동결 정체와 반복 재현

B0는 `7a2db1a0cf38e5f4eb278a58c3903d295258d0ea` 역사적 소스의 보존된 재빌드다. 당시 원본 binary 자체가 남아 있다는 뜻은 아니다. B1은 `59abec45fe0919de20550ce7cdcf363d9f7bbe5a` 기반의 server/common(`llama-phase-barrier`), libllama(`llama-prefill-attention-v2`), CPU DSO(`llama-phase-batch-q4-exact-v1`)와 캡처된 overlay의 조합이다. `identity/B0.json`, `identity/B1.json` 및 실제 loaded DSO SHA256을 사용했으며 현재 HEAD 하나로 대체하지 않았다.

모델 SHA256: `f3bdf9cf31dee4b57ae4e455a1cb0d01b5c2c1b50d72d3112141c195506c2840`.

CPU envelope `[0,2,4,6,8,10]`, threads5/threads-batch6, parallel8, batch512/ubatch256, ctx8192, full Flash attention, separate KV, GPU0, no speculation을 유지했다. 원래 8개 prompt token 배열을 atomic `/completion` 요청으로 보냈다. 요청 간 cache 재사용 없이, temperature0/seed424242/ignore_eos=true/128 generated tokens였다. 최초 반복에서 포트만 임시 localhost 포트로 바꿨다.

원시32개 응답의 첫 mismatch를 독립 재계산했다. 두 cohort 모두 request index0,1,2,5는 같고3,4,6,7은 다르다. 첫 다른 generated-token index는 h1 `[2,7,10,7]`, h2 `[123,10,5,2]`다. 각 cohort에서 B0/B1/B1/B0 순서의 fresh server를 실행했고, 서버별 warmup/measured가 모두 같은 runtime의 기존 출력과 정확히 일치했다. 총8 fresh visits,128 응답이다. 이는 correctness 반복이며 새 throughput confirmation이 아니다.

BOS와 실제 tokenizer 결과, 유효 sampling processor/parameter, model/config/compiler/ISA, loaded project 및 system libraries를 대조했다. B0/B1 sampler 및 batch 핵심 소스는 byte-identical하다. B1 attention 대체 경로는 실제 env에서 off이고, 최초 분기 구간에 context-shift도 없었다. 자세한 차이/동일성은 `evidence/component-source-comparison.json`과 `.diff`에 있다.

## 2. 원래 8요청의 최초 token 분기

| 항목 | 관측 |
|---|---|
| Cohort / 요청 | heldout-1, index3, h1-d(어휘 학습 설계) |
| Generated-token index | 0-based2 |
| Model call / sequence / position | call4 / seq4 / pos110, batch_index4 |
| B0 선택 / B1 선택 | token6169 / token3561 |
| Raw argmax | sampler 이전부터 각각6169 /3561 |
| Vocab logits |151,936개, 모두 finite |
| max absolute difference |0.714747428894043 |
| mean absolute / RMS difference |0.1270115707792352 /0.15550459202924385 |
| top1-top2 margin B0 / B1 |0.033043861389160156 /0.18288803100585938 |
| RNG / processor sequence | 동일 |

이 호출까지 **전체8개 요청의 논리 token history, 실제 batch/physical ubatch token ordering, seq/position, KV min/max와 graph worker profile**이 같다. 대상 요청 하나만 맞춘 비교가 아니다. 다만 기존 산술 차이로 K/V의 수치 내용이 이미 달라질 수 있으므로 KV buffer byte equality를 주장하지 않는다.

대상 요청의 g0(call2) logits부터 이미 maxabs0.730075 차이가 있고 g1은0.686031이다. 이때는 선택 token이 같았다. 따라서 “처음 다른 token”과 “처음 관측한 logit 차이”를 구분해야 한다. 전체 network의 최초 산술 차이 위치는 아직 특정하지 않았다.

두 free-generation 실행이 분기한 이후의 logits는 같은 계산으로 비교하지 않는다. h1 free 비교의 g3은 분석에서 제외했다. 이후 비교에서는 **8요청 모두** B0 token을 teacher-force하고 원래 sampler 선택/강제 반환을 분리 기록했다. 강제 반환값의 B0 일치를 정확성 증거로 세지 않는다. 상대오차 분모는 `max(abs(a),abs(b),0.001)`이며, near-zero에서 커지는 상대오차를 절대오차와 분리한다.

## 3. 한 요인씩 분리한 결과

| B1 변화 | 실제 경로 증거 | 같은 전체 history에서 g0..3 logits | 자유 warmup 출력 |
|---|---|---|---|
| 원래 full | Q4/Q6 phase_batch | B0와 다름 | 기존 B1과 일치 |
| Q6만 off | Q6 mode=off, chunks0/0/0/0 | full B1과 byte-identical | 기존 B1과 일치 |
| Q4만 off | Q4 calls0/0/0/0, Q6 positive | B0와 byte-identical | 8개 모두 B0와 일치 |
| Q4 Prefill-only | Q4 Prefill calls positive, Decode/Mixed0 | full B1과 byte-identical | 기존 B1과 일치 |
| full 재활성화 | 원래 설정, fresh server | 최초 full B1과 byte-identical | warmup/measured 모두 기존 B1과 일치 |

추가 범위 확인에서 heldout-2도 Q4만 끈 자유 생성의 warmup/measured8개씩 모두 원래 B0 출력과 일치했다(`evidence/h2-q4off-output-comparison.json`). h2의 layer별 수치 원인까지 별도로 계측한 것은 아니다.

`GGML_NEWA_Q4_TILE32`는 실제 frozen CPU DSO가 지원하는 설정이다. `sources/newa-q4-policy.h:43` 이후는 semantic Prefill(phase1)이고 nr>=32이면 `newa_q4_candidate`를 호출한다. Decode/Mixed의4/8/12행은 별도 `newa_q4_decode_exact` 경로다. 호출부는 frozen `arch/x86/repack.cpp:2045`다. marker 원래 함수를 그대로 실행했으며 userspace phase 갱신을 끄지 않았다. ABI가 불명확한 DSO 교환도 하지 않았다.

`newa-q4-tile32.h`의 Prefill candidate는32행 tile과 fused minimum correction을 사용한다. 원래 copy는 positive/minimum을 별도 float accumulator에 더한 뒤 빼고, candidate는 같은 accumulator에 fmadd/fnmadd를 수행한다(예: candidate1081–1094, tail1412–1425). 따라서 실제 float rounding 순서가 다르다. exact Decode 경로의 이름에 있는 “exact”를 전체 B1/B0 동일성으로 해석할 수 없다.

## 4. 단일 요청 및 실제 operator 축소

원래 h1-d token109개와128 output 정책을 유지하되 active request를 하나로 줄였다. slot 수와 CPU 상한은 유지했다. 각 arm 내부 warmup/measured는 일치했다. B0/B1은 **첫 generated token(g0)** 부터2014/5443으로 달랐고, 같은 입력/ubatch/profile/RNG에서 maxabs logit0.7090420722961426이었다. Q4off는 singleton B0의128개 token 및 저장한 g0..3 logits와 정확히 일치했다. 원래8요청과 single은 첫 분기 위치가 다르므로 두 형상을 섞어 비교하지 않는다.

별도 read-only operator overlay는 실제 single Prefill의 첫 worker0 Q4 GEMM에서 K1536, 실제 nr108/nc64/stride1536 중 첫32×8 결과만 비교했다. 같은 live quantized 입력을 세 계산에 그대로 제공했다. 가중치를 dump하거나 원래 출력 buffer를 수정하지 않았다.

- 별도 컴파일한 candidate가 실제 frozen runtime의 해당256개 값과 byte-identical.
- 모든256개가 finite; copy/candidate 중224개 값이 다름.
- copy/candidate maxabs 차이: `4.172325134277344e-7`, relative L2: `1.8254377556469953e-7`.
- FP64 dequantized dot reference 대비 최대 절대오차: copy `3.02564882481704e-7`, candidate `2.702860069092594e-7`.
- magnitude-scaled FP64 error: copy `4.139688861914147e-8`, candidate `3.891323281477209e-8`.

이 작은 실제 구간은 누적 순서 차이에 따른 수치 차이와 부합한다. 전 층·모든 shape의 정확성,0.7 수준 logit 차이까지의 전체 증폭 경로, 혹은 일반적인 semantic quality 동등성을 증명하지 않는다. NaN/Inf·index 오류·누락 연산 같은 concrete defect는 이 범위에서 발견하지 않았다. 따라서 기존 runtime을 “수정 완료”했다고 주장하지 않는다.

## 5. 기존 성능과 E의 해석

기존 C/B0 약18–22% generated-token throughput 결과, cpu25에서의 C/C-off 효과, 원래 success gate와 파일은 보존했다. 이번에는 성능 캠페인을 실행하지 않았다. Q4off나 진단 overlay의 성능으로 그 수치를 재사용하지 않는다. 원래 workload는 같은 모델·입력·출력 token 수를 통제했지만, 자유 생성이 갈라진 뒤에는 token 내용과 수치 KV 상태까지 같은 계산이라고 할 수 없다. 원래 결과는 선언한 generated-token 처리량 범위이며 정확한 답변 생산성이 아니다.

**E/B1 equality 상태: PASS_EXISTING_EVIDENCE, 이번 신규 E 실행 NOT_RUN.** 기존 감사에서 C/C-off의1,024 응답은 독립 B1 oracle과 일치했다(`evidence/prior-E-B1-token-equality.json`). 이 파일과 원본 E hash를 보존했다. 이 사실이 B0/B1 의미적 동등성까지 뜻하지는 않는다.

품질 원인의 상태와 별도20응답 결과는 `quality-report.md`에 기록한다. 수치 분기와 품질 문제를 동일 원인으로 합치지 않는다. Intel 및 다른 모델·ISA·resource envelope는 이번 검증 범위가 아니다.

## 6. 재현성과 종료 범위

`reproduce.sh`는 일반 계정용 checksum 검사, raw 재계산, singleton/8요청 재현 및 별도 품질 진단을 구분한다. 모든 재현은 새 출력 디렉터리로 실행하며 원래 study/review를 덮어쓰지 않는다. 명령과 의존성, 안전한 cleanup은 README에 있다.

정적 비교·재현·최초 분기 대조·component 격리·단일 축소·bounded live operator 비교까지 수행했다. 최초 연산 bit 위치/전 층 error propagation과 일반 품질 동등성은 미해결 범위로 남긴다. 이 단계의 종료는 특정 경로까지의 진단과 재현 패키지 완성을 기준으로 하며 추가 성능 목표 달성을 뜻하지 않는다. 다음 작업 하나는 `next-step.md`의 B0 누적 순서 호환 후보 검증이다.
