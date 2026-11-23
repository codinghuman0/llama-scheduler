# Persistent pool selective-port review

상태: **WAITING_NUMERICAL_BASELINE**. [검토 결과](result-summary.md), [통합 차이](integration-delta.md), [과거 pool 실험](pool-history.md), [baseline 정체](baseline-identity.md).

현재 E 위의 pool-only overlay와 모델 없는 테스트다. 검증된 runtime에 설치하지 않았다. 원본 E와 후보 모두에서 HINT OFF 전체 context가 컴파일되지 않는 기존 문제를 보존·공개한다. 새로운 모델 처리량 결과는 없다.

new-a-workspace 루트에서:

```bash
bash experiments/persistent-pool-port-v1/reproduce.sh verify
bash experiments/persistent-pool-port-v1/reproduce.sh model-free --output experiments/persistent-pool-port-v1/results/my-check-001
python3 -B experiments/persistent-pool-port-v1/code/analyze.py
```

출력 폴더는 새 경로여야 한다. 일반 계정에서 실행하며 sudo, 모델, BPF를 사용하지 않는다. 실제 동결 NEW_A DSO로 owner/graph/ABI 검사와 원본·후보 context syntax 검사를 수행한다. 고정 CPU envelope가 사용할 수 없는 머신은 이 재현 조건을 만족하지 않는다. 전체 server 빌드나 모델 기능 검사 명령이 아니다. 적용 가능한 검사 통과 시 종료 코드 0이며 inherited HINT OFF failure는 결과 JSON에 별도로 남는다. 예기치 않은 실패는 0으로 처리하지 않는다.

ZIP을 다른 곳에 풀었다면 workspace를 명시한다:

```bash
bash reproduce.sh --workspace /home/codinghuman/projects/new-a-workspace verify
bash reproduce.sh --workspace /home/codinghuman/projects/new-a-workspace model-free --output /tmp/pool-check-001
```

source, compile commands, stdout/stderr, 실패 결과를 보존한다. 완료·중단 시 자신의 child process만 정리하며 생성된 ELF는 hash 기록 후 삭제한다. 완료된 실제 명령은 results/*/commands.json과 results/reproduce-1/*/commands.json에 있다. code/initialize.py, prepare_overlay.py 및 code/recorded/는 초기 준비/과거 시도의 기록이며 재현 진입점이 아니다.

method.patch는 정확한 overlay를 재구성하기 위한 변경 파일이다. `patch --dry-run`으로 현재 통합 E 소스에서 적용 가능함을 확인했다. 보호 소스에 직접 적용하지 않는다. 현재 모형 독립 검증은 overlay source를 직접 컴파일한다. 승인된 R 위의 실제 server 빌드·모델 검사는 아직 허용되지 않았다.

ZIP에 모델 가중치, runtime binary, 전체 build tree, credentials를 넣지 않는다. REVIEW-MANIFEST.json은 패키지 member hash/mode를 담고, ZIP hash 및 검증 결과는 ZIP 옆 sidecar에 있다. ZIP만으로 전체 llama.cpp/runtime을 새로 재빌드하는 백업 패키지는 아니다.

[다음 단계](next-step.md)는 R 수치 호환 baseline 검증 하나다.
