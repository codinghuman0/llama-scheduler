# Source attribution

- Base runtime and GGML, including local R/E adaptations, retain the original MIT
  license in `../../src/llama/LICENSE`. The existing ggml copyright notices apply.
- Runtime donor `hsju2021/llama.cpp-fork` at the explicit profile lock in
  `sources.lock.json` contributed the server threadpool owner, state-v2 publisher
  ABI, separate marker translation unit and CPU serving harness. Server wiring,
  CPU bridge separation, ownership guards and the serving adapter are integrated
  changes. The mixed-prefill budget and head64 Flash Attention route are
  adapted from donor ref `65e2275`.
- Scheduler donor `euichan0418/new-a-llm-scheduler` at the locked main contributes
  the CPUID/Portable/Hybrid logic, universal guard and object attestation,
  local/shared DSQs, weighted-vtime and Lite instrumentation design. Preserve
  GPL-2.0 and the derived scx_simple author notices in source. Original donor
  NOTICE and GPL-2.0 are in `../../tools/integration_v2/topology/`.
- The state receiver, mode selection and launcher are integration adapters.
  The 32-byte marker wire layout comes from the MIT runtime side; the BPF
  receiver compiles it with the GPL-2.0 scheduler.
- Decode idle handoff and previous-idle locality come from the local GPL-2.0
  scheduler experiments. The locality snapshot was restored from the frozen
  archive. Its path and SHA are in `evidence/model-free/locality-origin.json`.
- Historical R/P/E evidence and published pins are kept as attribution and
  validation inputs. A source lineage overlap is not a new contribution claim.
