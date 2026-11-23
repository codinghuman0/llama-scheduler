# 디스크 정리 및 폴더 통합 결과

상태: 파일 작업 및 보존 검사 PASS. 최신 사용자 답변에 따라 삭제는 빌드 캐시·임시 파일로 제한했다. 첨부 지시의 경로 이동 금지와 뒤이은 명시적 “두 폴더와 모델 하나” 요청은, 후자의 폴더 통합을 허용하되 기존 증빙 바이트를 보존하는 것으로 적용했다.

## 최종 구조와 역할

`/home/codinghuman/projects`에는 다음 세 항목만 남았다.

```text
projects/
├── llama.cpp/          원본: 내용·빌드·.git 및 dirty 변경 유지
├── model.gguf          원본: 위치·내용 유지
└── new-a-workspace/    나머지 여섯 폴더와 새 안내/검증 도구
```

| 기존 폴더 | 현재 위치 | 처리 |
| --- | --- | --- |
| `llama.cpp-lightweight` | `new-a-workspace/llama.cpp-lightweight` | 보존·이동 |
| `new-a-llm-scheduler` | `new-a-workspace/new-a-llm-scheduler` | 보존·이동 |
| `new-a-lab` | `new-a-workspace/new-a-lab` | 보존·이동 |
| `new-a-performance` | `new-a-workspace/new-a-performance` | 보존·이동 |
| `new-a-runs` | `new-a-workspace/new-a-runs` | 보존·이동 |
| `llama-ngram-shortcut` | `new-a-workspace/llama-ngram-shortcut` | 보존·이동 |

폴더별 역할은 통합 폴더의 [README](../../README.md)와 아래 분류를 참고한다.

- KEEP_ACTIVE: lightweight 공통 Git, 9개 worktree, scheduler 수정 중인 소스, B0/B1/E 실행 파일·DSO, 다음 Q4 Prefill 후보의 소스·parent `.o/.a`·생성 header/UI, selected-child loader/probe/BPF 및 measurement lock.
- KEEP_EVIDENCE: 성공·실패·중단 원시 결과, logits, 분석 코드, protocol/identity/patch, 진단·감사 ZIP, 제출 tar, 과거 복원 보관본.
- CMakeCache와 configure 기록은 컴파일 설정 증빙이다. 남은 작은 compiler dependency 파일은 generated `build.make`가 include한다. 확장자만 보고 삭제하지 않았다.
- 이전 656개 보호 목록뿐 아니라 조사 시점의 모든 파일 74,123개와 링크 287개를 별도로 기록했다. 현재 다음 계획은 B0 누적 순서와 호환되는 Q4 Prefill 후보 검증이며 새 R/pool 후보는 발견되지 않았다.

## 삭제와 실제 공간

SAFE_DELETE는 아래 하나뿐이다. 삭제 전 `cleanup-plan.json`에 경로·inode·hash·근거를 고정했다.

`new-a-performance/combined-cpu/ambient-pilot-v1/block-4/LINUX_COMBINED/cleanup.json.tmp`

종료된 interrupted pilot의 0바이트 임시 파일이다. 이웃 로그·명령·raw 및 실패 기록은 전부 유지했다. **삭제된 데이터/할당 블록은 0바이트이며, 큰 회수 항목은 없다.** 재생성 가능한 큰 캐시가 이미 정리된 상태에서 남은 실질 파일은 재현 입력 또는 증빙이었다.

`llama-ngram-shortcut` 전체는 삭제하지 않았다. private 원격 main과 로컬 commit `8c7cb6a6cd3f805a151fc2856084e0f5720583dc`, 트리 및 530개 tracked blob 일치를 확인했지만, 최신 답변이 캐시·임시 파일로 범위를 좁혔으므로 약 94.72 MiB의 파일 할당량을 가진 저장소를 보존했다. 로컬 validation 3개도 유지했다. 이 수치는 파일 st_blocks 합이며 디렉터리·Git 파일 포함 방식에 따라 du의 약 97 MiB와 다르다.

- 최초 전체 조사 시 사용자 가용 공간: 1,392,742,400 bytes.
- 삭제 직전: 1,389,105,152 bytes.
- 삭제 직후 관측: 1,389,084,672 bytes.
- 통합·첫 검증 직후 관측: 1,388,249,088 bytes.
- 보고서 작성 시 가용 공간: 약 1.29 GiB (1,387,933,696 bytes).
- 최초 조사 대비 관측 차이: -4,808,704 bytes. 새 감사 기록과 같은 파일시스템의 다른 쓰기가 포함되므로 이를 삭제 효과로 해석하지 않는다. **양의 공간 회수는 없었다.**

