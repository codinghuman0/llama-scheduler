# 기능별 통합·기여 감사표

JSON/CSV와 동일한 34개 행이다. 출처·채택·실행·성능은 독립 축이며 퍼센트나 점수로 합치지 않는다. A_L은 연구상 기본 역할, A_S는 평가 역할, P는 미채택 후보다. 전체 source SHA와 행번호는 JSON 및 [source anchors](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/evidence/source-anchors.json)에 있다.

## semantic-origin — 요청 token-origin과 semantic phase

- **donor_repo**: hsju2021/llama.cpp-fork
- **donor_ref**: 5219055a578fd741e029e81fefef6f3a5695086d
- **donor_path_symbol**: tools/server/server-context.cpp; token.phase / classifier
- **upstream_shared_ancestor**: 5219055a578fd741e029e81fefef6f3a5695086d for shared phase/profile; Linux scx_simple where stated; local base 59abec45fe0919de20550ce7cdcf363d9f7bbe5a
- **already_in_B0**: NO
- **already_in_B1**: YES
- **final_source**: /home/codinghuman/projects/new-a-workspace/src/llama/tools/server/server-context.cpp:541 / SHA256 85a9650aada34a5b0b726ac427dbe268ac625442f15ec68a7674c1520d455685 / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/semantic-origin.txt); /home/codinghuman/projects/new-a-workspace/src/llama/tools/server/server-phase.h:24 / SHA256 9b6165627fbb8f775a50fbc574a08d30914aae9ee3ca6679b3450ec3f79f459b / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/phase-classifier.txt)
- **change**: prompt 삽입 Prefill, sampled token Decode; 실제 off/view 구간에서 Unknown 우선, 양쪽 있으면 Mixed. retry split마다 재분류.
- **ancestry**: SHARED_ANCESTRY
- **build_flags**: HINT ON; profile mode phase
- **project_ELF_DSO_sha256**: {"A_runtime": {"libggml.so.0.18.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libmtmd.so.0": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "llama-server": "da9eaf0a3de17353dc2c7cab31c44a75e8f5c43b24efdb8d8cf675b3fec649fe", "libmtmd.so.0.0.10249": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libggml-base.so.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama-common.so.0.0.10249": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libmtmd.so": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so.0.18.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama.so": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libggml.so.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so.0.18.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libllama-common.so": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libllama-server-impl.so": "9204b0d4e45d4b5437c61417afe912d55618ce62ece6b6adf83ca7967dbe8cfc", "libggml.so": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libllama.so.0": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama.so.0.0.10249": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama-common.so.0": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libggml-cpu.so.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6"}, "P_runtime": {"libggml.so.0.18.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libmtmd.so.0": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "llama-server": "da9eaf0a3de17353dc2c7cab31c44a75e8f5c43b24efdb8d8cf675b3fec649fe", "libmtmd.so.0.0.10249": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libggml-base.so.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama-common.so.0.0.10249": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libmtmd.so": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so.0.18.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama.so": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libggml.so.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so.0.18.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libllama-common.so": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libllama-server-impl.so": "250671e9d6a21c467d7a20582682c77fd514f11f3aff308ca6a50c67d463f2fd", "libggml.so": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libllama.so.0": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama.so.0.0.10249": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama-common.so.0": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libggml-cpu.so.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6"}}
- **adoption**: {"A_L": "ACTIVE_DEFAULT", "A_S": "ACTIVE_EVALUATION_ONLY", "P": "TESTED_NOT_ADOPTED"}
- **execution**: {"A_L": "OBSERVED_EXECUTED", "A_S": "OBSERVED_EXECUTED", "P": "OBSERVED_EXECUTED"}
- **runtime_evidence**: ["evidence/scheduler-attachments.json", "observed-usage.json", "evidence/identity-recheck.json", "evidence/static-elf.json", "evidence/preserved/a-component-scheduler-replication-v1/frozen-release-map.json", "evidence/commit-hunks.json"]
- **observed_unit_denominator**: 정책 select 호출; token 수만으로 phase를 판단하지 않음
- **performance**: NOT_ISOLATED
- **comparison**: NONE
- **campaign_results**: []
- **actual_choice_difference**: See evidence and scope; no feature-off timing
- **allowed_claim**: 공유 기반을 최종 경로에서 사용
- **forbidden_claim**: semantic label 자체가 11~12%를 만들었다
- **unknown**: 동일 비-phase controller 대비 비교 없음

## phase-lightening — phase header와 transition-only 경량화

- **donor_repo**: local shared-base derivative
- **donor_ref**: c2c398510f69180cfc29026cb1e0ca133b01d548
- **donor_path_symbol**: server-phase.h / server_scx_phase_state
- **upstream_shared_ancestor**: 5219055a578fd741e029e81fefef6f3a5695086d for shared phase/profile; Linux scx_simple where stated; local base 59abec45fe0919de20550ce7cdcf363d9f7bbe5a
- **already_in_B0**: NO
- **already_in_B1**: YES
- **final_source**: /home/codinghuman/projects/new-a-workspace/src/llama/tools/server/server-phase.h:24 / SHA256 9b6165627fbb8f775a50fbc574a08d30914aae9ee3ca6679b3450ec3f79f459b / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/phase-classifier.txt); /home/codinghuman/projects/new-a-workspace/src/llama/tools/server/server-context.cpp:541 / SHA256 85a9650aada34a5b0b726ac427dbe268ac625442f15ec68a7674c1520d455685 / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/semantic-origin.txt)
- **change**: 기존 의미 분류를 경량 scalar transition 상태로 연결; 동일 phase 재방출 생략.
- **ancestry**: BORROWED_MODIFIED
- **build_flags**: LLAMA_SCX_PHASE_HINT=ON; TRACE undefined
- **project_ELF_DSO_sha256**: {"A_runtime": {"libggml.so.0.18.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libmtmd.so.0": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "llama-server": "da9eaf0a3de17353dc2c7cab31c44a75e8f5c43b24efdb8d8cf675b3fec649fe", "libmtmd.so.0.0.10249": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libggml-base.so.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama-common.so.0.0.10249": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libmtmd.so": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so.0.18.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama.so": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libggml.so.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so.0.18.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libllama-common.so": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libllama-server-impl.so": "9204b0d4e45d4b5437c61417afe912d55618ce62ece6b6adf83ca7967dbe8cfc", "libggml.so": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libllama.so.0": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama.so.0.0.10249": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama-common.so.0": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libggml-cpu.so.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6"}, "P_runtime": {"libggml.so.0.18.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libmtmd.so.0": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "llama-server": "da9eaf0a3de17353dc2c7cab31c44a75e8f5c43b24efdb8d8cf675b3fec649fe", "libmtmd.so.0.0.10249": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libggml-base.so.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama-common.so.0.0.10249": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libmtmd.so": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so.0.18.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama.so": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libggml.so.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so.0.18.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libllama-common.so": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libllama-server-impl.so": "250671e9d6a21c467d7a20582682c77fd514f11f3aff308ca6a50c67d463f2fd", "libggml.so": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libllama.so.0": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama.so.0.0.10249": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama-common.so.0": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libggml-cpu.so.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6"}}
- **adoption**: {"A_L": "ACTIVE_DEFAULT", "A_S": "ACTIVE_EVALUATION_ONLY", "P": "TESTED_NOT_ADOPTED"}
- **execution**: {"A_L": "OBSERVED_EXECUTED", "A_S": "OBSERVED_EXECUTED", "P": "OBSERVED_EXECUTED"}
- **runtime_evidence**: ["evidence/scheduler-attachments.json", "observed-usage.json", "evidence/identity-recheck.json", "evidence/static-elf.json", "evidence/preserved/a-component-scheduler-replication-v1/frozen-release-map.json", "sources/commit-patches/c2c398510f69-tools_server_server-context.cpp.patch"]
- **observed_unit_denominator**: 전환 수는 최종 timing raw에 직접 export되지 않음
- **performance**: NOT_ISOLATED
- **comparison**: NONE
- **campaign_results**: []
- **actual_choice_difference**: See evidence and scope; no feature-off timing
- **allowed_claim**: 경량 경로가 활성
- **forbidden_claim**: idle 동안 phase별 계산 시간을 잴 수 있다
- **unknown**: header 최초 추가 commit은 선택 Git path 집계에 없음; base59와 최종 byte identity 확인

## profile-api — 명시적 compute-profile API

- **donor_repo**: hsju2021/llama.cpp-fork
- **donor_ref**: a94326390a8fb8686881e0463321acce4419ddcc
- **donor_path_symbol**: include/llama.h, src/llama-context.*; llama_decode_with_options
- **upstream_shared_ancestor**: 5219055a578fd741e029e81fefef6f3a5695086d for shared phase/profile; Linux scx_simple where stated; local base 59abec45fe0919de20550ce7cdcf363d9f7bbe5a
- **already_in_B0**: NO
- **already_in_B1**: YES; legacy defaults AUTO
- **final_source**: /home/codinghuman/projects/new-a-workspace/src/llama/include/llama.h:221 / SHA256 9d5a18d731237f25111e1772eb0546690497b8a25ec2ad299910f6f7234f172b / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/profile-header.txt); /home/codinghuman/projects/new-a-workspace/src/llama/src/llama-context.h:38 / SHA256 af5f558d5e4e1ce38c0e541f60181053291ac8e9355f4e63eeb59a9f8caef9e5 / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/profile-resolve.txt); /home/codinghuman/projects/new-a-workspace/src/llama/src/llama-context.cpp:2457 / SHA256 5e7b81b3ddcc851fcb0e9dbf49b6ba1cb663b677d25de2a2b8eca31d42670f0a / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/profile-engine.txt)
- **change**: AUTO는 physical ubatch 토큰 수, GENERATION/BATCH는 명시 선택; default_options와 validation 유지.
- **ancestry**: SHARED_ANCESTRY
- **build_flags**: 동결 libllama; archived O3/OpenMP build
- **project_ELF_DSO_sha256**: {"A_runtime": {"libggml.so.0.18.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libmtmd.so.0": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "llama-server": "da9eaf0a3de17353dc2c7cab31c44a75e8f5c43b24efdb8d8cf675b3fec649fe", "libmtmd.so.0.0.10249": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libggml-base.so.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama-common.so.0.0.10249": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libmtmd.so": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so.0.18.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama.so": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libggml.so.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so.0.18.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libllama-common.so": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libllama-server-impl.so": "9204b0d4e45d4b5437c61417afe912d55618ce62ece6b6adf83ca7967dbe8cfc", "libggml.so": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libllama.so.0": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama.so.0.0.10249": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama-common.so.0": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libggml-cpu.so.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6"}, "P_runtime": {"libggml.so.0.18.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libmtmd.so.0": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "llama-server": "da9eaf0a3de17353dc2c7cab31c44a75e8f5c43b24efdb8d8cf675b3fec649fe", "libmtmd.so.0.0.10249": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libggml-base.so.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama-common.so.0.0.10249": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libmtmd.so": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so.0.18.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama.so": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libggml.so.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so.0.18.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libllama-common.so": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libllama-server-impl.so": "250671e9d6a21c467d7a20582682c77fd514f11f3aff308ca6a50c67d463f2fd", "libggml.so": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libllama.so.0": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama.so.0.0.10249": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama-common.so.0": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libggml-cpu.so.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6"}}
- **adoption**: {"A_L": "ACTIVE_DEFAULT", "A_S": "ACTIVE_EVALUATION_ONLY", "P": "TESTED_NOT_ADOPTED"}
- **execution**: {"A_L": "OBSERVED_EXECUTED", "A_S": "OBSERVED_EXECUTED", "P": "OBSERVED_EXECUTED"}
- **runtime_evidence**: ["evidence/scheduler-attachments.json", "observed-usage.json", "evidence/identity-recheck.json", "evidence/static-elf.json", "evidence/preserved/a-component-scheduler-replication-v1/frozen-release-map.json", "evidence/donor-profile-origin.json", "evidence/commit-hunks.json"]
- **observed_unit_denominator**: API 호출과 내부 graph는 1:1 보장 없음
- **performance**: NOT_ISOLATED
- **comparison**: NONE
- **campaign_results**: []
- **actual_choice_difference**: See evidence and scope; no feature-off timing
- **allowed_claim**: 기존 API가 E 결정을 전달
- **forbidden_claim**: pool off이므로 API도 off / API 단독 개선율
- **unknown**: API만 끈 동등한 controller counterfactual 없음

## openmp-team — profile에서 CPU worker까지 연결

- **donor_repo**: hsju2021/llama.cpp-fork
- **donor_ref**: a94326390a8fb8686881e0463321acce4419ddcc
- **donor_path_symbol**: graph_compute; ggml_backend_cpu_set_n_threads; omp parallel
- **upstream_shared_ancestor**: 5219055a578fd741e029e81fefef6f3a5695086d for shared phase/profile; Linux scx_simple where stated; local base 59abec45fe0919de20550ce7cdcf363d9f7bbe5a
- **already_in_B0**: OpenMP/threads already YES; override NO
- **already_in_B1**: YES
- **final_source**: /home/codinghuman/projects/new-a-workspace/src/llama/src/llama-context.cpp:2457 / SHA256 5e7b81b3ddcc851fcb0e9dbf49b6ba1cb663b677d25de2a2b8eca31d42670f0a / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/profile-engine.txt); /home/codinghuman/projects/new-a-workspace/src/llama/ggml/src/ggml-cpu/ggml-cpu.cpp:256 / SHA256 8ab6ed68e2c0eea05090368d7788636500d146851298685276d7a9302c03c5c1 / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/CPU-registry.txt); /home/codinghuman/projects/new-a-workspace/src/llama/ggml/src/ggml-cpu/ggml-cpu.c:481 / SHA256 cc4366fb2ed1fa466958557e8d631eda1a73b4d144498b98d969a9b5e0fdd13e / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/CPU-graph.txt)
- **change**: profile이 generation5/batch6 선택, thread setter, graph의 omp team에 전달.
- **ancestry**: BORROWED_MODIFIED
- **build_flags**: GGML_USE_OPENMP; -fopenmp; libgomp; OMP_DYNAMIC=FALSE
- **project_ELF_DSO_sha256**: {"A_runtime": {"libggml.so.0.18.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libmtmd.so.0": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "llama-server": "da9eaf0a3de17353dc2c7cab31c44a75e8f5c43b24efdb8d8cf675b3fec649fe", "libmtmd.so.0.0.10249": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libggml-base.so.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama-common.so.0.0.10249": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libmtmd.so": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so.0.18.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama.so": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libggml.so.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so.0.18.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libllama-common.so": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libllama-server-impl.so": "9204b0d4e45d4b5437c61417afe912d55618ce62ece6b6adf83ca7967dbe8cfc", "libggml.so": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libllama.so.0": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama.so.0.0.10249": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama-common.so.0": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libggml-cpu.so.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6"}, "P_runtime": {"libggml.so.0.18.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libmtmd.so.0": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "llama-server": "da9eaf0a3de17353dc2c7cab31c44a75e8f5c43b24efdb8d8cf675b3fec649fe", "libmtmd.so.0.0.10249": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libggml-base.so.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama-common.so.0.0.10249": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libmtmd.so": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so.0.18.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama.so": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libggml.so.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so.0.18.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libllama-common.so": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libllama-server-impl.so": "250671e9d6a21c467d7a20582682c77fd514f11f3aff308ca6a50c67d463f2fd", "libggml.so": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libllama.so.0": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama.so.0.0.10249": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama-common.so.0": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libggml-cpu.so.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6"}}
- **adoption**: {"A_L": "ACTIVE_DEFAULT", "A_S": "ACTIVE_EVALUATION_ONLY", "P": "TESTED_NOT_ADOPTED"}
- **execution**: {"A_L": "OBSERVED_EXECUTED", "A_S": "OBSERVED_EXECUTED", "P": "OBSERVED_EXECUTED"}
- **runtime_evidence**: ["evidence/scheduler-attachments.json", "observed-usage.json", "evidence/identity-recheck.json", "evidence/static-elf.json", "evidence/preserved/a-component-scheduler-replication-v1/frozen-release-map.json"]
- **observed_unit_denominator**: NEWA_TEAM은 libgomp affinity-report team set; 전체 graph 계수 아님
- **performance**: NOT_ISOLATED
- **comparison**: NONE
- **campaign_results**: []
- **actual_choice_difference**: See evidence and scope; no feature-off timing
- **allowed_claim**: 실제 5/6 team 관측과 선택 로그가 연결
- **forbidden_claim**: 매 graph마다 OS thread를 새로 생성 / pool port가 wakeup을 제거
- **unknown**: 연속 graph별 team 수는 무거운 tracing 없이 계수하지 않음

