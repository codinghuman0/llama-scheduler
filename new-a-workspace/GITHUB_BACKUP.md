# GitHub에 올릴 범위

이 연구의 작업 폴더는 `new-a-workspace/`다. 정리 시점의 터미널 기준 디렉터리는 그 부모인 `/home/codinghuman/projects`이며, `new-a-workspace` 자체는 아직 Git 저장소가 아닌 일반 폴더다.

대상은 [codinghuman0/llama-scheduler](https://github.com/codinghuman0/llama-scheduler)다. 2026-11-23 확인 당시 공개 저장소이며 `main`에는 기존 neutral scheduler base 프로젝트가 있다. 기존 이력을 유지하고 그 아래 `new-a-workspace/` 하위 폴더로 추가한다. 작업용 checkout은 `/home/codinghuman/projects/llama-scheduler-publish`이며 로컬 원본 폴더/모델/동결 runtime은 보존한다. 사용자가 Intel 검증 후 commit/push를 명시적으로 요청했다.

## 포함하는 파일

- `src/llama/`의 runtime 소스, 라이선스, `scheduler/`의 C/BPF/header 소스.
- 설정, 빌드·실행·분석·재현 스크립트.
- 실험 protocol/fixture/order/identity, 요약 보고서와 원시 측정 JSON/JSONL/log.
- R/P/E 관련 overlay/patch, 최신 통합 감사의 source excerpts와 commit patch.
- 빌드 입력·옵션·명령·해시 기록. `build-cpu/`와 `build-server/` 전체를 무조건 제외하지 않는다.

`src/llama/tools/ui/frozen-ui.cpp`는 약15 MiB지만 오프라인 UI를 포함해 빌드하는 데 필요한 소스라 유지한다. `scheduler/include/vmlinux.h`도 기록된 BPF source/build 입력으로 유지한다. 작은 수치 진단 자료(`*.f32`)와 실제 측정 로그를 단순 캐시로 취급하지 않는다.

## 로컬에만 남기는 파일

- `models/model.gguf`, `runtime/`와 각 후보의 runtime 바이너리.
- `archive/legacy.tar.xz`와 생성된 ZIP 등의 재포장 파일.
- `.o`, `.a`, `.so*`, CMake/obj 캐시, 확장자 없는 loader/진단 실행파일.
- 중복 `reference-original/`, 감사 중 추출한 전체 역사 source snapshot과 약50 MiB archive index. 필요한 발췌·patch·계보/해시는 포함한다.
- measurement lock/실행 상태, 개인 환경 파일, 도구 캐시와 원래 요청 전문.

**파일을 삭제한 것이 아니다.** `.gitignore`로 Git 업로드 대상에서 제외했다. 모델과 최선 A runtime은 로컬에 그대로 남는다. `.gitignore`는 이미 추적 중인 파일을 Git에서 제거하지 않으므로 추후에는 아래 점검 도구로 tracked-ignored 파일도 확인한다.

## 업로드 전 점검

Git 초기화 전에도 실행할 수 있다. 임시 Git metadata로 실제 `.gitignore` 규칙을 해석하며 stage/commit/push나 원본 삭제를 하지 않는다.

```bash
cd /home/codinghuman/projects/new-a-workspace
python3 -B tools/git_upload_audit.py \
  --output maintenance/github-prep-20261123/upload-manifest.json
```

출력은 포함/제외 파일 수와 비압축 용량, 큰 파일, 포함돼야 할 소스/증빙, 빠져나온 실행 바이너리 및 일반적인 credential 패턴의 위치다. credential 패턴 검사는 전체 보안·개인정보 감사를 뜻하지 않는다. 보고서·원시 증빙에는 당시 절대 경로와 머신/프로세스 식별자가 남아 있으며 이 정리에서 역사 기록을 편집하지 않았다.

## Git 백업과 전체 실행 백업의 차이

Git clone만으로 모델·동결 runtime·legacy archive가 복원되지는 않는다. 기존 full-workspace 검증, frozen-runtime 실행, 과거 archive 조회에는 로컬 보존 파일이 필요하다. 모델은 별도로 준비하고 동결 runtime은 기존 hash가 일치하는 보존본을 사용해야 한다. 생략된 파일을 임의 재빌드로 대체하고 byte identity를 주장하지 않는다.

최종 A는 `experiments/r-pool-validation-v1/candidates/A/runtime/`다. 기존 `run.sh`의 기본 `runtime/NEW_A`는 pre-R 구성으로, 최종 A_L과 다르다. 최신 상태는 [감사 요약](experiments/final-team-integration-audit-v1/integration-summary.ko.md)을 참고한다. 원래 README/GOAL_STATE의 역사적 설명은 이 Git 정리에서 덮어쓰지 않았다.

전체 runtime 없이 Git에 포함된 발췌 수치를 재계산할 수 있다:

```bash
python3 -B experiments/final-team-integration-audit-v1/code/recalculate_packaged.py
```

이 명령은 모델 추론이 아니다. 반면 기존 full audit의 archive/Git-history 조사 보조도구는 제외한 로컬 archive/index를 요구할 수 있다. 모든 보조도구가 Git clone만으로 동작한다고 주장하지 않는다. 빌드 시 필요한 `state/.measurement.lock`도 Git에서는 제외된다. 새 [Intel 실행 스크립트](scripts/intel_experiment.sh)는 필요한 state와 lock을 직접 생성한다. 사용법과 정확한 A 재빌드 recipe는 [Intel 안내](docs/INTEL_EXPERIMENT.ko.md), 문제 발생 시에는 [Codex 전달용 프롬프트](docs/INTEL_CODEX_HANDOFF.ko.md)를 따른다. 기본 Linux의 B0_L/F6_L/A_L 비교이며 Intel 커널 scheduler 검증을 대체하지 않는다.
