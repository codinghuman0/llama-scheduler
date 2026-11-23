# B0 / B1 / E 정체

`baseline-runtime-identity.json`은 과거 실제 프로세스의 mapped ELF 해시를 현재 파일에 대조한 결과다. B0/B1/E 각각 8개, 총 24개의 프로젝트 ELF가 일치한다. 이번 검사에서 모델 프로세스를 새로 실행하지 않았다. 신규 unit 프로세스의 실제 DSO map/hash는 `results/reproduce-1/regressions/actual-loaded-libraries.json`에 있다.

| 역할 | 소스 및 overlay | 현재 runtime | 과거 실행 설정 |
|---|---|---|---|
| B0 | clean 7a2db1a0cf38e5f4eb278a58c3903d295258d0ea, tree 6fe27004353cc0b49334dd9aac78db20e1cc5ba9. 역사 소스를 GNU13.3.0 Release로 재빌드한 동결본; 당시 최초 바이너리 자체는 아님 | runtime/B0 | threads5/6, OpenMP, 기본 Linux |
| B1 | base 59abec45fe0919de20550ce7cdcf363d9f7bbe5a 위 Q4 exact CPU / llama graph / phase-barrier server의 별도 overlay. 15/7/6개 source-hash 목록과 원 compiler/CMake 명령을 JSON에 포함 | runtime/B1 | pool off, profile legacy, Q4/Q6 phase_batch, huge repack pages |
| E | B1의 산술 DSO를 그대로 유지하고 decode-cost 부모 위 Prefill pressure-v2 server DSO만 변경. 단일 clean revision으로 표시할 수 없는 조합 | runtime/NEW_A | pool off, profile phase, NEWA_DECODE_RESOURCE=pressure |

과거 캠페인의 C는 E runtime과 observe scheduler의 조합이었다. 여기서는 E를 runtime 이름으로만 사용하며 새 pool pilot은 기본 Linux에서 R과 R+pool만 비교한다. 과거 전체 시스템 개선을 이번 기여로 계산하지 않는다.

모델 SHA256은 f3bdf9cf31dee4b57ae4e455a1cb0d01b5c2c1b50d72d3112141c195506c2840이다. 로컬 모델은 models/model.gguf로 접근 가능하다. 공통 원 조건은 CPU 0,2,4,6,8,10, threads5/6, HTTP8, parallel8, context8192, batch512/ubatch256, FA on, separate KV, GPU0, speculative none이다. 전체 argv와 명시적인 GGML_NEWA_*/OpenMP 환경은 JSON에 있다. 시스템 DSO hash도 역사 기록과 신규 unit 기록을 구분해 보존했다.

B1의 선택 당시 Q4 exact 검증과 이후 발견된 Prefill 누적 순서 차이를 혼동하지 않는다. 현재 R 수치 호환 baseline은 준비되지 않았다. 기존 E를 R로 이름만 바꾸거나 Q4off 진단 실행을 R로 승격하지 않았다.