## hint-trace — HINT/TRACE 분리·진단 overhead 경량화

- **donor_repo**: local lineage
- **donor_ref**: 2ec5829580fa3d9e16e3a315eb789982f7169882; 1bb4bd7d; e5b38588; c8b9d61d
- **donor_path_symbol**: server CMake, context, worker diagnostics
- **upstream_shared_ancestor**: 5219055a578fd741e029e81fefef6f3a5695086d for shared phase/profile; Linux scx_simple where stated; local base 59abec45fe0919de20550ce7cdcf363d9f7bbe5a
- **already_in_B0**: NO
- **already_in_B1**: YES
- **final_source**: /home/codinghuman/projects/new-a-workspace/src/llama/tools/server/server-scx.h:11 / SHA256 655e62843596e98e66920b6b8d12e868ea0a01df96a5020c0ee6cc86d26f303f / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/phase-bridge.txt); /home/codinghuman/projects/new-a-workspace/src/llama/tools/server/server-context.cpp:541 / SHA256 85a9650aada34a5b0b726ac427dbe268ac625442f15ec68a7674c1520d455685 / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/semantic-origin.txt); /home/codinghuman/projects/new-a-workspace/src/llama/src/llama-context.cpp:2457 / SHA256 5e7b81b3ddcc851fcb0e9dbf49b6ba1cb663b677d25de2a2b8eca31d42670f0a / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/profile-engine.txt); /home/codinghuman/projects/new-a-workspace/src/llama/ggml/src/ggml-cpu/ggml-cpu.c:481 / SHA256 cc4366fb2ed1fa466958557e8d631eda1a73b4d144498b98d969a9b5e0fdd13e / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/CPU-graph.txt)
- **change**: begin/end TRACE, profile clocks/logging 조건부; context/team debug 제거. 실제 marker는 scalar HINT.
- **ancestry**: LOCAL_NEW
- **build_flags**: LLAMA_SCX_PHASE_HINT defined; LLAMA_SCX_PHASE_TRACE absent
- **project_ELF_DSO_sha256**: {"A_runtime": {"libggml.so.0.18.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libmtmd.so.0": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "llama-server": "da9eaf0a3de17353dc2c7cab31c44a75e8f5c43b24efdb8d8cf675b3fec649fe", "libmtmd.so.0.0.10249": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libggml-base.so.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama-common.so.0.0.10249": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libmtmd.so": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so.0.18.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama.so": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libggml.so.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so.0.18.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libllama-common.so": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libllama-server-impl.so": "9204b0d4e45d4b5437c61417afe912d55618ce62ece6b6adf83ca7967dbe8cfc", "libggml.so": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libllama.so.0": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama.so.0.0.10249": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama-common.so.0": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libggml-cpu.so.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6"}, "P_runtime": {"libggml.so.0.18.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libmtmd.so.0": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "llama-server": "da9eaf0a3de17353dc2c7cab31c44a75e8f5c43b24efdb8d8cf675b3fec649fe", "libmtmd.so.0.0.10249": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libggml-base.so.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama-common.so.0.0.10249": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libmtmd.so": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so.0.18.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama.so": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libggml.so.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so.0.18.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libllama-common.so": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libllama-server-impl.so": "250671e9d6a21c467d7a20582682c77fd514f11f3aff308ca6a50c67d463f2fd", "libggml.so": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libllama.so.0": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama.so.0.0.10249": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama-common.so.0": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libggml-cpu.so.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6"}}
- **adoption**: {"A_L": "ACTIVE_DEFAULT", "A_S": "ACTIVE_EVALUATION_ONLY", "P": "TESTED_NOT_ADOPTED"}
- **execution**: {"A_L": "OBSERVED_EXECUTED", "A_S": "OBSERVED_EXECUTED", "P": "OBSERVED_EXECUTED"}
- **runtime_evidence**: ["evidence/scheduler-attachments.json", "observed-usage.json", "evidence/identity-recheck.json", "evidence/static-elf.json", "evidence/preserved/a-component-scheduler-replication-v1/frozen-release-map.json", "evidence/commit-hunks.json"]
- **observed_unit_denominator**: 최종 타이밍은 TRACE 없음; OpenMP affinity 진단은 모든 arm 동일
- **performance**: NOT_ISOLATED
- **comparison**: NONE
- **campaign_results**: []
- **actual_choice_difference**: See evidence and scope; no feature-off timing
- **allowed_claim**: 경량화 계보와 실제 빌드 설정을 확인
- **forbidden_claim**: FULL 진단/모든 계측을 제거한 최고 성능
- **unknown**: HINT OFF 전체 context 기존 compile limitation; 전 build matrix PASS 아님

## cpu-phase-bridge — scalar marker의 userspace CPU phase setter

- **donor_repo**: local archived overlay
- **donor_ref**: 59abec45fe0919de20550ce7cdcf363d9f7bbe5a + overlay
- **donor_path_symbol**: llama_scx_phase_v1 -> ggml_backend_cpu_newa_phase
- **upstream_shared_ancestor**: 5219055a578fd741e029e81fefef6f3a5695086d for shared phase/profile; Linux scx_simple where stated; local base 59abec45fe0919de20550ce7cdcf363d9f7bbe5a
- **already_in_B0**: NO
- **already_in_B1**: YES
- **final_source**: /home/codinghuman/projects/new-a-workspace/src/llama/tools/server/server-scx.h:11 / SHA256 655e62843596e98e66920b6b8d12e868ea0a01df96a5020c0ee6cc86d26f303f / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/phase-bridge.txt); /home/codinghuman/projects/new-a-workspace/src/llama/ggml/src/ggml-cpu/ggml-cpu.cpp:256 / SHA256 8ab6ed68e2c0eea05090368d7788636500d146851298685276d7a9302c03c5c1 / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/CPU-registry.txt); /home/codinghuman/projects/new-a-workspace/src/llama/ggml/src/ggml-cpu/ggml-cpu.c:481 / SHA256 cc4366fb2ed1fa466958557e8d631eda1a73b4d144498b98d969a9b5e0fdd13e / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/CPU-graph.txt)
- **change**: 등록 함수 한번 lookup 후 phase atomic setter; uprobe 유무와 독립.
- **ancestry**: LOCAL_NEW
- **build_flags**: HINT ON; CPU registry export
- **project_ELF_DSO_sha256**: {"A_runtime": {"libggml.so.0.18.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libmtmd.so.0": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "llama-server": "da9eaf0a3de17353dc2c7cab31c44a75e8f5c43b24efdb8d8cf675b3fec649fe", "libmtmd.so.0.0.10249": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libggml-base.so.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama-common.so.0.0.10249": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libmtmd.so": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so.0.18.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama.so": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libggml.so.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so.0.18.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libllama-common.so": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libllama-server-impl.so": "9204b0d4e45d4b5437c61417afe912d55618ce62ece6b6adf83ca7967dbe8cfc", "libggml.so": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libllama.so.0": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama.so.0.0.10249": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama-common.so.0": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libggml-cpu.so.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6"}, "P_runtime": {"libggml.so.0.18.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libmtmd.so.0": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "llama-server": "da9eaf0a3de17353dc2c7cab31c44a75e8f5c43b24efdb8d8cf675b3fec649fe", "libmtmd.so.0.0.10249": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libggml-base.so.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama-common.so.0.0.10249": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libmtmd.so": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so.0.18.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama.so": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libggml.so.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so.0.18.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libllama-common.so": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libllama-server-impl.so": "250671e9d6a21c467d7a20582682c77fd514f11f3aff308ca6a50c67d463f2fd", "libggml.so": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libllama.so.0": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama.so.0.0.10249": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama-common.so.0": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libggml-cpu.so.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6"}}
- **adoption**: {"A_L": "ACTIVE_DEFAULT", "A_S": "ACTIVE_EVALUATION_ONLY", "P": "TESTED_NOT_ADOPTED"}
- **execution**: {"A_L": "OBSERVED_EXECUTED", "A_S": "OBSERVED_EXECUTED", "P": "OBSERVED_EXECUTED"}
- **runtime_evidence**: ["evidence/scheduler-attachments.json", "observed-usage.json", "evidence/identity-recheck.json", "evidence/static-elf.json", "evidence/preserved/a-component-scheduler-replication-v1/frozen-release-map.json", "observed-usage.json"]
- **observed_unit_denominator**: 별도 R 진단의 Q4/Q6 경로 계수; 모든 timing 호출 직접 추적 아님
- **performance**: NOT_ISOLATED
- **comparison**: NONE
- **campaign_results**: []
- **actual_choice_difference**: See evidence and scope; no feature-off timing
- **allowed_claim**: Linux만으로도 CPU kernel eligibility 전달
- **forbidden_claim**: HINT off 비교를 순수 scheduler ablation으로 처리
- **unknown**: overlay author/도입 commit의 hunk 귀속 UNKNOWN

## E-sensor — Prefill-pressure CPU 센서

- **donor_repo**: local frozen E overlay
- **donor_ref**: 59abec45fe0919de20550ce7cdcf363d9f7bbe5a + runtime-prefill-pressure-v2
- **donor_path_symbol**: newa-prefill-pressure.h: sample_cpu/score
- **upstream_shared_ancestor**: 5219055a578fd741e029e81fefef6f3a5695086d for shared phase/profile; Linux scx_simple where stated; local base 59abec45fe0919de20550ce7cdcf363d9f7bbe5a
- **already_in_B0**: NO
- **already_in_B1**: NO in runtime/B1; pre-R E sibling YES
- **final_source**: /home/codinghuman/projects/new-a-workspace/src/llama/tools/server/newa-prefill-pressure.h:22 / SHA256 944b2b546427fb97b7e5584c0a383ad97cbea04a987cf1a303fa69a4c01afe4d / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/E.txt)
- **change**: 선택 6 CPU /proc/stat user+nice+system 차이에서 process CPU·tick round 보정; margin .02, threshold .125.
- **ancestry**: LOCAL_NEW
- **build_flags**: NEWA_DECODE_RESOURCE=pressure/fixed6
- **project_ELF_DSO_sha256**: {"A_runtime": {"libggml.so.0.18.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libmtmd.so.0": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "llama-server": "da9eaf0a3de17353dc2c7cab31c44a75e8f5c43b24efdb8d8cf675b3fec649fe", "libmtmd.so.0.0.10249": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libggml-base.so.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama-common.so.0.0.10249": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libmtmd.so": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so.0.18.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama.so": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libggml.so.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so.0.18.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libllama-common.so": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libllama-server-impl.so": "9204b0d4e45d4b5437c61417afe912d55618ce62ece6b6adf83ca7967dbe8cfc", "libggml.so": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libllama.so.0": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama.so.0.0.10249": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama-common.so.0": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libggml-cpu.so.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6"}, "P_runtime": {"libggml.so.0.18.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libmtmd.so.0": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "llama-server": "da9eaf0a3de17353dc2c7cab31c44a75e8f5c43b24efdb8d8cf675b3fec649fe", "libmtmd.so.0.0.10249": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libggml-base.so.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama-common.so.0.0.10249": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libmtmd.so": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so.0.18.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama.so": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libggml.so.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so.0.18.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libllama-common.so": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libllama-server-impl.so": "250671e9d6a21c467d7a20582682c77fd514f11f3aff308ca6a50c67d463f2fd", "libggml.so": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libllama.so.0": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama.so.0.0.10249": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama-common.so.0": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libggml-cpu.so.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6"}}
- **adoption**: {"A_L": "ACTIVE_DEFAULT", "A_S": "ACTIVE_EVALUATION_ONLY", "P": "TESTED_NOT_ADOPTED"}
- **execution**: {"A_L": "OBSERVED_EXECUTED", "A_S": "OBSERVED_EXECUTED", "P": "OBSERVED_EXECUTED"}
- **runtime_evidence**: ["evidence/scheduler-attachments.json", "observed-usage.json", "evidence/identity-recheck.json", "evidence/static-elf.json", "evidence/preserved/a-component-scheduler-replication-v1/frozen-release-map.json"]
- **observed_unit_denominator**: 순수 Prefill >=32 tokens를 한번 포착; 실제 model call >=1초; read<=20ms
- **performance**: NOT_ISOLATED
- **comparison**: NONE
- **campaign_results**: []
- **actual_choice_difference**: See evidence and scope; no feature-off timing
- **allowed_claim**: 관측된 Prefill 경합 신호를 후속 Decode에 사용
- **forbidden_claim**: 매 Decode 부하 재측정 / 모든 부하 자동 적응
- **unknown**: 센서 자체와 task guard 각각의 성능 ablation 없음

## E-guards — epoch/8-task/position/fallback 안전 경계

