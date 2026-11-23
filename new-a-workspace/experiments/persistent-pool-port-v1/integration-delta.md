# Persistent CPU pool 선택 이식: 검토 결과

현재 상태는 **WAITING_NUMERICAL_BASELINE**이다. 준비된 R 수치 호환 baseline이 없으므로 모델 실행이나 성능 pilot을 수행하지 않았다. 현재 E 위의 별도 overlay는 검토·모델 없는 시험을 위한 후보이며 채택된 runtime이 아니다.

## 기존 구현과 이번 변경

| 항목 | 기존 E | donor | 이번 overlay |
|---|---|---|---|
| 설정 | 측정 env는 `GGML_NEWA_POOL=off` | server-owned pools | 기존 off/on 보존, `donor` 분기 추가 |
| pool 구성 | on일 때 max(threads,batch) 하나를 두 역할에 연결 | 모든 역할 parameter가 같으면 공유, 다르면 별도 | generation 5 / batch 6, 별도 pool |
| polling | optional on은 0, disposable 기본은 50 | CPU role parameter 전달 | baseline off와 donor 모두 50 |
| 배치 | process fixed affinity, optional unrestricted role | role mask/strict/priority 전달 가능 | 정상 priority, 역할 mask 없음, strict 없음만 허용 |
| 초기 상태 | optional on paused | 생성 시 paused | donor 그대로 |
| 소유권 | 수동 생성/해제 | RAII owner | owner를 llama context owner보다 먼저 선언 |
| 종료 | synchronize/detach 후 optional pool free, 이후 context 해제 | context/backend가 끝난 뒤 pool 해제 | donor 분기는 sync/detach, context reset, pool reset |
| phase | scalar v1 marker와 기존 E 정책 | HEAD에는 더 넓은 변경 포함 | scalar v1/E 정책 유지; v2 미이식 |

`method.patch`에는 header 추가와 server ownership/attachment/lifecycle 분기만 있다. `overlay-identity.json`에 E 정책 header, scalar marker, CPU backend, llama context, sampler의 불변 SHA256을 기록했다. Q4/Q6 연산, E threshold/task continuity/fallback, FA/KV, 모델, scheduler는 바꾸지 않았다. 전체 donor context를 복사하지 않았다.

선택 경로는 CPU-only 일반 decoder text, tensor override 없음, speculation/multimodal/embedding 없음, threads5/6, 두 role poll50 및 unrestricted placement에서만 허용한다. 지원 범위 밖이면 초기화 실패로 처리한다. 이는 모든 donor 기능을 검증했다는 뜻이 아니다.

## OpenMP에서 실제 의미

현재 동결 CPU DSO는 OpenMP ON이며 libgomp를 사용한다. `ggml_threadpool_new_impl`의 OpenMP 분기는 pool/worker 상태를 할당하지만 native `ggml_thread_create` 경로를 실행하지 않는다. 따라서 disposable GGML pool을 매 graph 만든다고 해서 매번 OS thread를 만든다는 뜻은 아니다. 기대 이득은 GGML 상태 할당/해제 비용 감소일 수 있으나 wall-time 기여는 아직 측정하지 않았다.

OpenMP에서 GGML pause/resume은 no-op이다. donor의 paused 값이 libgomp worker를 park시키거나 spin을 제어한다고 해석하면 안 된다. 비활성 donor pool에는 별도 native worker가 없다. 실제 unit test에서 pool 생성 전후 task 수가 증가하지 않음을 확인했으나 이는 libgomp의 모든 대기 비용이 0이라는 증거가 아니다.

Graph 실행 시 cgraph/cplan, current_chunk, abort, error 상태가 재설정되고 현재 phase가 갱신된다. native custom barrier는 OpenMP 경로와 분리되어 있다. 5/6 pool 교체와 abort 후 recovery를 실제 DSO의 F32 graph로 검사했다. 연산 모델 전체의 출력 동등성은 아직 확인하지 않았다.

기존 teardown에 구체적인 use-after-free가 있다고 단정하지 않는다. 새 donor 경로는 pool보다 context/backend를 먼저 해제하는 소유 순서를 명시한다. capability 누락 및 NULL 생성 실패의 unit test는 allocator 자체가 assert/abort하는 OOM까지 복구한다는 증거가 아니다.

## ABI와 회귀

실제 registry에는 `ggml_backend_cpu_newa_phase` setter가 있다. phase getter는 ELF export이며 registry entry가 아니므로 테스트에서 `dlsym`으로 확인했다. scalar `uint32_t` marker와 trace 구조(80 bytes)를 검증했고 v2 pointer ABI는 추가하지 않았다.

`results/model-free-1`: PASS. `results/regressions-1`: 초기 harness 조회 오류와 빠진 표준 header를 포함한 실패를 보존했다. 수정 후 `results/regressions-2`: 핵심 unit/graph/marker 검사, HINT ON 및 HINT+TRACE context syntax 검사 PASS. HINT OFF 전체 context는 원본 E와 후보 모두 `newa_resource` 미선언으로 실패한다. 이는 기존 E의 guard 문제이며 이번 lifecycle-only 범위에서 수정하지 않았다. 따라서 모든 build mode가 통과했다고 주장하지 않는다.

전체 server 재링크, 모델 token equality, cancellation/sleep-resume, 실제 server exception teardown, steady-state disposable-pool 진단은 NOT_RUN이다. 모델 없는 예외 소유권 시험을 실제 server 기능 시험으로 대체하지 않는다.

## 출처와 재현 경계

정확한 네 commit 및 Git blob 검증은 `source-pin.json`에 있다. donor 설명 파일의 실제 경로는 `tools/server/bench/cpu/threadpools.md`이다. donor HEAD에는 이미 pool 변경이 있으므로 문서의 `before=$(git rev-parse HEAD)`를 baseline 명령으로 사용하지 않았다.

공개 scheduler pin과 기존 보관 source의 비교에서 110개 blob이 동일했다. 공개 구현을 별도의 새 개선으로 계산하지 않는다. 향후 비교는 동일한 승인 R + 기존 E 정책에서 pool off/donor만 달리해야 한다. native pthread 전환, RT priority, per-role affinity, dynamic affinity 문제 해결은 이 후보의 범위 밖이다.

## 재현 진입점 확인

`results/reproduce-1/`에서 새 output 디렉터리를 받는 재현 진입점을 실제 실행했다. 13개 mapped DSO를 unit 프로세스 안에서 기록했고, 프로젝트 DSO가 동결 NEW_A 폴더에서 로드됐음을 확인했다. HINT OFF 오류는 원본·후보의 모든 `error:` 메시지가 동일한 경우에만 inherited로 분류한다. 이 분류는 해당 build mode의 실패를 PASS로 바꾸지 않으며 다른 gate의 실패를 제외하지 않는다. 생성된 test ELF는 hash를 남기고 정리했다.

정적 재사용·종료 순서 검토에 사용한 정확한 source 구간과 해시는 `evidence/pool-lifecycle-source-review.txt`에 있다. 코드 구조에 대한 증거와 실제 모델 lifecycle에 대한 증거를 구분한다.
