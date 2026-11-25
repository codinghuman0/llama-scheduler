# 세 저장소의 개선 의도와 2차 연결

| 저장소·선택 커밋 | 줄이려는 비용 | 코드 및 적용 조건 |
|---|---|---|
| codinghuman0/llama-scheduler `441b3b4` | 수치 경로에서 불필요한 Q4/Q6 비용, CPU 경쟁 시 과도한 Decode worker, 재현 시 혼합 DSO 오류 | R의 Prefill reference, exact eligible Decode/Mixed Q4, Q6 batch4, legacy E의 6 CPU / 5·6 workers. A의 일반 Linux 증거와 A_S 선택 child 관측은 보존한다. |
| hsju2021/llama.cpp-fork `384f3cf` | token-count 기반 compute profile이 semantic phase를 오인하는 경우, graph마다 pool 생성·해제, state 전이 관측, server 부하의 지연시간 계측 | explicit API는 generation/batch 두 자원 profile을 graph 전체에 설정한다. 실제 제출 view의 token origin으로 phase를 분류한다. persistent pool은 CPU-only decoder에서 awake lifecycle 동안 보유한다. v2는 sequence/run/active를 포함한다. Serving은 진행 중 Decode에 긴 요청을 넣어 동시 진행을 검증한다. |
| euichan0418/new-a-llm-scheduler `cc8c3ee` | hybrid 코어의 가용 범위·배치 불일치, 유휴 CPU에 대한 wakeup/dispatch 비용, FULL의 일상적인 elapsed 계측 비용 | architectural CPUID, sysfs의 물리/SMT 관계, online·allowed·cpuset, tiered idle CPU와 local/shared DSQ, weighted-vtime. 선택된 child만 SCHED_EXT. Lite는 정상 callback의 시간 합계를 줄이고 mask/tracking/migration/error 계측을 유지한다. |

Runtime의 explicit profile API는 공통 조상 `a9432639`, semantic routing은 `5219055a`를 통해 이미 통합 트리에 들어왔다. 이전 pool 후보 P는 donor `21537a5` 및 수정된 override null-padding guard를 검증했지만 A의 기본 빌드에는 반영되지 않았다. 기존 A에서 legacy scalar의 kernel 관측과 CPU phase 전달이 하나의 함수에 묶여 있었다. scheduler의 scx_simple 계보와 GGML/llama.cpp MIT 라이선스를 각 소스의 기존 표기대로 유지한다.

Runtime의 역사적 `b2ad09f` 이후 변경을 확인했다. `1746778`의 null context 처리와 `db33191`의 단일 marker TU를 반영했다. `a93fd7c`의 실제 제출 view 기준 및 진단/동기화 경계는 기존 Q4·E 연결과 충돌하지 않도록 유지했다. `2d51f37`를 포함한 Python serving harness를 공통 launcher의 manifest 및 고정 mask 검증 아래 연결했다. 현재 workspace의 `/slots`가 단일 원소 배열로 `next_token`을 내는 차이는 overlap 확인에서 정상적으로 읽도록 적응했다.

Runtime의 별도 연구 ref `65e2275`는 Mixed에서 Prefill budget을 제한하는 cap128과 64토큰 Flash Attention 경로를 제공한다. cap128은 Decode가 실제 제출 batch에 있는 경우에만 적용하는 설정으로 연결했다. head64는 CPU 전용 Qwen2의 12/2 heads, 128 head dim, 6/6 native worker, 실제 4개 연속 incumbent와 6,144-token newcomer, KV/ubatch 조건을 요구한다. context·server 분기의 충돌을 기존 phase/pressure/lifecycle과 맞춰 병합했다. AMD의 `m4`에서 실제 전용 kernel 호출을 두 source checkpoint에서 확인했고, cap128과 요청별 생성 ID가 일치했다.

Scheduler의 역사적 `a9be078` 이후 hybrid `c89b5fe`는 CPUID/sysfs 및 Intel E 배치를 검증하고, universal `45e704d`는 1,024 CPU descriptor, possible CPU slot과 실제 CPU ID 매핑, controller/selected mask, BPF object 동일성을 점검한다. 이를 공통 topology/loader 경로에 가져왔다. donor universal 자체의 기록은 STRICT_ACCEPTANCE FAILED와 네이티브 실행 미완료를 포함한다. 이번 결합도 별도 verifier/selected-child/실기 검증이 필요하다.

로컬 보존 archive의 Decode idle-handoff는 enqueue에서 첫 tier의 idle CPU를 찾는다. `locality-build-v2`의 이전 CPU 우선은 wakeup의 `select_cpu`에서 먼저 이전 CPU를 검사한다. 이전 locality 연구의 두 블록에서 조건별 효과는 −0.57%에서 +0.42%였다. 새 빌드에서는 각각 v2 유효 상태와 고정 envelope를 적용하는 선택 옵션으로 연결했고, 이식 후의 수치는 실기 실행 전이다. [복원 출처](evidence/model-free/locality-origin.json)

Native 구현에서 기존 spin 대기와 futex park를 별도 선택할 수 있다. `budget` 모드는 Prefill 4,096과 Decode 65,536 회전 예산을 적용하고 Mixed·Unknown은 기본 spin으로 처리한다. 실기에서 Prefill의 대기 호출과 동일 생성 ID를 확인했다. `hint`는 기존 진단 심볼만 있고 현 v2 scheduler에 소비 경로가 없어 공통 선택지에서 제외했다. OpenMP는 별도 barrier를 사용한다. Repack 버퍼의 큰 페이지 advisory는 양 backend에서 `madvise` 성공을 기록했으며, 실제 THP 할당량과 성능은 측정하지 않았다.

Fallback과 기본값은 기능 성능과 따로 평가한다. 이전 AMD 시험에서 P의 ambient point가 약 −1.65%였고 cpu25에서는 약 +1.05%였다. 이 자료는 pool을 선택 가능하게 두는 이유가 되지만 새 runtime의 성능 수치로 사용하지 않는다. 이전 Intel F6 약 +16%와 pressure A/F6 약 −5.28%는 사용자 제공 pilot 요약이며 이번 Intel 실기 증거가 아니다.