- **donor_repo**: local frozen E overlay
- **donor_ref**: 59abec45fe0919de20550ce7cdcf363d9f7bbe5a + runtime-prefill-pressure-v2
- **donor_path_symbol**: select/begin/finish/reset
- **upstream_shared_ancestor**: 5219055a578fd741e029e81fefef6f3a5695086d for shared phase/profile; Linux scx_simple where stated; local base 59abec45fe0919de20550ce7cdcf363d9f7bbe5a
- **already_in_B0**: NO
- **already_in_B1**: NO in B1; E sibling YES
- **final_source**: /home/codinghuman/projects/new-a-workspace/src/llama/tools/server/newa-prefill-pressure.h:22 / SHA256 944b2b546427fb97b7e5584c0a383ad97cbea04a987cf1a303fa69a4c01afe4d / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/E.txt); /home/codinghuman/projects/new-a-workspace/src/llama/tools/server/server-context.cpp:541 / SHA256 85a9650aada34a5b0b726ac427dbe268ac625442f15ec68a7674c1520d455685 / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/semantic-origin.txt)
- **change**: 첫 Decode age<=10초, 8-task 시작, 위치 연속, tail은 subset, <=256 적격 calls; idle/reset; 실패 미commit. Unknown/Mixed6, singleton Decode5.
- **ancestry**: LOCAL_NEW
- **build_flags**: threads5/batch6, fixed 6 physical-core envelope
- **project_ELF_DSO_sha256**: {"A_runtime": {"libggml.so.0.18.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libmtmd.so.0": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "llama-server": "da9eaf0a3de17353dc2c7cab31c44a75e8f5c43b24efdb8d8cf675b3fec649fe", "libmtmd.so.0.0.10249": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libggml-base.so.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama-common.so.0.0.10249": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libmtmd.so": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so.0.18.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama.so": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libggml.so.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so.0.18.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libllama-common.so": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libllama-server-impl.so": "9204b0d4e45d4b5437c61417afe912d55618ce62ece6b6adf83ca7967dbe8cfc", "libggml.so": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libllama.so.0": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama.so.0.0.10249": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama-common.so.0": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libggml-cpu.so.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6"}, "P_runtime": {"libggml.so.0.18.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libmtmd.so.0": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "llama-server": "da9eaf0a3de17353dc2c7cab31c44a75e8f5c43b24efdb8d8cf675b3fec649fe", "libmtmd.so.0.0.10249": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libggml-base.so.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama-common.so.0.0.10249": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libmtmd.so": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so.0.18.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama.so": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libggml.so.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so.0.18.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libllama-common.so": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libllama-server-impl.so": "250671e9d6a21c467d7a20582682c77fd514f11f3aff308ca6a50c67d463f2fd", "libggml.so": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libllama.so.0": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama.so.0.0.10249": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama-common.so.0": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libggml-cpu.so.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6"}}
- **adoption**: {"A_L": "ACTIVE_DEFAULT", "A_S": "ACTIVE_EVALUATION_ONLY", "P": "TESTED_NOT_ADOPTED"}
- **execution**: {"A_L": "OBSERVED_EXECUTED", "A_S": "OBSERVED_EXECUTED", "P": "OBSERVED_EXECUTED"}
- **runtime_evidence**: ["evidence/scheduler-attachments.json", "observed-usage.json", "evidence/identity-recheck.json", "evidence/static-elf.json", "evidence/preserved/a-component-scheduler-replication-v1/frozen-release-map.json"]
- **observed_unit_denominator**: raw epoch와 committed select 호출; fallback별 timing은 별도 미측정
- **performance**: NOT_ISOLATED
- **comparison**: NONE
- **campaign_results**: []
- **actual_choice_difference**: See evidence and scope; no feature-off timing
- **allowed_claim**: 지원 cohort 범위와 보수적 fallback 명시
- **forbidden_claim**: any concurrency/shape 안정성 일반화
- **unknown**: guard별 독립 효과와 모든 예외 shape 확인 없음

## E-choice — Prefill 관측 기반 적격 Decode 5/6 선택

- **donor_repo**: local frozen E overlay
- **donor_ref**: 59abec45fe0919de20550ce7cdcf363d9f7bbe5a + runtime-prefill-pressure-v2
- **donor_path_symbol**: select -> options.compute_profile
- **upstream_shared_ancestor**: 5219055a578fd741e029e81fefef6f3a5695086d for shared phase/profile; Linux scx_simple where stated; local base 59abec45fe0919de20550ce7cdcf363d9f7bbe5a
- **already_in_B0**: NO
- **already_in_B1**: NO in B1; E sibling YES
- **final_source**: /home/codinghuman/projects/new-a-workspace/src/llama/tools/server/newa-prefill-pressure.h:22 / SHA256 944b2b546427fb97b7e5584c0a383ad97cbea04a987cf1a303fa69a4c01afe4d / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/E.txt); /home/codinghuman/projects/new-a-workspace/src/llama/tools/server/server-context.cpp:541 / SHA256 85a9650aada34a5b0b726ac427dbe268ac625442f15ec68a7674c1520d455685 / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/semantic-origin.txt); /home/codinghuman/projects/new-a-workspace/src/llama/src/llama-context.cpp:2457 / SHA256 5e7b81b3ddcc851fcb0e9dbf49b6ba1cb663b677d25de2a2b8eca31d42670f0a / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/profile-engine.txt)
- **change**: same sensor/guards의 fixed6와 pressure 비교. condition명/답변내용 입력 없음.
- **ancestry**: LOCAL_NEW
- **build_flags**: pressure 대 fixed6; 나머지 env와 binary 동일
- **project_ELF_DSO_sha256**: {"A_runtime": {"libggml.so.0.18.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libmtmd.so.0": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "llama-server": "da9eaf0a3de17353dc2c7cab31c44a75e8f5c43b24efdb8d8cf675b3fec649fe", "libmtmd.so.0.0.10249": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libggml-base.so.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama-common.so.0.0.10249": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libmtmd.so": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so.0.18.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama.so": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libggml.so.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so.0.18.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libllama-common.so": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libllama-server-impl.so": "9204b0d4e45d4b5437c61417afe912d55618ce62ece6b6adf83ca7967dbe8cfc", "libggml.so": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libllama.so.0": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama.so.0.0.10249": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama-common.so.0": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libggml-cpu.so.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6"}, "P_runtime": {"libggml.so.0.18.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libmtmd.so.0": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "llama-server": "da9eaf0a3de17353dc2c7cab31c44a75e8f5c43b24efdb8d8cf675b3fec649fe", "libmtmd.so.0.0.10249": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libggml-base.so.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama-common.so.0.0.10249": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libmtmd.so": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so.0.18.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama.so": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libggml.so.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so.0.18.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libllama-common.so": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libllama-server-impl.so": "250671e9d6a21c467d7a20582682c77fd514f11f3aff308ca6a50c67d463f2fd", "libggml.so": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libllama.so.0": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama.so.0.0.10249": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama-common.so.0": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libggml-cpu.so.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6"}}
- **adoption**: {"A_L": "ACTIVE_DEFAULT", "A_S": "ACTIVE_EVALUATION_ONLY", "P": "TESTED_NOT_ADOPTED"}
- **execution**: {"A_L": "OBSERVED_EXECUTED", "A_S": "OBSERVED_EXECUTED", "P": "OBSERVED_EXECUTED"}
- **runtime_evidence**: ["evidence/scheduler-attachments.json", "observed-usage.json", "evidence/identity-recheck.json", "evidence/static-elf.json", "evidence/preserved/a-component-scheduler-replication-v1/frozen-release-map.json", "evidence/performance-recalculation.json"]
- **observed_unit_denominator**: 각 캠페인/조건/arm measured 적격 multi-token 1016 calls; CPU25 pressure5/fixed6=6
- **performance**: ISOLATED_SCOPED_GAIN
- **comparison**: A_L/F6_L
- **campaign_results**: [{"campaign": "original", "condition": "ambient", "contrast": "A_L/F6_L", "mean": 0.23480583297689483, "ci": [-0.12906371649655246, 0.6263084489440018], "faster": 7}, {"campaign": "original", "condition": "cpu25", "contrast": "A_L/F6_L", "mean": 11.327640297479341, "ci": [9.13004073979402, 13.636931994571391], "faster": 8}, {"campaign": "replication", "condition": "ambient", "contrast": "A_L/F6_L", "mean": -0.40971194899830504, "ci": [-0.7754580033828797, 0.008946094482505107], "faster": 1}, {"campaign": "replication", "condition": "cpu25", "contrast": "A_L/F6_L", "mean": 12.126291405022666, "ci": [8.741188400079047, 15.97147537562704], "faster": 8}]
- **actual_choice_difference**: CPU25 pressure: eligible multi-token Decode 5, fixed6: 6; ambient both 6
- **allowed_claim**: CPU25에서 fixed6 대비 E 선택 효과 재현
- **forbidden_claim**: 커널 scheduler 효과 / fixed5보다 우월 / phase label 단독 이득
- **unknown**: fixed5, nonsemantic controller, fixed6_S 없음

## R-reference — R: semantic Prefill Q4 기준 body 복원

- **donor_repo**: local R overlay
- **donor_ref**: preserved R-prefill-reference.patch
- **donor_path_symbol**: newa_q4_try: phase==1 return false
- **upstream_shared_ancestor**: 5219055a578fd741e029e81fefef6f3a5695086d for shared phase/profile; Linux scx_simple where stated; local base 59abec45fe0919de20550ce7cdcf363d9f7bbe5a
- **already_in_B0**: reference body YES
- **already_in_B1**: custom Prefill route previously YES
- **final_source**: /home/codinghuman/projects/new-a-workspace/experiments/r-pool-validation-v1/candidates/R/overlay/ggml/src/ggml-cpu/newa-q4-policy.h:38 / SHA256 014ec3787142838295cb9e8193453ea504cf7a27f18c14a0fa6b8799fcd93029 / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/Q4-R.txt)
- **change**: Prefill custom path만 차단; 정확 Q4 Decode/Mixed와 Q6 유지.
- **ancestry**: LOCAL_NEW
- **build_flags**: R CPU DSO 45ddfa4d...; Q4=phase_batch
- **project_ELF_DSO_sha256**: {"A_runtime": {"libggml.so.0.18.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libmtmd.so.0": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "llama-server": "da9eaf0a3de17353dc2c7cab31c44a75e8f5c43b24efdb8d8cf675b3fec649fe", "libmtmd.so.0.0.10249": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libggml-base.so.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama-common.so.0.0.10249": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libmtmd.so": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so.0.18.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama.so": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libggml.so.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so.0.18.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libllama-common.so": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libllama-server-impl.so": "9204b0d4e45d4b5437c61417afe912d55618ce62ece6b6adf83ca7967dbe8cfc", "libggml.so": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libllama.so.0": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama.so.0.0.10249": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama-common.so.0": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libggml-cpu.so.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6"}, "P_runtime": {"libggml.so.0.18.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libmtmd.so.0": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "llama-server": "da9eaf0a3de17353dc2c7cab31c44a75e8f5c43b24efdb8d8cf675b3fec649fe", "libmtmd.so.0.0.10249": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libggml-base.so.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama-common.so.0.0.10249": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libmtmd.so": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so.0.18.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama.so": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libggml.so.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so.0.18.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libllama-common.so": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libllama-server-impl.so": "250671e9d6a21c467d7a20582682c77fd514f11f3aff308ca6a50c67d463f2fd", "libggml.so": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libllama.so.0": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama.so.0.0.10249": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama-common.so.0": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libggml-cpu.so.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6"}}
- **adoption**: {"A_L": "ACTIVE_DEFAULT", "A_S": "ACTIVE_EVALUATION_ONLY", "P": "TESTED_NOT_ADOPTED"}
- **execution**: {"A_L": "OBSERVED_EXECUTED", "A_S": "OBSERVED_EXECUTED", "P": "OBSERVED_EXECUTED"}
- **runtime_evidence**: ["evidence/scheduler-attachments.json", "observed-usage.json", "evidence/identity-recheck.json", "evidence/static-elf.json", "evidence/preserved/a-component-scheduler-replication-v1/frozen-release-map.json", "evidence/preserved/r-pool-validation-v1/evidence/R-checkpoint.json"]
- **observed_unit_denominator**: 별도 diagnostic reference-body Prefill 3935; 제한 logits 8 checkpoints 모두 byte equal
- **performance**: NOT_ISOLATED
- **comparison**: NONE
- **campaign_results**: []
- **actual_choice_difference**: See evidence and scope; no feature-off timing
- **allowed_claim**: 수치 호환성 복원
- **forbidden_claim**: R이 새로운 속도 최적화 / 일반 품질 동등성 증명
- **unknown**: R vs pre-R 단독 성능 및 전체 모델/shape 품질 미검증

## Q4-exact — Decode/Mixed exact Q4 tile 준비 공유

- **donor_repo**: local archived CPU overlay
- **donor_ref**: 59abec45fe0919de20550ce7cdcf363d9f7bbe5a + phase-batch-q4-exact-v1
- **donor_path_symbol**: newa_q4_decode_exact; upstream repack arithmetic basis
- **upstream_shared_ancestor**: 5219055a578fd741e029e81fefef6f3a5695086d for shared phase/profile; Linux scx_simple where stated; local base 59abec45fe0919de20550ce7cdcf363d9f7bbe5a
- **already_in_B0**: reference arithmetic YES; this batching NO
- **already_in_B1**: YES
- **final_source**: /home/codinghuman/projects/new-a-workspace/src/llama/ggml/src/ggml-cpu/newa-q4-decode-exact.h:3 / SHA256 20d7bdc052650a53b6b5b7fabf81ec23d96aff4283c393ca3b9a23dcc98be62b / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/Q4-exact.txt); /home/codinghuman/projects/new-a-workspace/experiments/r-pool-validation-v1/candidates/R/overlay/ggml/src/ggml-cpu/newa-q4-policy.h:38 / SHA256 014ec3787142838295cb9e8193453ea504cf7a27f18c14a0fa6b8799fcd93029 / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/Q4-R.txt)
- **change**: 두 4-row activation group에 동일 weight 준비 공유; 누적 순서 exact 경로. phase2/3, nr4..15 중 원래 4배수 shape.
- **ancestry**: LOCAL_NEW
- **build_flags**: phase_batch; AVX2/native archived flags; retained R CPU
- **project_ELF_DSO_sha256**: {"A_runtime": {"libggml.so.0.18.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libmtmd.so.0": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "llama-server": "da9eaf0a3de17353dc2c7cab31c44a75e8f5c43b24efdb8d8cf675b3fec649fe", "libmtmd.so.0.0.10249": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libggml-base.so.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama-common.so.0.0.10249": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libmtmd.so": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so.0.18.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama.so": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libggml.so.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so.0.18.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libllama-common.so": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libllama-server-impl.so": "9204b0d4e45d4b5437c61417afe912d55618ce62ece6b6adf83ca7967dbe8cfc", "libggml.so": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libllama.so.0": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama.so.0.0.10249": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama-common.so.0": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libggml-cpu.so.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6"}, "P_runtime": {"libggml.so.0.18.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libmtmd.so.0": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "llama-server": "da9eaf0a3de17353dc2c7cab31c44a75e8f5c43b24efdb8d8cf675b3fec649fe", "libmtmd.so.0.0.10249": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libggml-base.so.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama-common.so.0.0.10249": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libmtmd.so": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so.0.18.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama.so": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libggml.so.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so.0.18.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libllama-common.so": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libllama-server-impl.so": "250671e9d6a21c467d7a20582682c77fd514f11f3aff308ca6a50c67d463f2fd", "libggml.so": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libllama.so.0": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama.so.0.0.10249": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama-common.so.0": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libggml-cpu.so.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6"}}
- **adoption**: {"A_L": "ACTIVE_DEFAULT", "A_S": "ACTIVE_EVALUATION_ONLY", "P": "TESTED_NOT_ADOPTED"}
- **execution**: {"A_L": "OBSERVED_EXECUTED", "A_S": "OBSERVED_EXECUTED", "P": "OBSERVED_EXECUTED"}
- **runtime_evidence**: ["evidence/scheduler-attachments.json", "observed-usage.json", "evidence/identity-recheck.json", "evidence/static-elf.json", "evidence/preserved/a-component-scheduler-replication-v1/frozen-release-map.json"]
- **observed_unit_denominator**: worker0 function calls: Decode167201/Mixed2656; diagnostic whole lifetime
- **performance**: NOT_ISOLATED
- **comparison**: NONE
- **campaign_results**: []
- **actual_choice_difference**: See evidence and scope; no feature-off timing
- **allowed_claim**: 재사용한 계산 준비를 줄인 누적 CPU 기능이 활성
- **forbidden_claim**: Q4 혼자 F6/B0 전부 또는 개인 몫
- **unknown**: 별도 Q4-off confirmation 및 dirty hunk author commit 없음

