# NEW_A: 독립된 CPU runtime 연구 작업 폴더

기존 6개 저장소/실험 폴더를 단순 이동한 구조를 없애고, 실행·수정에 필요한 파일을 하나의 프로젝트로 통합했습니다. 활성 Git worktree, 외부 공통 `.git`, 옛 실험 디렉터리, 옛 절대 경로에 대한 실행 의존성이 없습니다. 원본 `../llama.cpp`와 `../model.gguf`의 내용은 보존했습니다. 모델은 내부 `models/model.gguf`에도 하드링크로 두어 외부 경로 의존성과 추가 복사를 없앴습니다.

```text
new-a-workspace/
├── src/llama/       통합 소스 1벌: Q4 exact CPU + llama graph + phase server
├── models/          model.gguf 원본과 데이터 공유; 외부 경로 없이 사용 가능
├── runtime/         기존 동결 B0, B1, NEW_A 바이너리 (동일 파일은 hardlink 공유)
├── scheduler/       observe 정책, BPF, selected-child/guarded loader, 소스·header
├── config/          상대 경로 실행 설정, scheduler identity, package manifest
├── tools/           실행·검증·보관 자료 조회 도구
├── evidence/        성능 요약, 출력 차이 진단, 다음 연구 계획
├── archive/         과거 자료와 Git 이력의 중복 제거 압축본 1개
├── state/           같은 inode의 measurement lock; 이후 실행 로그
├── maintenance/     이번 통합·삭제·검증 기록 (일회성 작업 스크립트 포함)
├── run.sh
└── build.sh
```

## 바로 확인하기

```bash
cd /home/codinghuman/projects/new-a-workspace
python3 -B tools/verify.py --archive
bash run.sh --describe
```

위 명령은 모델 추론이나 BPF 로드를 하지 않습니다. `verify.py`는 파일 hash와 runtime 라이브러리 연결을 확인합니다.

일반 Linux scheduler에서 현재 NEW_A runtime을 실행하려면:

```bash
bash run.sh --runtime NEW_A --scheduler linux
```

기본 모델은 이 폴더 안의 `models/model.gguf`입니다. 원본과 같은 inode의 일반 파일이며 symlink가 아닙니다. 원본 경로를 읽을 필요 없이 사용할 수 있고, 폴더를 다른 파일시스템으로 복사하면 모델 데이터도 함께 복사됩니다. 두 경로 중 하나에서 모델 내용을 수정하면 공유된 원본도 바뀌므로 모델은 읽기 전용으로 취급합니다. 다른 모델은 `--model /absolute/path/model.gguf`로 지정합니다. 기본 포트는 51337, 실행 제한은 600초이며 Ctrl-C로 종료할 수 있습니다. `--port`, `--timeout`으로 변경할 수 있습니다. 요청은 사용자가 server API로 보냅니다. 프로그램이 임의 benchmark나 생성 요청을 실행하지 않습니다.

현재 동결 설정은 AMD 5500U의 6개 물리 코어에 대응하는 CPU `0,2,4,6,8,10`입니다. 실제 허용 CPU와 물리 코어 중복을 매번 검사합니다. 다른 머신은 해당 CPU 구성이 맞지 않으면 실행을 거부합니다. `--cpus`로 6개 물리 코어를 지정할 수 있지만, 다른 장비에서 기존 성능이 재현된다는 뜻은 아닙니다.

기존 observe scheduler를 함께 실행하려면 사용자의 터미널에서:

```bash
sudo -v
bash run.sh --runtime NEW_A --scheduler observe
```

서버는 일반 계정으로 실행하고 loader만 기존 권한 범위에서 sudo를 사용합니다. 기존 selected-child 등록, 고정 affinity, PID identity 기반 cleanup, loader 생존/worker policy 감시를 유지합니다. 새로운 loader는 자신 옆의 BPF object를 찾습니다. 정책/BPF bytes는 그대로이며 파일 경로 처리만 바뀌었습니다. **이번 통합에서는 loader 컴파일·도움말만 검사했으며 BPF attach는 실행하지 않았습니다.** Kernel/BTF가 기록과 다르면 실행을 거부합니다. 임의 전역 scheduler 모드를 추가하지 않았습니다.

## 소스와 빌드

