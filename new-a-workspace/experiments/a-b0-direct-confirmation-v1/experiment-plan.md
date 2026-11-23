# A/B0 직접 확인 계획

현재 `A`는 직전 R 수치 호환 gate를 통과한 CPU 라이브러리와 기존 E Prefill-pressure server/helper의 조합이다. donor pool은 off다. `B0`는 7a2db1a0cf38e5f4eb278a58c3903d295258d0ea의 보존된 재빌드이며 잃어버린 원본 binary와 byte identity를 주장하지 않는다. 이번 작업에서 inference 코드, binary, 모델, 커널, E 규칙을 변경하거나 재빌드하지 않는다.

`cases.json`은 직전 cases의 B0/A 항목을 그대로 참조한다. `fixtures.json`도 원본 그대로이며 두 8요청 cohort만 이번 계획에 사용한다. heldout이라는 이름은 과거 명칭이다. 실제 순서는 `order.json`에 있고, 각 campaign/condition/cohort 안에서 두 arm 순서가 각각 두 번 등장한다. campaign 2는 condition과 arm 순서를 뒤집는다.

먼저 네 fresh-server smoke에서 warmup/검사 출력을 확인한다. 통과하면 `confirmation-v1` namespace에서 두 campaign을 연속 실행한다. 캠페인마다 ambient 8 pairs와 cpu25 8 pairs, 총 64 measured server visits다. 요청 8개를 독립 반복으로 세지 않는다. 서로 다른 장비나 새로운 workload의 재현이라는 뜻은 아니다.

Primary는 각 atomic HTTP cohort에서 실제 생성된 1024 tokens를 전체 HTTP wall seconds로 나눈 값이다. 같은 fixture의 한 warmup과 loading은 제외하고, 정책 비용은 포함한다. identity/proc/환경 검사는 HTTP clock 밖에 있다. 공통 `--perf`, log verbosity 4, OMP_DISPLAY_AFFINITY 설정은 양 arm에 유지했다. 무거운 observer나 LD_PRELOAD는 없다. CPU seconds는 proc counter bracket의 보조 지표이며 에너지 소비가 아니다. 응답의 phase별 timings는 요청별 보조 자료로 보존하며 aggregate throughput으로 합산하지 않는다. TTFT는 nonstream이므로 NOT_MEASURED다.

기존 base visit, 부하 generator, pressure auditor를 hash가 같은 작은 Python 파일로 복사해 새 폴더에서 사용한다. inference runtime 복사본은 없다. wrapper는 같은 monotonic HTTP 경계, 명시적 환경 allowlist, 실제 loaded ELF, token oracle, worker envelope, cpu25 실소비 및 cleanup 검사를 추가한다. 부하는 CPU10에서 12.5 ms process CPU / 50 ms를 목표로 생성하고 READY 후 0.5초 안정화한다. measured window마다 0.22~0.28 core를 요구한다.

`seal.json`은 프로토콜·fixtures·cases·전체 order·runner·분석·독립 재계산 코드·원래 검증 문서를 smoke와 첫 timing 전에 동결한다. 초기 분석 자체 검사 호출에서 작업 디렉터리를 중복 지정한 command 오류가 있었다. 파일 수정이나 모델 실행 없이 명령 경로만 수정했고 상수 gain, cohort 비율 보존, quantile 계산 검사는 통과했다.

유효성/안전 실패는 해당 raw와 미실행 계획을 남기고 중단한다. 느린 결과나 목표 미달은 중단 사유가 아니다. pair 추가·교체는 없고 첫 campaign 결과를 보고 두 번째를 튜닝하지 않는다. 분석은 8 paired blocks를 cohort 안에서 4개씩 재표본하는 10,000회 stratified bootstrap, seed 20261122, `(n-1)*p` 선형보간 quantile로 고정했다. 각 네 cell의 mean gain>=5%, CI lower>0%, faster>=6/8을 모두 요구한다.

계획된 공간은 raw와 ZIP을 합해 512 MiB 이내이며 시작 시 약 3 GiB가 남아 있다. runtime/model/object/archive 복제나 기존 자료 삭제는 하지 않는다. measurement lock, 실행 timeout, UID와 sched_ext disabled, CPU topology, 시작/종료 온도·메모리·디스크·전원·governor 검사 및 자신이 시작한 프로세스 정리를 유지한다. 결과가 나오면 원시 HTTP token/clock/counter에서 재계산하고 별도 산술 경로와 대조한다.

`original-code-changing patch`: 없음. 신규 코드는 실험 runner, 검증/분석, 문서/포장에 한정한다. 전체 runtime 효과를 E의 단독 효과나 kernel scheduler 성과로 해석하지 않는다. P, A-fixed6, Intel, 새로운 scheduler는 이번 계획에 포함하지 않는다.

실행: `./reproduce.sh smoke --name admission-v1`, 이후 `./reproduce.sh full --name confirmation-v1`. 재현은 새 이름만 허용한다. 기존 namespace를 덮어쓰지 않는다. 상태는 GOAL_STATE.md와 ledger.jsonl, results/<name>/campaigns.json에 기록한다.