## Q6-expanded — Q6 batch4 적격 Decode/Mixed 확장

- **donor_repo**: local archived CPU overlay
- **donor_ref**: 59abec45fe0919de20550ce7cdcf363d9f7bbe5a + q6-batch
- **donor_path_symbol**: newa_q6_phase_allowed / newa_q6_batch4
- **upstream_shared_ancestor**: 5219055a578fd741e029e81fefef6f3a5695086d for shared phase/profile; Linux scx_simple where stated; local base 59abec45fe0919de20550ce7cdcf363d9f7bbe5a
- **already_in_B0**: original Q6 YES; expanded path NO
- **already_in_B1**: YES
- **final_source**: /home/codinghuman/projects/new-a-workspace/src/llama/ggml/src/ggml-cpu/newa-q6-policy.h:39 / SHA256 605cf933b96dc6ee4af7c635bdddb4dcdb04429d215b538bf0e59849f30b6d42 / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/Q6-policy.txt); /home/codinghuman/projects/new-a-workspace/src/llama/ggml/src/ggml-cpu/ggml-cpu.c:481 / SHA256 cc4366fb2ed1fa466958557e8d631eda1a73b4d144498b98d969a9b5e0fdd13e / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/CPU-graph.txt)
- **change**: pure Prefill와 phase_batch Decode/Mixed에서 적격 4-column 연산 사용.
- **ancestry**: LOCAL_NEW
- **build_flags**: GGML_NEWA_Q6_BATCH=phase_batch
- **project_ELF_DSO_sha256**: {"A_runtime": {"libggml.so.0.18.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libmtmd.so.0": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "llama-server": "da9eaf0a3de17353dc2c7cab31c44a75e8f5c43b24efdb8d8cf675b3fec649fe", "libmtmd.so.0.0.10249": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libggml-base.so.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama-common.so.0.0.10249": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libmtmd.so": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so.0.18.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama.so": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libggml.so.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so.0.18.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libllama-common.so": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libllama-server-impl.so": "9204b0d4e45d4b5437c61417afe912d55618ce62ece6b6adf83ca7967dbe8cfc", "libggml.so": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libllama.so.0": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama.so.0.0.10249": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama-common.so.0": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libggml-cpu.so.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6"}, "P_runtime": {"libggml.so.0.18.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libmtmd.so.0": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "llama-server": "da9eaf0a3de17353dc2c7cab31c44a75e8f5c43b24efdb8d8cf675b3fec649fe", "libmtmd.so.0.0.10249": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libggml-base.so.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama-common.so.0.0.10249": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libmtmd.so": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so.0.18.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama.so": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libggml.so.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so.0.18.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libllama-common.so": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libllama-server-impl.so": "250671e9d6a21c467d7a20582682c77fd514f11f3aff308ca6a50c67d463f2fd", "libggml.so": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libllama.so.0": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama.so.0.0.10249": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama-common.so.0": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libggml-cpu.so.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6"}}
- **adoption**: {"A_L": "ACTIVE_DEFAULT", "A_S": "ACTIVE_EVALUATION_ONLY", "P": "TESTED_NOT_ADOPTED"}
- **execution**: {"A_L": "OBSERVED_EXECUTED", "A_S": "OBSERVED_EXECUTED", "P": "OBSERVED_EXECUTED"}
- **runtime_evidence**: ["evidence/scheduler-attachments.json", "observed-usage.json", "evidence/identity-recheck.json", "evidence/static-elf.json", "evidence/preserved/a-component-scheduler-replication-v1/frozen-release-map.json"]
- **observed_unit_denominator**: worker0 chunk counts: Prefill15739/Decode462873/Mixed14003; Q4 호출과 단위 다름
- **performance**: NOT_ISOLATED
- **comparison**: NONE
- **campaign_results**: []
- **actual_choice_difference**: See evidence and scope; no feature-off timing
- **allowed_claim**: 남은 Q6 경로의 실행 확인
- **forbidden_claim**: Q6만의 정확한 처리량 몫
- **unknown**: 개별 Q6-off paired 확증 없음

## native-barrier — native spin/park/phase barrier 후보

- **donor_repo**: local archived barrier overlay
- **donor_ref**: 59abec45fe0919de20550ce7cdcf363d9f7bbe5a + phase-barrier
- **donor_path_symbol**: ggml_barrier / !GGML_USE_OPENMP
- **upstream_shared_ancestor**: 5219055a578fd741e029e81fefef6f3a5695086d for shared phase/profile; Linux scx_simple where stated; local base 59abec45fe0919de20550ce7cdcf363d9f7bbe5a
- **already_in_B0**: NO custom policy
- **already_in_B1**: source PRESENT; OpenMP inactive
- **final_source**: /home/codinghuman/projects/new-a-workspace/src/llama/ggml/src/ggml-cpu/ggml-cpu.c:481 / SHA256 cc4366fb2ed1fa466958557e8d631eda1a73b4d144498b98d969a9b5e0fdd13e / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/CPU-graph.txt)
- **change**: native custom barrier는 OpenMP compile branch에서 배제. OpenMP barrier는 유지.
- **ancestry**: LOCAL_NEW
- **build_flags**: GGML_USE_OPENMP defined
- **project_ELF_DSO_sha256**: {"A_runtime": {"libggml.so.0.18.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libmtmd.so.0": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "llama-server": "da9eaf0a3de17353dc2c7cab31c44a75e8f5c43b24efdb8d8cf675b3fec649fe", "libmtmd.so.0.0.10249": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libggml-base.so.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama-common.so.0.0.10249": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libmtmd.so": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so.0.18.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama.so": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libggml.so.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so.0.18.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libllama-common.so": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libllama-server-impl.so": "9204b0d4e45d4b5437c61417afe912d55618ce62ece6b6adf83ca7967dbe8cfc", "libggml.so": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libllama.so.0": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama.so.0.0.10249": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama-common.so.0": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libggml-cpu.so.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6"}, "P_runtime": {"libggml.so.0.18.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libmtmd.so.0": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "llama-server": "da9eaf0a3de17353dc2c7cab31c44a75e8f5c43b24efdb8d8cf675b3fec649fe", "libmtmd.so.0.0.10249": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libggml-base.so.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama-common.so.0.0.10249": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libmtmd.so": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so.0.18.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama.so": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libggml.so.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so.0.18.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libllama-common.so": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libllama-server-impl.so": "250671e9d6a21c467d7a20582682c77fd514f11f3aff308ca6a50c67d463f2fd", "libggml.so": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libllama.so.0": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama.so.0.0.10249": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama-common.so.0": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libggml-cpu.so.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6"}}
- **adoption**: {"A_L": "PRESENT_DISABLED", "A_S": "PRESENT_DISABLED", "P": "PRESENT_DISABLED"}
- **execution**: {"A_L": "NOT_ENABLED", "A_S": "NOT_ENABLED", "P": "NOT_ENABLED"}
- **runtime_evidence**: ["evidence/scheduler-attachments.json", "observed-usage.json", "evidence/identity-recheck.json", "evidence/static-elf.json", "evidence/preserved/a-component-scheduler-replication-v1/frozen-release-map.json"]
- **observed_unit_denominator**: 해당 native-policy 계수 최종에는 없음
- **performance**: NOT_MEASURED
- **comparison**: NONE
- **campaign_results**: []
- **actual_choice_difference**: See evidence and scope; no feature-off timing
- **allowed_claim**: source 보존과 실행 비활성 구분
- **forbidden_claim**: park/wakeup 최적화가 최종 이득을 만들었다
- **unknown**: native 경로 새 검증 금지 범위

## repack-memory — repack huge-page advice

- **donor_repo**: local archived memory overlay
- **donor_ref**: 59abec45fe0919de20550ce7cdcf363d9f7bbe5a + newa-repack-pages.h
- **donor_path_symbol**: madvise(MADV_HUGEPAGE)
- **upstream_shared_ancestor**: 5219055a578fd741e029e81fefef6f3a5695086d for shared phase/profile; Linux scx_simple where stated; local base 59abec45fe0919de20550ce7cdcf363d9f7bbe5a
- **already_in_B0**: NO explicit advice
- **already_in_B1**: YES
- **final_source**: /home/codinghuman/projects/new-a-workspace/src/llama/ggml/src/ggml-cpu/newa-repack-pages.h:30 / SHA256 69da9db393e937a15535b86255570e30290a116fb294a4c5d62f8ab9007a95c8 / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/repack-pages.txt)
- **change**: 정렬된 repack mapping에 madvise; 반환 log와 실제 huge page는 구분.
- **ancestry**: LOCAL_NEW
- **build_flags**: GGML_NEWA_REPACK_PAGES=huge
- **project_ELF_DSO_sha256**: {"A_runtime": {"libggml.so.0.18.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libmtmd.so.0": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "llama-server": "da9eaf0a3de17353dc2c7cab31c44a75e8f5c43b24efdb8d8cf675b3fec649fe", "libmtmd.so.0.0.10249": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libggml-base.so.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama-common.so.0.0.10249": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libmtmd.so": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so.0.18.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama.so": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libggml.so.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so.0.18.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libllama-common.so": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libllama-server-impl.so": "9204b0d4e45d4b5437c61417afe912d55618ce62ece6b6adf83ca7967dbe8cfc", "libggml.so": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libllama.so.0": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama.so.0.0.10249": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama-common.so.0": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libggml-cpu.so.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6"}, "P_runtime": {"libggml.so.0.18.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libmtmd.so.0": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "llama-server": "da9eaf0a3de17353dc2c7cab31c44a75e8f5c43b24efdb8d8cf675b3fec649fe", "libmtmd.so.0.0.10249": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libggml-base.so.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama-common.so.0.0.10249": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libmtmd.so": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so.0.18.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama.so": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libggml.so.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so.0.18.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libllama-common.so": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libllama-server-impl.so": "250671e9d6a21c467d7a20582682c77fd514f11f3aff308ca6a50c67d463f2fd", "libggml.so": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libllama.so.0": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama.so.0.0.10249": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama-common.so.0": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libggml-cpu.so.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6"}}
- **adoption**: {"A_L": "ACTIVE_DEFAULT", "A_S": "ACTIVE_EVALUATION_ONLY", "P": "TESTED_NOT_ADOPTED"}
- **execution**: {"A_L": "OBSERVED_EXECUTED", "A_S": "OBSERVED_EXECUTED", "P": "OBSERVED_EXECUTED"}
- **runtime_evidence**: ["evidence/scheduler-attachments.json", "observed-usage.json", "evidence/identity-recheck.json", "evidence/static-elf.json", "evidence/preserved/a-component-scheduler-replication-v1/frozen-release-map.json"]
- **observed_unit_denominator**: NEWA_REPACK_PAGES log는 advice 호출/return; actual huge-page bytes 없음
- **performance**: NOT_ISOLATED
- **comparison**: NONE
- **campaign_results**: []
- **actual_choice_difference**: See evidence and scope; no feature-off timing
- **allowed_claim**: huge-page 사용을 요청했다
- **forbidden_claim**: 실제 hugepage 사용 또는 이것만의 gain 확정
- **unknown**: smaps huge-page residency와 isolated comparison 없음

## FA-common — 일반 Flash Attention 공통 설정

- **donor_repo**: ggml-org/llama.cpp
- **donor_ref**: 7a2db1a0cf38e5f4eb278a58c3903d295258d0ea
- **donor_path_symbol**: --flash-attn on
- **upstream_shared_ancestor**: 5219055a578fd741e029e81fefef6f3a5695086d for shared phase/profile; Linux scx_simple where stated; local base 59abec45fe0919de20550ce7cdcf363d9f7bbe5a
- **already_in_B0**: YES
- **already_in_B1**: YES
- **final_source**: 최종 활성 source hunk 없음 또는 cases 공통 설정; 근거 경로 참조
- **change**: B0/F6/A 동일 on; 신규 차별점으로 세지 않음.
- **ancestry**: UPSTREAM_UNCHANGED
- **build_flags**: --flash-attn on
- **project_ELF_DSO_sha256**: 최종 해당 기능 ELF 없음; 공통 runtime identity는 frozen-release-map 참조
- **adoption**: {"A_L": "ACTIVE_DEFAULT", "A_S": "ACTIVE_EVALUATION_ONLY", "P": "TESTED_NOT_ADOPTED"}
- **execution**: {"A_L": "ENABLED_WITHOUT_PATH_PROOF", "A_S": "ENABLED_WITHOUT_PATH_PROOF", "P": "ENABLED_WITHOUT_PATH_PROOF"}
- **runtime_evidence**: ["evidence/scheduler-attachments.json", "observed-usage.json", "evidence/identity-recheck.json", "evidence/static-elf.json", "evidence/preserved/a-component-scheduler-replication-v1/frozen-release-map.json"]
- **observed_unit_denominator**: 동일 argv; FA-off ablation 없음
- **performance**: NOT_ISOLATED
- **comparison**: NONE
- **campaign_results**: []
- **actual_choice_difference**: See evidence and scope; no feature-off timing
- **allowed_claim**: 공통 통제 설정
- **forbidden_claim**: FA 켜서 얻은 신규 성과
- **unknown**: 본 감사에서 모든 attention node 직접 계수 안 함

## custom-prefill-attn — 별도 custom Prefill attention