동일 파일시스템 rename은 용량 회수로 계산하지 않았다. inode 중복을 고려했고 hardlink 그룹 294개를 발견했다. reflink 공유 extent는 추정하지 않았다. 프로젝트 안의 별도 mount는 없었다. 프로젝트 밖의 캐시/임시 파일은 정리하지 않았다.

## 보존 및 연결 검증

- 임시 파일 하나를 제외한 정규 파일 74,122개, 링크 287개 검사 PASS. 모든 남긴 일반 파일의 SHA256을 확인했다. Git 경로 메타데이터 예외 18개를 제외하면 size/mode/mtime/inode도 일치했다.
- 원본 `llama.cpp` 전체와 `.git`, 기존 dirty `src/llama-context.cpp` 그대로. 모델 SHA256: `f3bdf9cf31dee4b57ae4e455a1cb0d01b5c2c1b50d72d3112141c195506c2840`.
- 13개 Git checkout의 HEAD/ref/staged/unstaged/untracked/ignored/submodule 상태 보존. `git worktree repair`로 이동한 9개 worktree의 양방향 포인터 18개만 변경했다. 공통 object database는 그대로 유지했다.
- 절대 symlink 133개는 새 위치의 같은 파일을 가리키는 상대 링크로 바꿨다. 기존 링크 287개 모두 정상이다.
- 기존 보호 manifest의 656개 hash 재확인 PASS. 기존 manifest·sealed 파일 수정 없음.
- B0/B1/C/C-off artifact hash와 별도 경로 변환 설정의 `ldd` 확인 PASS. 바이너리를 고치지 않았으며 기존 arm별 LD_LIBRARY_PATH의 위치만 매핑했다. 해당 설정의 내부 llama/ggml/mtmd DSO는 해당 runtime/bin으로 해석된다.
- 기존 진단 패키지 `reproduce.sh verify` PASS. 모델 추론·재빌드·BPF 로드는 NOT_RUN.
- 삭제 전부터 사후 검증까지 기존 measurement lock inode 800700을 독점 유지했다. 부모 rename 뒤에도 동일 inode. 새 위치는 `new-a-workspace/new-a-runs/.measurement.lock`; 옛 경로를 재생성하지 않았다.
- 실제 실험/build/loader 충돌 없음, sched_ext disabled. `scx_enable_helper`는 PPid 2·빈 cmdline의 커널 스레드였다. 첫 보수적 preflight 중단 기록을 보존하고 확인 후 진행했다. 사용자 session systemd/sd-pam 두 프로세스와 다른 UID의 일부 /proc 정보에는 접근 제한이 있다. 이를 모든 시스템 FD를 조사했다는 주장으로 바꾸지 않았다. 프로세스를 종료하지 않았다.

## 다음 연구 준비와 한계

모델, 동결 runtime, 현재 및 다음 소스/parent 입력, 원시 자료는 남아 있다. 하지만 공간 확보가 없으므로 약 1.29 GiB의 여유가 대형 새 빌드에 충분하다고 판단할 수 없다.

옛 sealed 보고서와 Python/shell/CMake/linker 명령에는 이전 절대 경로가 남아 있다. 그대로 실행하지 말고 새 실행 사본에서 경로를 옮겨야 한다. `relocated-cases.json`은 별도 경로 전용 설정 사본이며 기존 freeze/identity를 대체하지 않는다. C의 scheduler 적용 여부나 성능 재현은 이번에 검증하지 않았다. 원본 바이너리 RUNPATH는 보존했으므로 각 runtime의 새 LD_LIBRARY_PATH를 사용해야 한다. 새로운 permission 상태나 Intel 검증도 조사하지 않았다.

새 작업의 첫 단계는 아래 보존 확인 후, next-step.md의 Q4 Prefill 호환 후보를 위한 **별도 실행/빌드 사본** 경로 준비다. 모든 runner가 새 lock 경로를 공유하도록 해야 한다. 모델·품질·기존 성과에 대한 새로운 결론은 만들지 않았다.

```bash
cd /home/codinghuman/projects/new-a-workspace
python3 -B workspace.py verify
python3 -B workspace.py path /home/codinghuman/projects/new-a-lab/llama-phase-batch-q4-exact-v1
python3 -B workspace.py config B1
```

## 기록

`cleanup-plan.json`, `cleanup-result.json`, `preservation-before.json`, `preservation-after.json`, 전체 `file-inventory-before.jsonl.gz`, `git-before/after.json`, `git-worktree-repair.json`, `runtime-library-check.json`, `relocated-cases.json`, `process-check.json`, `preflight-1-*`, `reusable-verifier-check.json`을 함께 보존한다. `execute_cleanup.py`는 이 작업의 일회성 수행 기록이며 재실행용이 아니다.
