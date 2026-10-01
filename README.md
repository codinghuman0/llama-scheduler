# llama-scheduler

CPU-only llama.cpp semantic phase-aware `sched_ext` Base Project

## 1. 프로젝트 소개

`llama-scheduler`는 Linux `sched_ext`를 이용해 CPU-only LLM scheduling을 연구하기 위한 공통 Base Project다. 수정된 semantic `llama-server`가 inference 중의 `PREFILL`, `DECODE`, `MIXED`, `UNKNOWN` phase를 제공하고, PID-specific `uprobe`가 이 정보를 eBPF의 TGID별 phase state로 전달한다. `sched_ext` callback에서는 선택된 `llama-server` worker가 실제로 실행될 때의 phase를 관측할 수 있다.

```text
modified llama-server
        |
        | semantic phase marker
        v
      uprobe
        |
        v
 BPF phase state
        |
        v
 sched_ext callbacks
```

현재 scheduler는 phase를 관측하고 계측할 뿐, CPU 선택, DSQ, queue order, vtime, slice 같은 scheduling 결정에는 phase를 사용하지 않는 neutral baseline이다. 따라서 성능을 개선하는 scheduling policy가 구현되었다거나 성능 향상이 입증되었다고 보지 않는다. 이 저장소는 팀원이 동일한 semantic phase 입력과 selected-child isolation 위에서 독립적인 policy 실험을 시작하기 위한 기반이다.

## 2. 현재 상태

| 항목 | 상태 |
|---|---|
| Semantic PREFILL/DECODE detection | 완료 |
| PID-specific uprobe integration | 완료 |
| sched_ext phase observation | 완료 |
| selected-child isolation | 완료 |
| reproducible setup/validation | 완료 |
| phase-aware scheduling policy | 미구현 |
| load-aware scheduling policy | 미구현 |
| performance improvement evaluation | 미수행 |

즉, `phase-aware observability`는 구현되어 있지만 `phase-aware scheduling policy`는 아직 구현되어 있지 않다.

## 3. Codex에 전달할 프로젝트 설명

새 Codex 세션에는 아래 내용을 그대로 전달할 수 있다.

```text
이 저장소는 CPU-only llama.cpp inference를 위한 Linux sched_ext scheduler 연구의 Base Project다.

modified llama-server가 semantic PREFILL/DECODE/MIXED/UNKNOWN phase를 제공하고,
PID-specific uprobe를 통해 eBPF의 TGID별 phase state로 전달된다.

sched_ext callback에서는 실제 selected llama-server worker의 phase를 관측할 수 있다.
현재 scheduling policy 자체는 phase 정보를 scheduling 결정에 사용하지 않는 neutral baseline이다.

이 저장소를 수정할 때:
- semantic phase input을 유지할 것
- selected-child isolation을 유지할 것
- llama-server workload는 normal user로 실행할 것
- privileged loader만 root로 실행할 것
- 한 번에 하나의 scheduling dimension만 변경할 것
- baseline validation을 깨뜨리지 말 것
- 성능 향상은 반복 실험 전에는 주장하지 말 것
- 실험 변경은 가급적 experiment/<name> 브랜치에서 진행할 것
```

## 4. 빠른 설치

지원 경로는 `sched_ext`, kernel BTF, 실행 중인 kernel과 일치하는 headers를 갖춘 Ubuntu x86-64 환경이다.

```bash
git clone https://github.com/codinghuman0/llama-scheduler.git
cd llama-scheduler

./scripts/bootstrap_ubuntu.sh --install-deps
```

bootstrap은 환경과 kernel capability를 검사하고, [config/versions.env](config/versions.env)에 고정된 semantic llama.cpp fork를 `.deps/llama.cpp-semantic`에 받아 CPU-only semantic server를 빌드한다. 이어서 scheduler와 BPF 구성 요소를 빌드하고 unprivileged tests를 실행한다.

현재 고정된 semantic revision은 `5219055a578fd741e029e81fefef6f3a5695086d`다. bootstrap은 kernel을 변경하거나 scheduler를 load하지 않으며 GPU dependency와 model도 설치하지 않는다. 시스템 dependency가 이미 준비되어 있다면 `--install-deps` 없이 실행할 수 있다.

## 5. Phase 연결 검증

호환되는 CPU-runnable GGUF model을 준비한 뒤 normal user shell에서 실행한다.

```bash
./scripts/validate_phase.sh \
    --model /path/to/model.gguf
```

이 검증은 semantic `llama-server -> uprobe -> BPF phase state -> sched_ext callback` 경로와 selected-child isolation을 한 번의 controlled inference로 확인한다. 내부적으로 `llama_scx_simple` loader만 `sudo`를 사용하며, `llama_scx_child`와 `llama-server`는 계속 normal-user process로 실행된다.

성공한 실행의 마지막에는 다음 결과와 run별 evidence directory가 출력된다.

```text
semantic_acceptance=PASS
result_dir=/absolute/path/to/result
```

GGUF model은 이 저장소에 포함되지 않으며 validation script가 자동으로 다운로드하지도 않는다.

## 6. 실험 시작

먼저 위 validation이 통과하는지 확인한 뒤 별도 브랜치를 만든다.

```bash
git checkout -b experiment/<name>
```

초기에는 `CPU selection`, `SMT avoidance`, `migration policy`, `DSQ policy`, `phase-dependent slice`, `load-aware scheduling` 중 하나처럼 한 번에 하나의 scheduling dimension만 변경한다. baseline validation과 semantic phase 입력을 유지하고, 반복 실험 전에는 성능 향상을 주장하지 않는다. 실험 원칙과 기록 항목은 [docs/EXPERIMENT_GUIDE.md](docs/EXPERIMENT_GUIDE.md)를 참고한다.