- **donor_repo**: local archived overlay
- **donor_ref**: 59abec45fe0919de20550ce7cdcf363d9f7bbe5a + prefill-attention-v2
- **donor_path_symbol**: src/llama-graph.cpp / GGML_NEWA_PREFILL_ATTN
- **upstream_shared_ancestor**: 5219055a578fd741e029e81fefef6f3a5695086d for shared phase/profile; Linux scx_simple where stated; local base 59abec45fe0919de20550ce7cdcf363d9f7bbe5a
- **already_in_B0**: NO
- **already_in_B1**: present optional
- **final_source**: 최종 활성 source hunk 없음 또는 cases 공통 설정; 근거 경로 참조
- **change**: 코드는 누적 libllama에 있지만 실제 env off.
- **ancestry**: LOCAL_NEW
- **build_flags**: GGML_NEWA_PREFILL_ATTN=off
- **project_ELF_DSO_sha256**: 최종 해당 기능 ELF 없음; 공통 runtime identity는 frozen-release-map 참조
- **adoption**: {"A_L": "PRESENT_DISABLED", "A_S": "PRESENT_DISABLED", "P": "PRESENT_DISABLED"}
- **execution**: {"A_L": "NOT_ENABLED", "A_S": "NOT_ENABLED", "P": "NOT_ENABLED"}
- **runtime_evidence**: ["evidence/scheduler-attachments.json", "observed-usage.json", "evidence/identity-recheck.json", "evidence/static-elf.json", "evidence/preserved/a-component-scheduler-replication-v1/frozen-release-map.json"]
- **observed_unit_denominator**: off env; 일반 FA on과 독립
- **performance**: NOT_MEASURED
- **comparison**: NONE
- **campaign_results**: []
- **actual_choice_difference**: See evidence and scope; no feature-off timing
- **allowed_claim**: 미사용 후보로 공개
- **forbidden_claim**: 일반 FA on이 이 custom 후보 사용 증거
- **unknown**: 해당 후보별 과거 성능은 최종 몫으로 계산 안 함

## common-workload — 동일 모델·slot KV·동시성 설정

- **donor_repo**: ggml-org/llama.cpp
- **donor_ref**: historical B0
- **donor_path_symbol**: server model/KV/parallel options
- **upstream_shared_ancestor**: 5219055a578fd741e029e81fefef6f3a5695086d for shared phase/profile; Linux scx_simple where stated; local base 59abec45fe0919de20550ce7cdcf363d9f7bbe5a
- **already_in_B0**: YES
- **already_in_B1**: YES
- **final_source**: 최종 활성 source hunk 없음 또는 cases 공통 설정; 근거 경로 참조
- **change**: 동일 weights, parallel8/no-kv-unified, 정상 요청내 KV, cache 재사용 금지, speculationnone/GPU0.
- **ancestry**: UPSTREAM_UNCHANGED
- **build_flags**: same cases/protocol
- **project_ELF_DSO_sha256**: 최종 해당 기능 ELF 없음; 공통 runtime identity는 frozen-release-map 참조
- **adoption**: {"A_L": "ACTIVE_DEFAULT", "A_S": "ACTIVE_EVALUATION_ONLY", "P": "TESTED_NOT_ADOPTED"}
- **execution**: {"A_L": "OBSERVED_EXECUTED", "A_S": "OBSERVED_EXECUTED", "P": "OBSERVED_EXECUTED"}
- **runtime_evidence**: ["evidence/scheduler-attachments.json", "observed-usage.json", "evidence/identity-recheck.json", "evidence/static-elf.json", "evidence/preserved/a-component-scheduler-replication-v1/frozen-release-map.json"]
- **observed_unit_denominator**: 8 distinct request atomic cohort; 1024 actual generated tokens/HTTP window
- **performance**: NOT_ISOLATED
- **comparison**: NONE
- **campaign_results**: []
- **actual_choice_difference**: See evidence and scope; no feature-off timing
- **allowed_claim**: 기존 기능·공정한 비교 조건
- **forbidden_claim**: 이 설정들을 새 scheduler 기여로 계산
- **unknown**: 다른 arrival/concurrency/model 일반화 미측정

## topology — topology detection 참조와 frozen tier config

- **donor_repo**: euichan0418/new-a-llm-scheduler
- **donor_ref**: a9be0785177a6679cb2cb76e1d334a05e6b3734d
- **donor_path_symbol**: portable/topology.py; tools/sched_ext/new_a/topology.py; loader topology map
- **upstream_shared_ancestor**: 5219055a578fd741e029e81fefef6f3a5695086d for shared phase/profile; Linux scx_simple where stated; local base 59abec45fe0919de20550ce7cdcf363d9f7bbe5a
- **already_in_B0**: NO
- **already_in_B1**: scheduler separate
- **final_source**: /home/codinghuman/projects/new-a-workspace/scheduler/loader.c:48 / SHA256 005f9f2a5b6d740c300bc60668af4cb1af6eb051d40dca8d6466bca33dbbc6c1 / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/scheduler-loader.txt)
- **change**: 탐지 계열 참조, 최종 실험은 고정 6 physical CPU config를 로드/검증; 전체 자동 설정 optimizer 사용 아님.
- **ancestry**: SHARED_ANCESTRY
- **build_flags**: topology enabled1, counts6/0/0
- **project_ELF_DSO_sha256**: {"/home/codinghuman/projects/new-a-workspace/scheduler/loader": "bb3e08930bf3538c6c82d1f21353cbca0f5b89a00cef3ae1169725c568424735", "/home/codinghuman/projects/new-a-workspace/scheduler/full_object.bpf.o": "cb63e744df618ae46e2fe101d842fb7fefed51e2dd581daef80662322b358c47", "/home/codinghuman/projects/new-a-workspace/scheduler/llama_scx_child": "ac4d0bb2a127803e246970bfee3528bfa5a13676ccfc5d923e3290b43a2747df"}
- **adoption**: {"A_L": "PRESENT_DISABLED", "A_S": "ACTIVE_EVALUATION_ONLY", "P": "PRESENT_DISABLED"}
- **execution**: {"A_L": "NOT_ENABLED", "A_S": "OBSERVED_EXECUTED", "P": "NOT_ENABLED"}
- **runtime_evidence**: ["evidence/scheduler-aggregate.json", "evidence/preserved/a-component-scheduler-replication-v1/scheduler-identity.json"]
- **observed_unit_denominator**: tier0/1/2 counts; fallback는 tier3 카운터
- **performance**: NOT_ISOLATED
- **comparison**: NONE
- **campaign_results**: []
- **actual_choice_difference**: See evidence and scope; no feature-off timing
- **allowed_claim**: AMD homogeneous tier0 배치 사용
- **forbidden_claim**: Intel P/E/SMT 최적 정책이 이 장비에서 시험됨
- **unknown**: 각 topology 정책의 개별 author 및 성능 분리 없음

## selected-loader — selected-child와 loader/uProbe 실제 연결

- **donor_repo**: euichan0418/new-a-llm-scheduler
- **donor_ref**: a9be0785177a6679cb2cb76e1d334a05e6b3734d
- **donor_path_symbol**: tools/sched_ext/base loader / llama_scx_child.c
- **upstream_shared_ancestor**: 5219055a578fd741e029e81fefef6f3a5695086d for shared phase/profile; Linux scx_simple where stated; local base 59abec45fe0919de20550ce7cdcf363d9f7bbe5a
- **already_in_B0**: NO
- **already_in_B1**: separate existing scheduler foundation
- **final_source**: /home/codinghuman/projects/new-a-workspace/scheduler/llama_scx_child.c:168 / SHA256 93638218e23ccacd061b35594e69c4900fef382918ec715fda55278cb263ba11 / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/selected-child.txt); /home/codinghuman/projects/new-a-workspace/scheduler/neutral_lifecycle.c:344 / SHA256 65ab6db95be1c94faa6bcd38de9d3d9c4c2b95408ee14221b6b3ccb51f2709b5 / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/scheduler-lifecycle.txt); /home/codinghuman/projects/new-a-workspace/scheduler/loader.c:48 / SHA256 005f9f2a5b6d740c300bc60668af4cb1af6eb051d40dca8d6466bca33dbbc6c1 / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/scheduler-loader.txt)
- **change**: 선택 child만 SCHED_EXT, UID1000 inference; loader/launcher ordinary Linux; marker ELF에 scalar uprobe.
- **ancestry**: SHARED_ANCESTRY
- **build_flags**: SCX_OPS_SWITCH_PARTIAL; selected TGID registration
- **project_ELF_DSO_sha256**: {"/home/codinghuman/projects/new-a-workspace/scheduler/loader": "bb3e08930bf3538c6c82d1f21353cbca0f5b89a00cef3ae1169725c568424735", "/home/codinghuman/projects/new-a-workspace/scheduler/full_object.bpf.o": "cb63e744df618ae46e2fe101d842fb7fefed51e2dd581daef80662322b358c47", "/home/codinghuman/projects/new-a-workspace/scheduler/llama_scx_child": "ac4d0bb2a127803e246970bfee3528bfa5a13676ccfc5d923e3290b43a2747df"}
- **adoption**: {"A_L": "PRESENT_DISABLED", "A_S": "ACTIVE_EVALUATION_ONLY", "P": "PRESENT_DISABLED"}
- **execution**: {"A_L": "NOT_ENABLED", "A_S": "OBSERVED_EXECUTED", "P": "NOT_ENABLED"}
- **runtime_evidence**: ["evidence/scheduler-attachments.json", "observed-usage.json", "evidence/identity-recheck.json", "evidence/static-elf.json", "evidence/preserved/a-component-scheduler-replication-v1/frozen-release-map.json", "observed-usage.json"]
- **observed_unit_denominator**: 36 A_S visits: timed32+admission4; each selected policy7
- **performance**: NOT_ISOLATED
- **comparison**: NONE
- **campaign_results**: []
- **actual_choice_difference**: See evidence and scope; no feature-off timing
- **allowed_claim**: 커널까지 실제 통합 실행
- **forbidden_claim**: build 성공만으로 적용 주장 / 모든 시스템 작업 교체
- **unknown**: callback별 별도 수익 없음

## dsq-vtime — idle tier/local DSQ/shared weighted-vtime

- **donor_repo**: euichan0418/new-a-llm-scheduler
- **donor_ref**: a9be0785177a6679cb2cb76e1d334a05e6b3734d
- **donor_path_symbol**: llama_select_cpu/enqueue/dispatch/stopping; Linux v6.17 scx_simple basis
- **upstream_shared_ancestor**: 5219055a578fd741e029e81fefef6f3a5695086d for shared phase/profile; Linux scx_simple where stated; local base 59abec45fe0919de20550ce7cdcf363d9f7bbe5a
- **already_in_B0**: NO research scheduler
- **already_in_B1**: existing scheduler foundation
- **final_source**: /home/codinghuman/projects/new-a-workspace/scheduler/handoff.bpf.c:249 / SHA256 c54dfa5b73e9eb09c981be8e9608b1c62c51ed950ed0468aa79a1f982520c736 / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/scheduler.txt)
- **change**: bounded online/affinity tier scan; idle local, 나머지 shared DSQ; slice*100/weight vtime.
- **ancestry**: SHARED_ANCESTRY
- **build_flags**: observe; fixed affinity; SCX_OPS_SWITCH_PARTIAL
- **project_ELF_DSO_sha256**: {"/home/codinghuman/projects/new-a-workspace/scheduler/loader": "bb3e08930bf3538c6c82d1f21353cbca0f5b89a00cef3ae1169725c568424735", "/home/codinghuman/projects/new-a-workspace/scheduler/full_object.bpf.o": "cb63e744df618ae46e2fe101d842fb7fefed51e2dd581daef80662322b358c47", "/home/codinghuman/projects/new-a-workspace/scheduler/llama_scx_child": "ac4d0bb2a127803e246970bfee3528bfa5a13676ccfc5d923e3290b43a2747df"}
- **adoption**: {"A_L": "PRESENT_DISABLED", "A_S": "ACTIVE_EVALUATION_ONLY", "P": "PRESENT_DISABLED"}
- **execution**: {"A_L": "NOT_ENABLED", "A_S": "OBSERVED_EXECUTED", "P": "NOT_ENABLED"}
- **runtime_evidence**: ["observed-usage.json", "evidence/scheduler-aggregate.json", "sources/patches/public-to-observe-bpf.patch"]
- **observed_unit_denominator**: select tier/fallback callback counts, running/stopping whole visit
- **performance**: NOT_ISOLATED
- **comparison**: NONE
- **campaign_results**: []
- **actual_choice_difference**: See evidence and scope; no feature-off timing
- **allowed_claim**: 공통 sched_ext 기반 위 topology 파생 실행
- **forbidden_claim**: DSQ/vtime를 팀 고유 발명 또는 isolated gain으로 표기
- **unknown**: common hunk 최초 저자 일부 UNKNOWN

## observe-phase — observe phase 수신과 counter

- **donor_repo**: euichan0418/new-a-llm-scheduler
- **donor_ref**: a9be0785177a6679cb2cb76e1d334a05e6b3734d
- **donor_path_symbol**: llama_phase uprobe / current_phase; local handoff observe derivative
- **upstream_shared_ancestor**: 5219055a578fd741e029e81fefef6f3a5695086d for shared phase/profile; Linux scx_simple where stated; local base 59abec45fe0919de20550ce7cdcf363d9f7bbe5a
- **already_in_B0**: NO
- **already_in_B1**: separate scheduler foundation
- **final_source**: /home/codinghuman/projects/new-a-workspace/scheduler/handoff.bpf.c:249 / SHA256 c54dfa5b73e9eb09c981be8e9608b1c62c51ed950ed0468aa79a1f982520c736 / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/scheduler.txt); /home/codinghuman/projects/new-a-workspace/src/llama/tools/server/server-scx.h:11 / SHA256 655e62843596e98e66920b6b8d12e868ea0a01df96a5020c0ee6cc86d26f303f / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/phase-bridge.txt)
- **change**: phase는 state/bitmap과 Decode attempt counter로 전달; CPU placement는 phase-independent.
- **ancestry**: BORROWED_MODIFIED
- **build_flags**: NEW_A_DIAGNOSTICS; no NEW_A_IDLE_HANDOFF
- **project_ELF_DSO_sha256**: {"/home/codinghuman/projects/new-a-workspace/scheduler/loader": "bb3e08930bf3538c6c82d1f21353cbca0f5b89a00cef3ae1169725c568424735", "/home/codinghuman/projects/new-a-workspace/scheduler/full_object.bpf.o": "cb63e744df618ae46e2fe101d842fb7fefed51e2dd581daef80662322b358c47", "/home/codinghuman/projects/new-a-workspace/scheduler/llama_scx_child": "ac4d0bb2a127803e246970bfee3528bfa5a13676ccfc5d923e3290b43a2747df"}
- **adoption**: {"A_L": "PRESENT_DISABLED", "A_S": "ACTIVE_EVALUATION_ONLY", "P": "PRESENT_DISABLED"}
- **execution**: {"A_L": "NOT_ENABLED", "A_S": "OBSERVED_EXECUTED", "P": "NOT_ENABLED"}
- **runtime_evidence**: ["observed-usage.json", "evidence/feedback-search.json"]
- **observed_unit_denominator**: phase_seen14는 1/2/3 관측 bitmap; event count 아님
- **performance**: NOT_ISOLATED
- **comparison**: NONE
- **campaign_results**: []
- **actual_choice_difference**: See evidence and scope; no feature-off timing
- **allowed_claim**: phase 관측 연결 입증
- **forbidden_claim**: phase-dependent kernel placement 또는 kernel->E feedback
- **unknown**: 전환 횟수 및 measured-only delta 미수집

