# 독립 프로젝트 통합 및 대량 정리

완료: 이전 6개 폴더를 제거하고, 코드·runtime·scheduler·도구가 함께 있는 독립된 `new-a-workspace` 프로젝트로 재구성했다. 단순히 과거 폴더를 상위 폴더에 모아 둔 구조를 대체했다.

## 실제 용량

- 시작 시 workspace는 약 2.5 GiB였다.
- 현재 할당량: **0.949 GiB**.
- 파일시스템 사용자 가용 공간의 순증가: **1.568 GiB** (1,683,431,424 bytes).
- 현재 사용자 가용 공간: **2.859 GiB**.
- 현재 압축 보관본: 848.19 MiB. 오래된 raw·소스·Git history까지 보존하기 때문에 이 용량은 의도적으로 남아 있다.

동일 파일시스템 이동량이나 hardlink 수를 회수량으로 세지 않았다. 순회수량은 압축본 생성 전후 df 가용량으로 계산하므로 새 패키지와 감사 기록의 점유량까지 반영한다. 동시 시스템 쓰기에 따른 작은 변동은 가능하다.

## 삭제·통합 내역

다음 활성 폴더는 모두 제거했다: `llama.cpp-lightweight`, `new-a-llm-scheduler`, `new-a-lab`, `new-a-performance`, `new-a-runs`, `llama-ngram-shortcut`.

- 전체 조사·보관 검증 후, 명시적 allowlist의 파일/링크 71,173개를 개별 unlink했다. 비어 있는 디렉터리만 제거했다.
- 9개 worktree와 공통 `.git`의 활성 의존성을 없앴다. Git database 자체는 압축본 안에 보존되어 있지만 현재 실행이나 소스 수정에 필요하지 않다.
- 최선 구성의 CPU(Q4 exact), llama graph, phase-aware server를 `src/llama` 하나에 합쳤다. 변경한 overlay와 출처 hash는 `source-provenance.json`, UI asset 연결 수정은 `offline-ui.patch`에 기록했다.
- B0/B1/NEW_A 동결 runtime 60개 경로는 내용이 같은 파일을 공유하여 17개 고유 payload만 저장한다. 바이너리 bytes는 모두 그대로다.
- 오래된 builder 중간 산출물·원시 결과·실패 기록·보관본·원본 스크립트는 보관용 ZIP의 SHA256별 blob으로 합쳤다. 중복 파일은 한 번만 저장한다.
- 기존 압축본 32개는 내부 파일을 이 구조에 편입했다. 원래 compressed container bytes 자체는 제거했으며, 과거 container SHA는 역사 기록으로 남긴다. 이를 옛 ZIP/tar 파일의 byte identity가 보존된 것으로 주장하지 않는다.
- 내부 `llama.cpp`, `model.gguf` 호환 symlink와 이전 정리용 `workspace.py`도 제거했다. 상위 실제 원본에는 손대지 않았다.

## 의존성 제거

현재 `run.sh`와 도구는 자신의 위치로 package root를 정한다. 외부 legacy checkout이나 `new-a-lab` 경로를 import하지 않는다. runtime DSO는 각 runtime 디렉터리에서 로드한다. 원본 binary의 역사적 RUNPATH를 다시 쓰지 않고 명시적인 LD_LIBRARY_PATH로 연결한다.

scheduler loader는 `/proc/self/exe`를 기준으로 옆에 있는 `full_object.bpf.o`를 찾는다. 기존 정책·BPF bytes·selected-child 등록·guard·cleanup을 유지했다. loader 파일 경로 수정은 `loader-path.patch`로 분리했고 일반 계정 컴파일과 도움말을 검사했다. 실제 BPF attach는 실행하지 않았다.

전체 소스의 웹 UI build/download 의존성은 기존 생성 asset으로 대체했다. 시스템 compiler, CMake, OpenMP/OpenSSL/libbpf 등은 일반 시스템 의존성으로 남아 있다. 모델은 명시적으로 보존한 상위 `model.gguf`를 쓰며 `--model`로 다른 경로를 지정할 수 있다. 원본 `llama.cpp` 폴더를 참조하지 않는다.

과거 runner는 archive 안의 역사적 코드다. 그 전체 실험을 다시 실행하려면 별도 추출 및 옛 절대 경로 검토가 필요하다. 이는 현재 runtime 실행의 legacy 폴더 의존성을 남긴 것이 아니다.

## 검증

- 압축본 CRC 및 고유 blob 35,190개 SHA 검증 PASS; 원래 71,178개 파일/링크와 확장 archive member를 합한 122,571개 경로 기록.
- 과거 파일 하나를 실제 추출해 현재 요약 파일과 byte equality 확인 PASS.
- 삭제 전후 원본 `llama.cpp` 전체 및 model 3,265개 regular file hash PASS. 모델 SHA는 `f3bdf9cf31dee4b57ae4e455a1cb0d01b5c2c1b50d72d3112141c195506c2840`.
- B0/B1/NEW_A hash·`ldd`·`--help` PASS. 실제로 다른 임시 디렉터리에 runner/config/runtime을 배치한 검사도 PASS. 과거 폴더는 삭제된 상태였다.
- 새 package 3,087개 파일 hash/mode 및 라이브러리 closure 검사는 `final-verification.json`에 기록했다.
- 같은 measurement lock inode 800700을 삭제와 사후 검증 동안 유지했고 `state/.measurement.lock`로 옮겼다.
- 모델 추론, full llama rebuild, token equality, 성능 재측정, scheduler attach는 NOT_RUN. 통합 소스의 새 빌드가 동결 runtime과 같다고 주장하지 않는다. 다음 빌드는 별도 `build/bin`에 생성하고 검증한 뒤 채택해야 한다.

## 안전 검사와 권한

첫 삭제 실행은 자동 안전 검사에서 원본과 같은 이름의 내부 symlink를 포함한 목록 때문에 거절됐다. 실행 전 차단이었으며 삭제는 발생하지 않았다. `safety-scope-proof.json`으로 실제 원본이 workspace 바깥에 있음을 확인하고, 삭제 루프를 6개 legacy root로만 제한한 뒤 승인된 실행으로 완료했다. 내부 alias는 symlink임과 원본 inode 보존을 별도로 검사한 뒤 unlink했다. 추가 사용자 승인 요청이나 권한 우회 없이 안전한 범위로 수정했다. sudo, BPF 로드, 시스템 변경, 관련 없는 프로세스 종료는 하지 않았다.

## 사용 및 재개

```bash
cd /home/codinghuman/projects/new-a-workspace
python3 -B tools/verify.py --archive --model ../model.gguf
bash run.sh --describe
bash run.sh --runtime NEW_A --scheduler linux
```

실제 연구 scheduler를 쓰는 터미널 실행은 README의 `sudo -v` 절차를 따른다. 현재 핵심 연구 이슈인 Q4 Prefill 출력 차이는 해결한 것으로 바꾸지 않았다. 다음 작업은 `evidence/NEXT_STEP.md`다.

`pack_legacy.py`, `prepare_package.py`, `retire_legacy.py`는 이번 일회성 작업 기록이다. 삭제 전 allowlist JSON은 공간을 줄이기 위해 `snapshot-before.json.gz`로 무손실 압축했고 원문 SHA를 `allowlist-storage.json`에 기록했다. 이 작업 스크립트를 재실행하지 않는다.
