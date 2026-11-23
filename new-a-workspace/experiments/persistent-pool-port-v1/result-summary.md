# 최종 검토 상태: WAITING_NUMERICAL_BASELINE

선택 이식 후보와 모델 없는 검증을 준비했다. **새 후보의 모델 성능은 측정하지 않았다.** R 또는 사전 지정 동등 수치 호환 baseline이 없으므로 모델 기능 검사와 paired pilot은 실행하지 않았다. 이는 sudo 문제나 성능 회귀 판정이 아니다. 이 goal은 sudo/BPF를 사용하지 않는 조건이다.

판정은 **검토용 후보 보존, 실사용 채택 보류**다. 선택 이식과 상태 재사용은 현재 OpenMP ABI에서 가능했지만, 할당 비용 절감이 충분한 처리량 개선으로 이어지는지는 R 이후의 제한된 pilot 전에는 판단할 수 없다.

## 무엇을 추가했는가

공개 scheduler pin에는 기존 감사 source와 동일한 blob이 110개 있다. 이를 새 개선으로 계산하지 않았다. 기존 E의 optional on은 max(5,6) 단일 pool/poll0였지만 실제 E 측정은 off였다. 이번 별도 overlay는 donor의 소유권·초기화·연결·해제만 선택 이식했고, OpenMP, poll50, 정상 priority, unrestricted role placement, 고정 프로세스 CPU envelope를 유지한다. generation5/batch6 두 pool을 기존 E resource policy와 함께 쓰는 후보다. phase v2, 새 scheduler, 수치 커널 또는 모델을 추가·변경하지 않았다.

현재 OpenMP에서는 GGML pool 생성과 OS worker 생성이 같지 않다. pool pause/resume은 OpenMP에서 no-op이다. 가능한 이득은 반복되는 GGML pool 상태 할당/해제 비용 감소이지만 그 비용의 wall-time 비중이나 최종 처리량 효과는 아직 모른다. phase 정책의 새 독립 기여를 주장하지 않는다.

## 검증과 한계

- 모델 없는 생성 실패/capability 누락/parameter forwarding/shared·separate pool/reset/retry 검사를 통과했다.
- 실제 frozen CPU DSO에서 5/6 pool 교체, abort 후 recovery, graph 재사용, 두 예외 소유권 cycle, scalar phase ABI 검사를 통과했다. pool 생성 자체의 OS task 증가가 없음을 관측했다.
- HINT ON 및 HINT+TRACE의 후보·원본 context syntax 검사는 통과했다. HINT OFF의 전체 context는 **원본과 후보 모두 동일한 newa_resource 미선언 오류**로 실패한다. 이 inherited failure는 숨기거나 PASS로 바꾸지 않았다. 작은 HINT OFF marker test 통과는 전체 server build 통과가 아니다.
- 최초 harness 실패(`regressions-1`)를 보존했다. getter의 registry/ELF 조회 차이와 누락된 테스트 include를 수정했다. `regressions-2` 및 실제 재현 진입점 `reproduce-1`에서 적용 가능한 검사들을 재확인했다.
- `reproduce-1`은 unit 프로세스가 실제 로드한 13개 DSO 경로·해시를 기록한다. 과거 B0/B1/E 프로세스에서 로드된 프로젝트 ELF 24개도 현재 동결 runtime과 일치한다.
- 전체 server 링크·실제 모델 자유 생성 equality·cancellation·sleep/resume·서버 예외 종료·steady-state disposable pool 진단은 NOT_RUN이다. 모델 없는 backend 예외 시험을 이러한 모델 기능 gate의 대체로 쓰지 않는다.

## 성능 결과

이번 후보 관측 수는 0, pilot raw는 빈 JSONL이다. `results/pilot-analysis.json`은 두 조건 모두 NOT_RUN을 반환한다. `protocol.json`과 `fixtures.json`에 정확한 과거 두 8요청 cohort 및 singleton, actual output count, threads5/6, 명시 환경, poll/mask 의미, 조건별 balanced 4 paired block과 중단/분석 규칙을 고정했다. admission은 닫혀 있다.

옛 OpenMP 대 native pool 실험은 4 paired block의 HTTP 시간 평균 변화 -0.6756%, 빠른 pair 2/4였다. backend·FA·동시성 등 현재 조건과 달라 현재 후보의 효과로 해석할 수 없다. `results/history-recalculated.json`은 그 개별 관측에서 재계산한 값이다. off 선택의 명시적인 최종 이유는 조사 범위에서 unknown이다.

새 5~10% 이득, 과거 18~22%의 재현, 에너지 절감, Intel 성능 개선을 주장하지 않는다. historical dynamic-affinity 문제도 해제하지 않았다.

## 보호·재현

수치 source/runtime/policy/model 내용은 보존했다. 도중 사용자의 별도 정리 지시로 archive 컨테이너와 실행 wrapper의 모델 경로, 문서·manifest가 변경되었다. 이 7개 변경은 `evidence/protection-after.json`에서 별도 표시한다. 남긴 과거 자료 35,174개 고유 blob은 원본 해시와 일치하며 원본 소스·모델 3,265개 파일도 다시 확인했다. 생성된 unit 실행 파일은 제거하고 source/명령/로그/결과를 보존했다.

재현 명령은 README.md에 있다. 이 review ZIP은 모델·runtime 복사본이 없는 작은 검토 패키지이므로 모델 없는 재현에는 기존 new-a-workspace가 필요하다. ZIP 자체의 모든 member hash는 REVIEW-MANIFEST.json으로 확인할 수 있다.

**다음 단계 하나:** 별도의 R 수치 호환 baseline 검증을 완료한다. 구체적인 gate는 next-step.md에 있다. 이 goal에서 R 구현을 중복 수행하지 않는다.
