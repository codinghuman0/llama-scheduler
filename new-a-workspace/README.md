# NEW_A integration-v2

이 브랜치의 기본 진입점은 `build.sh`와 `run.sh`입니다. CPU 전용 `src/llama`에서 실행 파일과 라이브러리를 함께 빌드하고 소스, 빌드 옵션, ELF 및 실제 로드된 라이브러리를 확인합니다. 기본 수치 경로에는 R의 semantic Prefill reference가 포함됩니다. 모델은 팀에서 배포한 원본 `model.gguf`를 사용합니다.

## CPU 빌드와 확인

```bash
model="$HOME/projects/model.gguf"
build_dir=state/integration-v2/builds/portable-openmp
bash scripts/integration_v2.sh test
bash build.sh --build-dir "$build_dir" --backend openmp --jobs 2
bash scripts/integration_v2.sh doctor --build-dir "$build_dir" --profile integrated-runtime-research
bash run.sh --build-dir "$build_dir" --model "$model" --output state/integration-v2/smoke-01 \
  --profile integrated-runtime-research --state-log --fixtures heldout-1
```

`unified-conservative`는 기본 Linux 스케줄러와 보수적인 런타임 구성을 선택합니다. `integrated-runtime-research`는 semantic profile, 역할별 지속 풀, 호스트 자원 정책, state-v2를 조합합니다. `doctor`에서 실제 허용 CPU, worker 수, pool, 전송 방식과 빌드 정체를 확인합니다. 새 작업마다 별도 output 경로를 지정합니다.

- Intel i5-1240P에서 같은 소스를 빌드하고 결과를 수집하는 절차. [Intel handoff](experiments/team-integration-v2/INTEL_HANDOFF.md)
- SSE의 Prefill/Decode/Mixed 및 native CPU의 좁은 head64 진단 조건. [AMD 검증과 재현 명령](experiments/team-integration-v2/amd-local-validation.md)
- 허용된 커널에서 FULL/Lite와 phase-aware Decode handoff를 평가하는 수동 loader 절차. [커널 실행 절차](experiments/team-integration-v2/INTEL_HANDOFF.md#선택된-child의-커널-스케줄러)
- 지원 조합과 최신 검증 범위. [호환성 표](experiments/team-integration-v2/compatibility-matrix.md)

## 동결 실험 재현

이전 runtime과 결과는 원본 workspace에 보존되어 있습니다. 아래 위임 명령은 그 workspace의 기존 run 진입점을 사용합니다.

```bash
bash scripts/historical-frozen.sh "$HOME/projects/new-a-workspace" run --describe
```

예전 Intel 재현은 같은 위임 명령에서 `intel check`를 사용합니다. 새 `run.sh --help`와 `build.sh --help`는 integration-v2의 인수만 표시합니다. 기존 보관 자료는 게시 기준 커밋 `441b3b4`의 README와 `experiments/`에 기록되어 있습니다.