## handoff-off — phase-dependent idle-handoff 미활성 코드

- **donor_repo**: local handoff overlay
- **donor_ref**: preserved observe build
- **donor_path_symbol**: try_idle_handoff / NEW_A_IDLE_HANDOFF
- **upstream_shared_ancestor**: 5219055a578fd741e029e81fefef6f3a5695086d for shared phase/profile; Linux scx_simple where stated; local base 59abec45fe0919de20550ce7cdcf363d9f7bbe5a
- **already_in_B0**: NO
- **already_in_B1**: not B1 runtime
- **final_source**: /home/codinghuman/projects/new-a-workspace/scheduler/handoff.bpf.c:249 / SHA256 c54dfa5b73e9eb09c981be8e9608b1c62c51ed950ed0468aa79a1f982520c736 / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/scheduler.txt)
- **change**: source 조건부 이동 분기 존재; observe compilation에는 빠짐. attempt는 셀 수 있으나 moved0.
- **ancestry**: LOCAL_NEW
- **build_flags**: NEW_A_IDLE_HANDOFF absent; FG_GUARD absent
- **project_ELF_DSO_sha256**: {"/home/codinghuman/projects/new-a-workspace/scheduler/loader": "bb3e08930bf3538c6c82d1f21353cbca0f5b89a00cef3ae1169725c568424735", "/home/codinghuman/projects/new-a-workspace/scheduler/full_object.bpf.o": "cb63e744df618ae46e2fe101d842fb7fefed51e2dd581daef80662322b358c47", "/home/codinghuman/projects/new-a-workspace/scheduler/llama_scx_child": "ac4d0bb2a127803e246970bfee3528bfa5a13676ccfc5d923e3290b43a2747df"}
- **adoption**: {"A_L": "PRESENT_DISABLED", "A_S": "PRESENT_DISABLED", "P": "PRESENT_DISABLED"}
- **execution**: {"A_L": "NOT_ENABLED", "A_S": "NOT_ENABLED", "P": "NOT_ENABLED"}
- **runtime_evidence**: ["evidence/scheduler-aggregate.json", "evidence/preserved/a-component-scheduler-replication-v1/inputs/compile.log"]
- **observed_unit_denominator**: moved0 in every A_S raw visit
- **performance**: NOT_MEASURED
- **comparison**: NONE
- **campaign_results**: []
- **actual_choice_difference**: See evidence and scope; no feature-off timing
- **allowed_claim**: 관측과 이동 결정을 구분
- **forbidden_claim**: Decode handoff가 최종 성능 향상 원인
- **unknown**: 다른 handoff 후보 성적을 이 final에 합치지 않음

## FULL-diagnostics — FULL 진단 포함한 scheduler 순효과

- **donor_repo**: euichan0418/new-a-llm-scheduler
- **donor_ref**: a9be0785177a6679cb2cb76e1d334a05e6b3734d
- **donor_path_symbol**: NEW_A_DIAGNOSTICS / new_a_stats
- **upstream_shared_ancestor**: 5219055a578fd741e029e81fefef6f3a5695086d for shared phase/profile; Linux scx_simple where stated; local base 59abec45fe0919de20550ce7cdcf363d9f7bbe5a
- **already_in_B0**: NO
- **already_in_B1**: separate existing full diagnostics
- **final_source**: /home/codinghuman/projects/new-a-workspace/scheduler/handoff.bpf.c:249 / SHA256 c54dfa5b73e9eb09c981be8e9608b1c62c51ed950ed0468aa79a1f982520c736 / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/scheduler.txt); /home/codinghuman/projects/new-a-workspace/scheduler/loader.c:48 / SHA256 005f9f2a5b6d740c300bc60668af4cb1af6eb051d40dca8d6466bca33dbbc6c1 / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/scheduler-loader.txt); /home/codinghuman/projects/new-a-workspace/scheduler/monitor.h:71 / SHA256 0a0f0c0257c3e551cb741214d26ed71d19431a931a0057681dd476eeebe1832d / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/monitor.txt)
- **change**: 최종 FULL BPF와 loader; Lite나 plain 객체 아님.
- **ancestry**: SHARED_ANCESTRY
- **build_flags**: NEW_A_DIAGNOSTICS defined; HANDOFF_MODE=observe
- **project_ELF_DSO_sha256**: {"/home/codinghuman/projects/new-a-workspace/scheduler/loader": "bb3e08930bf3538c6c82d1f21353cbca0f5b89a00cef3ae1169725c568424735", "/home/codinghuman/projects/new-a-workspace/scheduler/full_object.bpf.o": "cb63e744df618ae46e2fe101d842fb7fefed51e2dd581daef80662322b358c47", "/home/codinghuman/projects/new-a-workspace/scheduler/llama_scx_child": "ac4d0bb2a127803e246970bfee3528bfa5a13676ccfc5d923e3290b43a2747df"}
- **adoption**: {"A_L": "PRESENT_DISABLED", "A_S": "ACTIVE_EVALUATION_ONLY", "P": "PRESENT_DISABLED"}
- **execution**: {"A_L": "NOT_ENABLED", "A_S": "OBSERVED_EXECUTED", "P": "NOT_ENABLED"}
- **runtime_evidence**: ["evidence/scheduler-attachments.json", "observed-usage.json", "evidence/identity-recheck.json", "evidence/static-elf.json", "evidence/preserved/a-component-scheduler-replication-v1/frozen-release-map.json", "evidence/performance-recalculation.json"]
- **observed_unit_denominator**: A_S/A_L each condition8 blocks in each of2 campaigns
- **performance**: NO_CONSISTENT_GAIN
- **comparison**: A_S/A_L
- **campaign_results**: [{"campaign": "original", "condition": "ambient", "contrast": "A_S/A_L", "mean": 0.032869584746740566, "ci": [-0.29844289625725606, 0.3412242419400621], "faster": 5}, {"campaign": "original", "condition": "cpu25", "contrast": "A_S/A_L", "mean": -0.6168544568614751, "ci": [-1.6861540894849507, 0.4487251663983144], "faster": 2}, {"campaign": "replication", "condition": "ambient", "contrast": "A_S/A_L", "mean": 0.7453105494634196, "ci": [0.37454940824115796, 1.1165267996539248], "faster": 7}, {"campaign": "replication", "condition": "cpu25", "contrast": "A_S/A_L", "mean": -1.2555163899982333, "ci": [-1.8030025353573205, -0.6970869622379638], "faster": 2}]
- **actual_choice_difference**: Same frozen runtime for scheduler contrast; P/A has matching E choices; bundle contrasts change multiple features
- **allowed_claim**: FULL 포함 순효과는 조건/캠페인 의존
- **forbidden_claim**: 계측 비용 임의 차감 후 큰 scheduler gain 주장
- **unknown**: Lite 대비 overhead counterfactual 없음

## fixed-guard — fixed-affinity live monitor/watchdog/cleanup

- **donor_repo**: euichan0418/new-a-llm-scheduler
- **donor_ref**: a9be0785177a6679cb2cb76e1d334a05e6b3734d
- **donor_path_symbol**: selected-child lifecycle / local monitor.h
- **upstream_shared_ancestor**: 5219055a578fd741e029e81fefef6f3a5695086d for shared phase/profile; Linux scx_simple where stated; local base 59abec45fe0919de20550ce7cdcf363d9f7bbe5a
- **already_in_B0**: NO
- **already_in_B1**: existing safety foundation
- **final_source**: /home/codinghuman/projects/new-a-workspace/scheduler/monitor.h:71 / SHA256 0a0f0c0257c3e551cb741214d26ed71d19431a931a0057681dd476eeebe1832d / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/monitor.txt); /home/codinghuman/projects/new-a-workspace/scheduler/neutral_lifecycle.c:344 / SHA256 65ab6db95be1c94faa6bcd38de9d3d9c4c2b95408ee14221b6b3ccb51f2709b5 / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/scheduler-lifecycle.txt); /home/codinghuman/projects/new-a-workspace/scheduler/llama_scx_child.c:168 / SHA256 93638218e23ccacd061b35594e69c4900fef382918ec715fda55278cb263ba11 / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/selected-child.txt)
- **change**: worker mask/policy 검사, kernel monitor와 owned-child 정리; dynamic-affinity 미해결 경계 유지.
- **ancestry**: BORROWED_MODIFIED
- **build_flags**: FULL loader monitor; absence of FG_GUARD macro does not disable this monitor
- **project_ELF_DSO_sha256**: {"/home/codinghuman/projects/new-a-workspace/scheduler/loader": "bb3e08930bf3538c6c82d1f21353cbca0f5b89a00cef3ae1169725c568424735", "/home/codinghuman/projects/new-a-workspace/scheduler/full_object.bpf.o": "cb63e744df618ae46e2fe101d842fb7fefed51e2dd581daef80662322b358c47", "/home/codinghuman/projects/new-a-workspace/scheduler/llama_scx_child": "ac4d0bb2a127803e246970bfee3528bfa5a13676ccfc5d923e3290b43a2747df"}
- **adoption**: {"A_L": "PRESENT_DISABLED", "A_S": "ACTIVE_EVALUATION_ONLY", "P": "PRESENT_DISABLED"}
- **execution**: {"A_L": "NOT_APPLICABLE", "A_S": "OBSERVED_EXECUTED", "P": "NOT_APPLICABLE"}
- **runtime_evidence**: ["observed-usage.json", "evidence/preserved/a-component-scheduler-replication-v1/scheduler-identity.json"]
- **observed_unit_denominator**: mask/tracking/event-drop 오류0; live monitor PASS for recorded visits
- **performance**: NOT_ISOLATED
- **comparison**: NONE
- **campaign_results**: []
- **actual_choice_difference**: See evidence and scope; no feature-off timing
- **allowed_claim**: 측정 범위에서 적용/안전 검사 통과
- **forbidden_claim**: 모든 kernel/CPU mask에서 안전 / dynamic-affinity 해결
- **unknown**: 새 전역 모드·다른 mask 미시험

## pool-donor — donor persistent pool 소유/재사용

- **donor_repo**: hsju2021/llama.cpp-fork
- **donor_ref**: 21537a585728a8afe62a32003457248172b74f68
- **donor_path_symbol**: tools/server/server-threadpool.h; parent5cd6b0ea
- **upstream_shared_ancestor**: 5219055a578fd741e029e81fefef6f3a5695086d for shared phase/profile; Linux scx_simple where stated; local base 59abec45fe0919de20550ce7cdcf363d9f7bbe5a
- **already_in_B0**: NO
- **already_in_B1**: NO
- **final_source**: /home/codinghuman/projects/new-a-workspace/experiments/r-pool-validation-v1/candidates/P-padding-fix/overlay/tools/server/server-threadpool.h:8 / SHA256 61a61c12907cf122ed5de90ef1fb9acb80531e39a86b56b9ccd314d0736fde58 / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/P-owner.txt); /home/codinghuman/projects/new-a-workspace/experiments/r-pool-validation-v1/candidates/P-padding-fix/overlay/tools/server/server-context.cpp:1280 / SHA256 378d0f745e44b4da887820fc85bef3c143170bb5a949c3c5633ac198809a7410 / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/P-context.txt)
- **change**: header는 donor byte-identical; P server ownership/attach/teardown는 local adaptation. A server에는 donor owner 미포함.
- **ancestry**: BORROWED_EXACT
- **build_flags**: P donor: generation5/batch6, poll50, normal, unrestricted; final A off
- **project_ELF_DSO_sha256**: {"A_runtime": {"libggml.so.0.18.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libmtmd.so.0": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "llama-server": "da9eaf0a3de17353dc2c7cab31c44a75e8f5c43b24efdb8d8cf675b3fec649fe", "libmtmd.so.0.0.10249": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libggml-base.so.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama-common.so.0.0.10249": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libmtmd.so": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so.0.18.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama.so": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libggml.so.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so.0.18.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libllama-common.so": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libllama-server-impl.so": "9204b0d4e45d4b5437c61417afe912d55618ce62ece6b6adf83ca7967dbe8cfc", "libggml.so": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libllama.so.0": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama.so.0.0.10249": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama-common.so.0": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libggml-cpu.so.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6"}, "P_runtime": {"libggml.so.0.18.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libmtmd.so.0": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "llama-server": "da9eaf0a3de17353dc2c7cab31c44a75e8f5c43b24efdb8d8cf675b3fec649fe", "libmtmd.so.0.0.10249": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libggml-base.so.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama-common.so.0.0.10249": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libmtmd.so": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so.0.18.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama.so": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libggml.so.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so.0.18.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libllama-common.so": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libllama-server-impl.so": "250671e9d6a21c467d7a20582682c77fd514f11f3aff308ca6a50c67d463f2fd", "libggml.so": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libllama.so.0": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama.so.0.0.10249": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama-common.so.0": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libggml-cpu.so.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6"}}
- **adoption**: {"A_L": "TESTED_NOT_ADOPTED", "A_S": "TESTED_NOT_ADOPTED", "P": "TESTED_NOT_ADOPTED"}
- **execution**: {"A_L": "NOT_ENABLED", "A_S": "NOT_ENABLED", "P": "OBSERVED_EXECUTED"}
- **runtime_evidence**: ["evidence/scheduler-attachments.json", "observed-usage.json", "evidence/identity-recheck.json", "evidence/static-elf.json", "evidence/preserved/a-component-scheduler-replication-v1/frozen-release-map.json", "evidence/preserved/r-pool-validation-v1/evidence/AP-lifecycle-summary.json"]
- **observed_unit_denominator**: P steady512 attached/A512 disposable; P creation6/free6 including2resume
- **performance**: NO_CONSISTENT_GAIN
- **comparison**: P/A
- **campaign_results**: [{"condition": "ambient", "n": 4, "mean": -1.6546492449760946, "ci": [-3.3043124379872446, -0.004986051964944727], "faster": 1, "gains": [-3.612212004947968, -2.9964128710265214, 0.4022361069162761, -0.41220821084616555], "raw_tps": [{"block": 1, "A": 59.22667494314104, "P": 57.08728188071339}, {"block": 2, "A": 58.22165290744971, "P": 56.4770918060065}, {"block": 3, "A": 57.03024175221286, "P": 57.2596379764019}, {"block": 4, "A": 57.28199986419288, "P": 57.04587875741579}]}, {"condition": "cpu25", "n": 4, "mean": 1.0510832539163988, "ci": [0.17762574820798516, 2.26676904623182], "faster": 3, "gains": [-0.0403433903688577, 2.8269664714156706, 0.8315331639385137, 0.586176770680269], "raw_tps": [{"block": 1, "A": 51.8240480431404, "P": 51.80314046513341}, {"block": 2, "A": 51.37781313438322, "P": 52.83024668543882}, {"block": 3, "A": 51.78237846279872, "P": 52.21296611279305}, {"block": 4, "A": 51.14333287009128, "P": 51.443123207127435}]}]
- **actual_choice_difference**: Same frozen runtime for scheduler contrast; P/A has matching E choices; bundle contrasts change multiple features
- **allowed_claim**: 실제 이식·모델 검증 후 mixed pilot으로 보류
- **forbidden_claim**: pool이 최종 A 개선율을 만들었다 / OS worker 생성 제거
- **unknown**: limited n4 pilot; OpenMP paused pool은 native park 아님

