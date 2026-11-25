# Intel 전달 전 로컬 호환성 점검

이 문서는 과거 B0/A 비교의 보존 기록입니다. 현재 배포본의 실행 명령, 폴더 구조와 결과 위치는 공용 실행 안내에서 확인하세요. [현재 Intel·AMD 실험](../../README.md#intelamd-cpu-실험) · [과거 전체 원본](https://github.com/codinghuman0/llama-scheduler/tree/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace)


2026-11-23 결과: **LOCAL_AVX2_BUILD_AND_SMOKE_PASS**.

대상은 Intel i5-1240P / Ubuntu이며 실제 점검 호스트는 AMD Ryzen 5 5500U다. Intel에서 사용할 공통 ISA로 소스를 다시 빌드하고 실제 모델 실행까지 확인했다. **Intel 하드웨어 실행·Intel 성능·Intel 커널 sched_ext 적용은 NOT_RUN**이다. Intel 성능 개선이나 완전한 시스템 이식 성공으로 확대 해석하지 않는다.

| 검사 | 결과 |
|---|---|
| B0 pinned source + A/R overlay의 새 Release/OpenMP 빌드 | 두 arm PASS |
| AVX2/FMA/F16C/SSE4.2 공통 옵션, native/AVX512/AMX 미사용 | compile_commands 검사 PASS |
| i5-1240P형 4P+8E synthetic topology, 제한 cpuset, SMT 중복 거부 | 비권한 unit tests PASS |
| 원본 모델 tokenize/토큰 수/요청 간 cache_n=0 | PASS |
| 두 8-request cohort + 두 singleton, 각 arm warmup/measured | PASS |
| cpu25에서 첫 8-request cohort, 세 arm 비교 | PASS |
| 총 15 fresh-server visits / warmup 포함 156개 완료 요청 | 16 tokens/request, PASS |
| B0/A equality 및 A/F6 신규 정책 equality | 5개 cohort/condition 비교 모두 PASS |
| 실제 DSO 해시, 기본 Linux worker policy/affinity, OpenMP team | PASS |
| cpu25에서 실제 외부 소비 | B0 0.25198, F6 0.24955, A 0.24993 core |
| measured multi-request Decode 선택 | ambient A=6; cpu25 F6=6, A=5, 각 15회 |
| 모든 소유 server/load cleanup | 정상 종료, sched_ext disabled |
| 새 unit tests | 9개 PASS |
| 기존 저장소 `make -j2 check` | PASS; Python 51개 중 1개 skip + shell 검사 |
| 모델 + 보관 best A runtime 20개 경로, 원본 `src/llama` | 해시 보존 확인 PASS |

기존 `make check`의 skip 하나는 별도 `.deps` semantic fork가 없는 검사다. 새 `src/llama + R` 전체 빌드와 smoke를 건너뛴 것이 아니다. BPF를 빌드하는 기존 make target은 실행했지만 로드하지 않았다.

새 빌드 ID는 `e611172cc7a6a518`이다. 첫 시도에서는 B0에 복사한 고정 UI가 `ui.h`를 찾지 못해 실패했다. recipe 2에서 alias header까지 양쪽에 동일하게 포함해 해결했다. 실패 로그와 두 번째 빌드의 전체 입력·컴파일 명령을 보존했다. 기존 source와 검증 runtime을 고친 것이 아니다.

증빙: [verification.json](../experiments/intel-portability-check-v1/verification.json), [전체 로컬 검증 폴더](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/intel-portability-check-v1/README.md). raw HTTP 응답, policy 재계산, CPU/load, DSO, cleanup, build 로그와 artifact SHA256가 포함된다.

이번 측정은 짧은 기능 smoke이며 **성능 gain 판정이나 full pilot/confirmation은 하지 않았다**. pilot의 paired 분석·불균등 부하 거부 경로는 unit test로 점검했다. 실제 Intel에서 128 tokens/request pilot을 실행할 방법은 [실험 안내](INTEL_EXPERIMENT.ko.md)에 있다. 새 B0/A AVX2 바이너리는 보관된 AMD runtime과 바이트가 같은 것으로 주장하지 않는다.

남은 Intel 검증은 해당 장비의 실제 CPU 선택 확인, 새 빌드, smoke, pilot이다. i5-1240P의 P/E 혼합 및 더 짧은 Prefill 때문에 6-worker fallback이나 다른 성능 결과가 가능하다. 기존 6-CPU envelope를 유지한 한정 비교이며 16 threads 전체를 최적화한 정책이 아니다. 커널 scheduler를 검증하려면 별도 kernel/BTF 검토와 승인된 selected-child load 절차가 필요하다.
