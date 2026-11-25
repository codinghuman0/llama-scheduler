# AMD 로컬 검증과 재현

Ryzen 5 5500U에서 원본 모델 SHA256으로 수행했다. 새 경로마다 OpenMP와 native 실행 파일·DSO를 같은 canonical tree에서 빌드한다. 이 문서의 경로는 `new-a-workspace` 기준이다.

## Native 역할별 우선순위

```bash
model="$HOME/projects/model.gguf"
b=state/integration-v2/builds/native-local-recheck
out=state/integration-v2/native-priority-recheck
bash build.sh --build-dir "$b" --backend native --markers state-only --jobs 2
bash scripts/integration_v2.sh doctor --build-dir "$b" --resources amd-5-6 --policy phase-fixed \
  --profile integrated-runtime-research --batch-priority batch

cc -std=c11 -Wall -Wextra -Werror -I src/llama/ggml/include \
  tools/integration_v2/test_native_role_priority.c -L "$b/bin" -lggml-cpu -lggml-base \
  -o "$b/test-native-role-priority"
LD_LIBRARY_PATH="$PWD/$b/bin" timeout 20s "$b/test-native-role-priority"

for priority in normal batch; do
  bash run.sh --build-dir "$b" --model "$model" --resources amd-5-6 --policy phase-fixed \
    --profile integrated-runtime-research --generation-poll 0 --batch-poll 1 --strict-placement \
    --batch-priority "$priority" --state-log --fixtures heldout-1 --output "$out-$priority"
done
```

Graph 검사에서 `SCHED_BATCH`는 해당 풀의 graph 중에만 호출자에게 적용됐고, 성공과 abort 이후 모두 `SCHED_OTHER`로 복원됐다. 실제 서버에서 `--batch-priority batch`는 다섯 native 지속 worker에 정책 3을 적용했다. 나머지 서버 스레드는 기동 시 정책 0이었다. 두 arm의 워밍업·측정 각각 여덟 요청에서 요청당 16개 생성 ID가 모두 일치했다. [우선순위 검증 요약](evidence/role-priority-native-v1/priority-and-park-expanded.json)

## head64 특수 구조

```bash
out=state/integration-v2/m4-recheck
for mode in cap128 head64; do
  bash scripts/integration_v2.sh serve-bench --build-dir "$b" --model "$model" \
    --profile integrated-runtime-research --resources physical --policy phase-fixed \
    --mixed-prefill "$mode" --workloads m4 --tokens 128 --output "$out-$mode"
done
python3 -B tools/integration_v2/verify_head64.py "$out-cap128" "$out-head64"
```

`m4`는 Decode 네 요청이 각각 8토큰 이상을 낸 뒤 6,144토큰 Prefill을 더한다. 5 slots, native 6/6, AVX2/F16C, Flash Attention 및 지정 모델의 FP16 KV·attention 구조에서만 head64 경로를 열었다. CPU 커널이 처리한 layer 호출 수를 서버의 정상 종료 때 기록한다. 대조군은 0회, head64는 워밍업과 측정을 합쳐 3,584회였다. SSE의 Prefill progress 알림을 빼고 워밍업과 측정에서 각각 520개 실제 생성 ID를 비교해 전부 일치했다. 두 source checkpoint에서 동일한 검사를 통과했다. 성능 판정은 `INCONCLUSIVE`다. [첫 비교 요약](evidence/head64-native-v1/token-equality.json), [두 번째 비교 요약](evidence/head64-native-roles-v1/token-equality.json)

## Park와 pool 생성 실패 검사

```bash
bash run.sh --build-dir "$b" --model "$model" --resources amd-5-6 --policy phase-fixed \
  --profile integrated-runtime-research --state-log --batch-priority batch \
  --native-barrier park --barrier-phase budget --fixtures heldout-1 --output "$out-park"

cc -std=c11 -Wall -Wextra -Werror -I src/llama/ggml/include \
  tools/integration_v2/test_native_pool_failure.c -L "$b/bin" -lggml-cpu -lggml-base -ldl -pthread \
  -Wl,--export-dynamic -o "$b/test-native-pool-failure"
LD_LIBRARY_PATH="$PWD/$b/bin" timeout 20s "$b/test-native-pool-failure"
```

독립 park 설정에서 Prefill의 futex 대기 3,402회와 기본 설정과 같은 출력을 확인했다. Decode는 해당 방문에서 futex까지 진행하지 않았다. 모델 없는 검사에서는 두 할당 지점과 두 번째 worker 생성에 실패를 주입했다. 커널이 보는 남은 스레드 수와 이후 정상 생성·정리를 확인했다. [Park 결과](evidence/role-priority-native-v1/priority-and-park-expanded.json), [최종 조합 요약](evidence/pool-failure-v1/composition-proof.json)