## pool-port — P의 선택 이식과 padding guard 수정

- **donor_repo**: local P overlay
- **donor_ref**: method.patch + P-padding-compatibility.patch
- **donor_path_symbol**: server ownership/reset and override validation
- **upstream_shared_ancestor**: 5219055a578fd741e029e81fefef6f3a5695086d for shared phase/profile; Linux scx_simple where stated; local base 59abec45fe0919de20550ce7cdcf363d9f7bbe5a
- **already_in_B0**: NO
- **already_in_B1**: NO
- **final_source**: /home/codinghuman/projects/new-a-workspace/experiments/r-pool-validation-v1/candidates/P-padding-fix/overlay/tools/server/server-context.cpp:1280 / SHA256 378d0f745e44b4da887820fc85bef3c143170bb5a949c3c5633ac198809a7410 / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/P-context.txt)
- **change**: donor owner와 context 해제 순서; parser의 null4096 항목을 실제 override와 구분. 원래 실패 보존.
- **ancestry**: LOCAL_NEW
- **build_flags**: P-only full server link; arithmetic DSOs byte-identical A
- **project_ELF_DSO_sha256**: {"A_runtime": {"libggml.so.0.18.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libmtmd.so.0": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "llama-server": "da9eaf0a3de17353dc2c7cab31c44a75e8f5c43b24efdb8d8cf675b3fec649fe", "libmtmd.so.0.0.10249": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libggml-base.so.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama-common.so.0.0.10249": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libmtmd.so": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so.0.18.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama.so": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libggml.so.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so.0.18.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libllama-common.so": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libllama-server-impl.so": "9204b0d4e45d4b5437c61417afe912d55618ce62ece6b6adf83ca7967dbe8cfc", "libggml.so": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libllama.so.0": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama.so.0.0.10249": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama-common.so.0": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libggml-cpu.so.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6"}, "P_runtime": {"libggml.so.0.18.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libmtmd.so.0": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "llama-server": "da9eaf0a3de17353dc2c7cab31c44a75e8f5c43b24efdb8d8cf675b3fec649fe", "libmtmd.so.0.0.10249": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libggml-base.so.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama-common.so.0.0.10249": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libmtmd.so": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so.0.18.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama.so": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libggml.so.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so.0.18.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libllama-common.so": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libllama-server-impl.so": "250671e9d6a21c467d7a20582682c77fd514f11f3aff308ca6a50c67d463f2fd", "libggml.so": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libllama.so.0": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama.so.0.0.10249": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama-common.so.0": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libggml-cpu.so.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6"}}
- **adoption**: {"A_L": "TESTED_NOT_ADOPTED", "A_S": "TESTED_NOT_ADOPTED", "P": "TESTED_NOT_ADOPTED"}
- **execution**: {"A_L": "NOT_ENABLED", "A_S": "NOT_ENABLED", "P": "OBSERVED_EXECUTED"}
- **runtime_evidence**: ["evidence/scheduler-attachments.json", "observed-usage.json", "evidence/identity-recheck.json", "evidence/static-elf.json", "evidence/preserved/a-component-scheduler-replication-v1/frozen-release-map.json", "evidence/preserved/r-pool-validation-v1/candidates/P-padding-fix/validation.json"]
- **observed_unit_denominator**: functional/cancel/error/sleep-resume 진단과 별도 pilot
- **performance**: NOT_ISOLATED
- **comparison**: NONE
- **campaign_results**: []
- **actual_choice_difference**: See evidence and scope; no feature-off timing
- **allowed_claim**: 연결·lifecycle 정확성의 제한 증거
- **forbidden_claim**: known baseline UAF 해결 또는 OOM 완전복구
- **unknown**: 기존 bug를 추정하지 않음; 전체 server failure space 미시험

## pool-old — 기존 optional 단일 pool

- **donor_repo**: local pre-R overlay
- **donor_ref**: 59abec45fe0919de20550ce7cdcf363d9f7bbe5a + optional pool
- **donor_path_symbol**: server_context GGML_NEWA_POOL=on
- **upstream_shared_ancestor**: 5219055a578fd741e029e81fefef6f3a5695086d for shared phase/profile; Linux scx_simple where stated; local base 59abec45fe0919de20550ce7cdcf363d9f7bbe5a
- **already_in_B0**: NO
- **already_in_B1**: YES optional
- **final_source**: /home/codinghuman/projects/new-a-workspace/src/llama/tools/server/server-context.cpp:541 / SHA256 85a9650aada34a5b0b726ac427dbe268ac625442f15ec68a7674c1520d455685 / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/semantic-origin.txt)
- **change**: max threads 하나/poll0로 두 역할 연결하는 old on 경로; donor 두 role poll50과 다름.
- **ancestry**: LOCAL_NEW
- **build_flags**: GGML_NEWA_POOL=off final
- **project_ELF_DSO_sha256**: {"A_runtime": {"libggml.so.0.18.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libmtmd.so.0": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "llama-server": "da9eaf0a3de17353dc2c7cab31c44a75e8f5c43b24efdb8d8cf675b3fec649fe", "libmtmd.so.0.0.10249": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libggml-base.so.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama-common.so.0.0.10249": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libmtmd.so": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so.0.18.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama.so": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libggml.so.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so.0.18.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libllama-common.so": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libllama-server-impl.so": "9204b0d4e45d4b5437c61417afe912d55618ce62ece6b6adf83ca7967dbe8cfc", "libggml.so": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libllama.so.0": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama.so.0.0.10249": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama-common.so.0": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libggml-cpu.so.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6"}, "P_runtime": {"libggml.so.0.18.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libmtmd.so.0": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "llama-server": "da9eaf0a3de17353dc2c7cab31c44a75e8f5c43b24efdb8d8cf675b3fec649fe", "libmtmd.so.0.0.10249": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libggml-base.so.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama-common.so.0.0.10249": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libmtmd.so": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so.0.18.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama.so": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libggml.so.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so.0.18.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libllama-common.so": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libllama-server-impl.so": "250671e9d6a21c467d7a20582682c77fd514f11f3aff308ca6a50c67d463f2fd", "libggml.so": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libllama.so.0": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama.so.0.0.10249": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama-common.so.0": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libggml-cpu.so.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6"}}
- **adoption**: {"A_L": "PRESENT_DISABLED", "A_S": "PRESENT_DISABLED", "P": "PRESENT_DISABLED"}
- **execution**: {"A_L": "NOT_ENABLED", "A_S": "NOT_ENABLED", "P": "NOT_ENABLED"}
- **runtime_evidence**: ["evidence/scheduler-attachments.json", "observed-usage.json", "evidence/identity-recheck.json", "evidence/static-elf.json", "evidence/preserved/a-component-scheduler-replication-v1/frozen-release-map.json"]
- **observed_unit_denominator**: A raw NEWA_POOL attached=0
- **performance**: NOT_MEASURED
- **comparison**: NONE
- **campaign_results**: []
- **actual_choice_difference**: See evidence and scope; no feature-off timing
- **allowed_claim**: pool off와 API active를 구분
- **forbidden_claim**: 이 old pool이 donor pool과 동일
- **unknown**: old on 성능을 final donor 성과로 사용 안 함

## v2-unadopted — v2 active/idle phase state

- **donor_repo**: hsju2021/llama.cpp-fork
- **donor_ref**: 44c95d5eb264b1665c6cff2862c4b9b4a115ad43
- **donor_path_symbol**: 32-byte phase ABI/state notifications
- **upstream_shared_ancestor**: 5219055a578fd741e029e81fefef6f3a5695086d for shared phase/profile; Linux scx_simple where stated; local base 59abec45fe0919de20550ce7cdcf363d9f7bbe5a
- **already_in_B0**: NO
- **already_in_B1**: NO
- **final_source**: 최종 활성 source hunk 없음 또는 cases 공통 설정; 근거 경로 참조
- **change**: 검토 pin만 존재; final scalar v1에 active/idle 이벤트 없음.
- **ancestry**: UNKNOWN
- **build_flags**: not compiled/linked in final A/P
- **project_ELF_DSO_sha256**: 최종 해당 기능 ELF 없음; 공통 runtime identity는 frozen-release-map 참조
- **adoption**: {"A_L": "REVIEWED_ONLY", "A_S": "REVIEWED_ONLY", "P": "REVIEWED_ONLY"}
- **execution**: {"A_L": "NOT_ENABLED", "A_S": "NOT_ENABLED", "P": "NOT_ENABLED"}
- **runtime_evidence**: ["evidence/donor-v2-commit.json", "evidence/static-elf.json"]
- **observed_unit_denominator**: NOT_APPLICABLE
- **performance**: NOT_MEASURED
- **comparison**: NONE
- **campaign_results**: []
- **actual_choice_difference**: See evidence and scope; no feature-off timing
- **allowed_claim**: 미채택 후속 기능 공개
- **forbidden_claim**: v2 idle 정밀 phase timer 이미 적용
- **unknown**: 저장소 내부 donor 계보는 별개; final hunk 없음

## lite-unadopted — Runtime Lite

- **donor_repo**: euichan0418/new-a-llm-scheduler
- **donor_ref**: a9be0785177a6679cb2cb76e1d334a05e6b3734d
- **donor_path_symbol**: Runtime Lite / optional elapsed diagnostics
- **upstream_shared_ancestor**: 5219055a578fd741e029e81fefef6f3a5695086d for shared phase/profile; Linux scx_simple where stated; local base 59abec45fe0919de20550ce7cdcf363d9f7bbe5a
- **already_in_B0**: NO
- **already_in_B1**: NO final adoption
- **final_source**: 최종 활성 source hunk 없음 또는 cases 공통 설정; 근거 경로 참조
- **change**: public 설명 검토; 최종 객체는 FULL.
- **ancestry**: UNKNOWN
- **build_flags**: FULL; no Lite timing arm
- **project_ELF_DSO_sha256**: 최종 해당 기능 ELF 없음; 공통 runtime identity는 frozen-release-map 참조
- **adoption**: {"A_L": "REVIEWED_ONLY", "A_S": "REVIEWED_ONLY", "P": "REVIEWED_ONLY"}
- **execution**: {"A_L": "NOT_ENABLED", "A_S": "NOT_ENABLED", "P": "NOT_ENABLED"}
- **runtime_evidence**: ["evidence/scheduler-pin-commit.json", "evidence/preserved/a-component-scheduler-replication-v1/scheduler-identity.json"]
- **observed_unit_denominator**: NOT_APPLICABLE
- **performance**: NOT_MEASURED
- **comparison**: NONE
- **campaign_results**: []
- **actual_choice_difference**: See evidence and scope; no feature-off timing
- **allowed_claim**: FULL 측정 범위 명시
- **forbidden_claim**: Lite 계측 제거 성과를 final로 이월
- **unknown**: Lite 독립 timing 없음

## intel-unadopted — Intel 4/8·P4+E4 결과/구성

- **donor_repo**: euichan0418/new-a-llm-scheduler
- **donor_ref**: a9be0785177a6679cb2cb76e1d334a05e6b3734d
- **donor_path_symbol**: NEW_A4/8 portable configurations
- **upstream_shared_ancestor**: 5219055a578fd741e029e81fefef6f3a5695086d for shared phase/profile; Linux scx_simple where stated; local base 59abec45fe0919de20550ce7cdcf363d9f7bbe5a
- **already_in_B0**: NO local test
- **already_in_B1**: NO local test
- **final_source**: 최종 활성 source hunk 없음 또는 cases 공통 설정; 근거 경로 참조
- **change**: 현재 AMD5/6, topology6/0/0; Intel 장비 실험은 이 감사에 없음.
- **ancestry**: UNKNOWN
- **build_flags**: no Intel runtime execution
- **project_ELF_DSO_sha256**: 최종 해당 기능 ELF 없음; 공통 runtime identity는 frozen-release-map 참조
- **adoption**: {"A_L": "REVIEWED_ONLY", "A_S": "REVIEWED_ONLY", "P": "REVIEWED_ONLY"}
- **execution**: {"A_L": "NOT_ENABLED", "A_S": "NOT_ENABLED", "P": "NOT_ENABLED"}
- **runtime_evidence**: ["evidence/scheduler-public-topology.json", "evidence/scheduler-aggregate.json"]
- **observed_unit_denominator**: NOT_APPLICABLE
- **performance**: NOT_MEASURED
- **comparison**: NONE
- **campaign_results**: []
- **actual_choice_difference**: See evidence and scope; no feature-off timing
- **allowed_claim**: 지원 확대 가설과 현 검증을 분리
- **forbidden_claim**: AMD gain에 Intel 결과 더하기 / 자동일반화
- **unknown**: 현재 Intel 검증과 threshold 재보정 미실행

## serving-harness — donor CPU serving benchmark harness

- **donor_repo**: hsju2021/llama.cpp-fork
- **donor_ref**: 4694fc88d00a2ded5783ce993e5eb28b4f6ec56f
- **donor_path_symbol**: tools/server/bench/cpu
- **upstream_shared_ancestor**: 5219055a578fd741e029e81fefef6f3a5695086d for shared phase/profile; Linux scx_simple where stated; local base 59abec45fe0919de20550ce7cdcf363d9f7bbe5a
- **already_in_B0**: NO at B0
- **already_in_B1**: NO direct reuse established
- **final_source**: 최종 활성 source hunk 없음 또는 cases 공통 설정; 근거 경로 참조
- **change**: 현재 실행은 보존된 Python campaign runner/HTTP 관측; donor harness 실행/직접 import 증거 없음.
- **ancestry**: UNKNOWN
- **build_flags**: current runner independent; donor reviewed only
- **project_ELF_DSO_sha256**: 최종 해당 기능 ELF 없음; 공통 runtime identity는 frozen-release-map 참조
- **adoption**: {"A_L": "REVIEWED_ONLY", "A_S": "REVIEWED_ONLY", "P": "REVIEWED_ONLY"}
- **execution**: {"A_L": "NOT_ENABLED", "A_S": "NOT_ENABLED", "P": "NOT_ENABLED"}
- **runtime_evidence**: ["evidence/donor-serving-commit.json", "evidence/usage-inputs.json"]
- **observed_unit_denominator**: 두 campaign protocol/order/HTTP raw
- **performance**: NOT_MEASURED
- **comparison**: NONE
- **campaign_results**: []
- **actual_choice_difference**: See evidence and scope; no feature-off timing
- **allowed_claim**: 참조 후보와 실제 runner를 구분
- **forbidden_claim**: donor 최신 harness가 final campaign을 수행
- **unknown**: 유사 benchmark 아이디어의 최초 저자/모든 hunk 복사 여부 UNKNOWN

## runtime-bundle — E 선택 제외 누적 runtime 묶음