`src/llama`는 기존 최선 runtime을 이루던 CPU, llama graph, server 소스를 합친 독립된 일반 디렉터리입니다. `.git` pointer가 없습니다. 고정 UI asset도 포함해 frontend 다운로드나 Node 빌드 의존성을 제거했습니다. 원본 및 대체 후보 소스, diff, Git database는 과거 압축본에 있습니다.

```bash
bash build.sh
```

새 빌드는 `build/bin`에만 생성하며 `runtime/`의 검증된 바이너리를 덮어쓰지 않습니다. 필요한 시스템 C/C++ compiler, CMake, OpenMP/OpenSSL 등은 시스템 의존성으로 남습니다. 이는 폴더 간 의존성을 제거한 것이며 모든 시스템 라이브러리를 정적 링크한 패키지는 아닙니다. **통합 소스의 전체 재빌드·token equality·성능 확인은 이번 정리 범위에서 실행하지 않았습니다.** 새 빌드는 그 검증을 거친 뒤 채택해야 합니다. 동결 runtime은 파일 hash로 기존과 동일함을 확인했습니다.

scheduler loader를 별도 재빌드하는 명령은 `bash tools/build_scheduler.sh`입니다. 기존 loader를 자동 교체하거나 BPF를 자동 로드하지 않습니다.

## 기존 결과 해석

`runtime/B0`는 연구 시작 revision의 동결 비교 runtime, `runtime/B1`은 기존 누적 최적화, `runtime/NEW_A`는 선택된 Prefill pressure runtime입니다. 기본 Linux 실행을 과거 `C + 연구 scheduler` 확인 실험과 동일한 구성으로 부르지 않습니다.

[evidence/performance-result.md](evidence/performance-result.md)의 과거 throughput 개선과 [evidence/diagnosis-state.md](evidence/diagnosis-state.md)의 출력 차이·미해결 품질 범위를 함께 보세요. 이번 폴더 통합으로 새 성능 향상을 주장하지 않습니다. [다음 작업](evidence/NEXT_STEP.md)은 Q4 Prefill 누적 순서 호환 후보 검증입니다.

## 과거 자료

`archive/legacy.tar.xz`는 내용 SHA256별 blob과 경로 manifest로 이루어진 독립 압축본입니다. 연속 압축으로 비슷한 파일 간 중복도 줄였습니다. Python bytecode와 확인된 컴파일 중간 object만 제거하고, 실행 바이너리·BPF object·소스·Git 이력·원시 결과는 유지했습니다. 삭제 항목은 manifest에 `removed_build_cache`로 명시되어 있습니다. 동일 파일은 한 번만 저장합니다. 기존 압축본 32개는 내부 파일을 풀어 같은 방식으로 합쳤으므로 옛 압축 컨테이너 자체의 byte identity는 보존하지 않았습니다. 원래 SHA는 역사 기록으로 남기고, 각 내부 파일과 고유 소스·원시 결과·Git 이력은 보존·검증했습니다. 과거 기록에 등장하는 절대 경로는 실행 의존성이 아니라 기록입니다.

```bash
python3 -B tools/archive.py list new-a-performance/phase-scheduling-study-v1/runs/
python3 -B tools/archive.py get new-a-performance/output-divergence-diagnosis-v1/next-step.md /tmp/new-a-next-step.md
python3 -B tools/archive.py extract new-a-performance/output-divergence-diagnosis-v1 /tmp/new-a-diagnosis
```

출력 경로는 새 경로여야 합니다. 압축본의 내부 경로는 `원래압축파일!/내부파일` 형식입니다. 추출은 파일만 복원하고 옛 symlink를 자동 활성화하지 않습니다. 과거 전체 runner 재실행에는 기록된 절대 경로를 검토해 새 실행 사본을 준비해야 합니다. 이 절차는 현재 `run.sh`의 실행 의존성과 분리됩니다.

정리 기록: [기존 통합](maintenance/compact-20261122/report.md), [외부 모델 의존성 제거와 추가 용량 정리](maintenance/self-contained-20261122/report.md).

과거 명령·로그의 절대 경로는 당시 실행 증빙이므로 그대로 남겼습니다. 현재 진입점 `run.sh`, `build.sh`, `tools/verify.py`, `tools/archive.py`는 폴더 위치에서 경로를 계산합니다. 과거의 일회성 준비 스크립트는 재실행 진입점이 아닙니다. 이동 시에는 `new-a-workspace` 폴더 전체를 복사하세요.