- **donor_repo**: shared base + local overlays
- **donor_ref**: 59abec45fe0919de20550ce7cdcf363d9f7bbe5a
- **donor_path_symbol**: R arithmetic + frozen E server with fixed6
- **upstream_shared_ancestor**: 5219055a578fd741e029e81fefef6f3a5695086d for shared phase/profile; Linux scx_simple where stated; local base 59abec45fe0919de20550ce7cdcf363d9f7bbe5a
- **already_in_B0**: NO bundle
- **already_in_B1**: partially YES
- **final_source**: /home/codinghuman/projects/new-a-workspace/experiments/r-pool-validation-v1/candidates/R/overlay/ggml/src/ggml-cpu/newa-q4-policy.h:38 / SHA256 014ec3787142838295cb9e8193453ea504cf7a27f18c14a0fa6b8799fcd93029 / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/Q4-R.txt); /home/codinghuman/projects/new-a-workspace/src/llama/ggml/src/ggml-cpu/newa-q4-decode-exact.h:3 / SHA256 20d7bdc052650a53b6b5b7fabf81ec23d96aff4283c393ca3b9a23dcc98be62b / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/Q4-exact.txt); /home/codinghuman/projects/new-a-workspace/src/llama/ggml/src/ggml-cpu/newa-q6-policy.h:39 / SHA256 605cf933b96dc6ee4af7c635bdddb4dcdb04429d215b538bf0e59849f30b6d42 / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/Q6-policy.txt); /home/codinghuman/projects/new-a-workspace/src/llama/src/llama-context.cpp:2457 / SHA256 5e7b81b3ddcc851fcb0e9dbf49b6ba1cb663b677d25de2a2b8eca31d42670f0a / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/profile-engine.txt)
- **change**: F6_L도 E sensor/guards/phase를 유지하며 eligible multi Decode만 fixed6.
- **ancestry**: BORROWED_MODIFIED
- **build_flags**: same A binary; fixed6 mode
- **project_ELF_DSO_sha256**: {"A_runtime": {"libggml.so.0.18.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libmtmd.so.0": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "llama-server": "da9eaf0a3de17353dc2c7cab31c44a75e8f5c43b24efdb8d8cf675b3fec649fe", "libmtmd.so.0.0.10249": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libggml-base.so.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama-common.so.0.0.10249": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libmtmd.so": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so.0.18.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama.so": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libggml.so.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so.0.18.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libllama-common.so": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libllama-server-impl.so": "9204b0d4e45d4b5437c61417afe912d55618ce62ece6b6adf83ca7967dbe8cfc", "libggml.so": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libllama.so.0": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama.so.0.0.10249": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama-common.so.0": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libggml-cpu.so.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6"}, "P_runtime": {"libggml.so.0.18.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libmtmd.so.0": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "llama-server": "da9eaf0a3de17353dc2c7cab31c44a75e8f5c43b24efdb8d8cf675b3fec649fe", "libmtmd.so.0.0.10249": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libggml-base.so.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama-common.so.0.0.10249": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libmtmd.so": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so.0.18.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama.so": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libggml.so.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so.0.18.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libllama-common.so": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libllama-server-impl.so": "250671e9d6a21c467d7a20582682c77fd514f11f3aff308ca6a50c67d463f2fd", "libggml.so": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libllama.so.0": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama.so.0.0.10249": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama-common.so.0": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libggml-cpu.so.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6"}}
- **adoption**: {"A_L": "ACTIVE_DEFAULT", "A_S": "ACTIVE_EVALUATION_ONLY", "P": "TESTED_NOT_ADOPTED"}
- **execution**: {"A_L": "OBSERVED_EXECUTED", "A_S": "OBSERVED_EXECUTED", "P": "OBSERVED_EXECUTED"}
- **runtime_evidence**: ["evidence/scheduler-attachments.json", "observed-usage.json", "evidence/identity-recheck.json", "evidence/static-elf.json", "evidence/preserved/a-component-scheduler-replication-v1/frozen-release-map.json", "evidence/performance-recalculation.json"]
- **observed_unit_denominator**: condition별8 paired blocks
- **performance**: BUNDLE_EFFECT_ONLY
- **comparison**: F6_L/B0_L
- **campaign_results**: [{"campaign": "original", "condition": "ambient", "contrast": "F6_L/B0_L", "mean": 15.934377272085666, "ci": [15.451244558505604, 16.447818953664676], "faster": 8}, {"campaign": "original", "condition": "cpu25", "contrast": "F6_L/B0_L", "mean": 18.951725455315298, "ci": [14.71072593269863, 23.339445630430884], "faster": 8}, {"campaign": "replication", "condition": "ambient", "contrast": "F6_L/B0_L", "mean": 15.883744424525792, "ci": [15.212470767867412, 16.446321338549232], "faster": 8}, {"campaign": "replication", "condition": "cpu25", "contrast": "F6_L/B0_L", "mean": 15.255742119774634, "ci": [14.139067828475946, 16.363328047134996], "faster": 8}]
- **actual_choice_difference**: Same frozen runtime for scheduler contrast; P/A has matching E choices; bundle contrasts change multiple features
- **allowed_claim**: 누적 개선 묶음이 historical B0 rebuild보다 빠름
- **forbidden_claim**: Q4/Q6/API 각각의 몫 또는 runtime 전체 pure kernel effect
- **unknown**: per-kernel/component factorial 없음

## system-A-L — A_L 전체 직접 비교

- **donor_repo**: shared base + local overlays
- **donor_ref**: 59abec45fe0919de20550ce7cdcf363d9f7bbe5a E/R
- **donor_path_symbol**: frozen A composition
- **upstream_shared_ancestor**: 5219055a578fd741e029e81fefef6f3a5695086d for shared phase/profile; Linux scx_simple where stated; local base 59abec45fe0919de20550ce7cdcf363d9f7bbe5a
- **already_in_B0**: NO
- **already_in_B1**: NO R compatibility/E combined
- **final_source**: /home/codinghuman/projects/new-a-workspace/src/llama/tools/server/newa-prefill-pressure.h:22 / SHA256 944b2b546427fb97b7e5584c0a383ad97cbea04a987cf1a303fa69a4c01afe4d / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/E.txt); /home/codinghuman/projects/new-a-workspace/experiments/r-pool-validation-v1/candidates/R/overlay/ggml/src/ggml-cpu/newa-q4-policy.h:38 / SHA256 014ec3787142838295cb9e8193453ea504cf7a27f18c14a0fa6b8799fcd93029 / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/Q4-R.txt)
- **change**: Linux default 역할의 A; workspace run.sh 기본 경로와 다름.
- **ancestry**: BORROWED_MODIFIED
- **build_flags**: pressure + Linux
- **project_ELF_DSO_sha256**: {"A_runtime": {"libggml.so.0.18.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libmtmd.so.0": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "llama-server": "da9eaf0a3de17353dc2c7cab31c44a75e8f5c43b24efdb8d8cf675b3fec649fe", "libmtmd.so.0.0.10249": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libggml-base.so.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama-common.so.0.0.10249": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libmtmd.so": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so.0.18.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama.so": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libggml.so.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so.0.18.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libllama-common.so": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libllama-server-impl.so": "9204b0d4e45d4b5437c61417afe912d55618ce62ece6b6adf83ca7967dbe8cfc", "libggml.so": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libllama.so.0": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama.so.0.0.10249": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama-common.so.0": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libggml-cpu.so.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6"}, "P_runtime": {"libggml.so.0.18.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libmtmd.so.0": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "llama-server": "da9eaf0a3de17353dc2c7cab31c44a75e8f5c43b24efdb8d8cf675b3fec649fe", "libmtmd.so.0.0.10249": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libggml-base.so.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama-common.so.0.0.10249": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libmtmd.so": "81eb6c228d0c2281388f962717c820cf7847680fde7d191011ee098360397f52", "libggml-base.so.0.18.0": "a4dc4cd55be832cd880ba366d1cd498d7f6b017cd6166733b072d85a93ecd918", "libllama.so": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libggml.so.0": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libggml-cpu.so.0.18.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6", "libllama-common.so": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libllama-server-impl.so": "250671e9d6a21c467d7a20582682c77fd514f11f3aff308ca6a50c67d463f2fd", "libggml.so": "c1ae9bc8eebb243761a3d584b18022bee39727f89c3c6134b23c298fbb77049d", "libllama.so.0": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama.so.0.0.10249": "dcd9ba968ae8f641e82a2cf1860e7b883b68e578ee86fb2ffeab1d07f678a063", "libllama-common.so.0": "e2eb5251ae1947051645c24616efad8317fd9c16dddcb0a052c198d86f473877", "libggml-cpu.so.0": "45ddfa4d0e4815a4d3aee9fa1eb8a07a0e8ec768c245b57bf319e47704a960e6"}}
- **adoption**: {"A_L": "ACTIVE_DEFAULT", "A_S": "ACTIVE_EVALUATION_ONLY", "P": "TESTED_NOT_ADOPTED"}
- **execution**: {"A_L": "OBSERVED_EXECUTED", "A_S": "OBSERVED_EXECUTED", "P": "OBSERVED_EXECUTED"}
- **runtime_evidence**: ["evidence/scheduler-attachments.json", "observed-usage.json", "evidence/identity-recheck.json", "evidence/static-elf.json", "evidence/preserved/a-component-scheduler-replication-v1/frozen-release-map.json", "evidence/performance-recalculation.json", "evidence/entrypoint-scope.json"]
- **observed_unit_denominator**: two preserved campaigns; each condition8 paired blocks
- **performance**: BUNDLE_EFFECT_ONLY
- **comparison**: A_L/B0_L
- **campaign_results**: [{"campaign": "original", "condition": "ambient", "contrast": "A_L/B0_L", "mean": 16.203717550052072, "ci": [15.843334850495914, 16.579198893692595], "faster": 8}, {"campaign": "original", "condition": "cpu25", "contrast": "A_L/B0_L", "mean": 32.38963622307374, "ci": [27.699838221471573, 37.41691625355205], "faster": 8}, {"campaign": "replication", "condition": "ambient", "contrast": "A_L/B0_L", "mean": 15.406539770212758, "ci": [14.78550316219271, 15.927899998930538], "faster": 8}, {"campaign": "replication", "condition": "cpu25", "contrast": "A_L/B0_L", "mean": 29.228904608876466, "ci": [25.233338506306495, 33.619173970235444], "faster": 8}]
- **actual_choice_difference**: Same frozen runtime for scheduler contrast; P/A has matching E choices; bundle contrasts change multiple features
- **allowed_claim**: 전체 조합의 직접 paired 성과
- **forbidden_claim**: kernel scheduler가 필수 / 최신 upstream보다 빠름
- **unknown**: 외부 장비·새 prompt population 일반화 없음

## system-A-S — A_S 전체 직접 비교

- **donor_repo**: shared runtime + scheduler derivative
- **donor_ref**: 59abec45fe0919de20550ce7cdcf363d9f7bbe5a E/R + observe
- **donor_path_symbol**: A_S cases and loaded artifacts
- **upstream_shared_ancestor**: 5219055a578fd741e029e81fefef6f3a5695086d for shared phase/profile; Linux scx_simple where stated; local base 59abec45fe0919de20550ce7cdcf363d9f7bbe5a
- **already_in_B0**: NO
- **already_in_B1**: NO combined
- **final_source**: /home/codinghuman/projects/new-a-workspace/src/llama/tools/server/newa-prefill-pressure.h:22 / SHA256 944b2b546427fb97b7e5584c0a383ad97cbea04a987cf1a303fa69a4c01afe4d / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/E.txt); /home/codinghuman/projects/new-a-workspace/experiments/r-pool-validation-v1/candidates/R/overlay/ggml/src/ggml-cpu/newa-q4-policy.h:38 / SHA256 014ec3787142838295cb9e8193453ea504cf7a27f18c14a0fa6b8799fcd93029 / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/Q4-R.txt); /home/codinghuman/projects/new-a-workspace/scheduler/handoff.bpf.c:249 / SHA256 c54dfa5b73e9eb09c981be8e9608b1c62c51ed950ed0468aa79a1f982520c736 / [발췌](https://github.com/codinghuman0/llama-scheduler/blob/25ab433140eafc6cbb3b259b017c2a9252b37900/new-a-workspace/experiments/final-team-integration-audit-v1/sources/excerpts/scheduler.txt)
- **change**: A runtime + selected observe/FULL 평가 구성; donor pool 없음.
- **ancestry**: BORROWED_MODIFIED
- **build_flags**: pressure + observe/FULL
- **project_ELF_DSO_sha256**: {"/home/codinghuman/projects/new-a-workspace/scheduler/loader": "bb3e08930bf3538c6c82d1f21353cbca0f5b89a00cef3ae1169725c568424735", "/home/codinghuman/projects/new-a-workspace/scheduler/full_object.bpf.o": "cb63e744df618ae46e2fe101d842fb7fefed51e2dd581daef80662322b358c47", "/home/codinghuman/projects/new-a-workspace/scheduler/llama_scx_child": "ac4d0bb2a127803e246970bfee3528bfa5a13676ccfc5d923e3290b43a2747df"}
- **adoption**: {"A_L": "PRESENT_DISABLED", "A_S": "ACTIVE_EVALUATION_ONLY", "P": "PRESENT_DISABLED"}
- **execution**: {"A_L": "NOT_APPLICABLE", "A_S": "OBSERVED_EXECUTED", "P": "NOT_APPLICABLE"}
- **runtime_evidence**: ["evidence/scheduler-attachments.json", "observed-usage.json", "evidence/identity-recheck.json", "evidence/static-elf.json", "evidence/preserved/a-component-scheduler-replication-v1/frozen-release-map.json", "evidence/performance-recalculation.json"]
- **observed_unit_denominator**: two preserved campaigns; each condition8 paired blocks
- **performance**: BUNDLE_EFFECT_ONLY
- **comparison**: A_S/B0_L
- **campaign_results**: [{"campaign": "original", "condition": "ambient", "contrast": "A_S/B0_L", "mean": 16.24190951940772, "ci": [15.768904150043406, 16.739478898372035], "faster": 8}, {"campaign": "original", "condition": "cpu25", "contrast": "A_S/B0_L", "mean": 31.560919507348896, "ci": [26.5255352672458, 36.52006245002164], "faster": 8}, {"campaign": "replication", "condition": "ambient", "contrast": "A_S/B0_L", "mean": 16.26491255861004, "ci": [15.558195505556352, 16.842314182810497], "faster": 8}, {"campaign": "replication", "condition": "cpu25", "contrast": "A_S/B0_L", "mean": 27.5785589708236, "ci": [23.84055598702883, 31.858996035392945], "faster": 8}]
- **actual_choice_difference**: Same frozen runtime for scheduler contrast; P/A has matching E choices; bundle contrasts change multiple features
- **allowed_claim**: 커널 연결 포함 전체 시스템 성과
- **forbidden_claim**: 전체 gain이 scheduler 기여 / E와 scheduler 상승효과
- **unknown**: fixed6_S 없음; 완전한 E×scheduler interaction 미분리

