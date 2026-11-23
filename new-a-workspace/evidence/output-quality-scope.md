# Heldout reference quality review

Read-only review covered all32 measured outputs (2 fresh heldout cohorts ×8 requests × B0/B1) against complete prompts. evidence/heldout-output-differences.json independently records exact token/text differences. In each cohort, indices0,1,2,5 are identical and3,4,6,7 differ. First differing token indices are [2,7,10,7] for heldout1 and [123,10,5,2] for heldout2. Every input contains its full declared prompt+BOS (96–109 tokens, no256-token cap truncation). All32 outputs contain exactly128 generated tokens and stop_type=limit, truncated=false; temperature0, seed424242, ignore_eos=true. This controls generated work, not semantic answer quality.

Concrete observed failures:
- h1-a garden: both repeat the request for a dry-week example without a water allocation plan.
- h1-b museum: both invent and repeat vocabulary constraints instead of a workflow.
- h1-c configuration file: both echo the prompt and restate the problem rather than providing an atomic update sequence.
- h1-d vocabulary study: B0 starts discussing practice effects without completing the design; B1 repeats invented formatting instructions and _number_.
- h1-e download: B0 invents header/identifier requirements; B1 restates requirements; neither completes safe resume/verification/publish steps.
- h1-f bakery: both repeat batch assumptions without a usable schedule.
- h1-g reservation: B0 repeats an invented network-disconnection situation; B1 introduces unrelated login conditions; neither supplies transaction/idempotency handling.
- h1-h noise: B0 invents budget and sensor constraints; B1 reverses the prompt prohibition, asking for a summary that hides brief loud events or treats spikes as permanent.
- h2-a kitchen: both repeatedly refer to an unavailable ingredient table.
- h2-b payment and h2-c buses: both echo or add requirements without solving the requested design/comparison.
- h2-d recovery: both repeat the prompt and mention mistakes; the token difference begins only at123.
- h2-e insulation: B0 invents vocabulary restrictions; B1 lists terms then starts an incomplete analysis.
- h2-f robot and h2-g dashboard: outputs repeat requested requirements without the requested concrete plan/interface behavior.
- h2-h parts: B0 repeats/changes the question; B1 starts a monthly-average suggestion but does not complete a lead-time-aware policy.

The common128-token limit may explain incomplete endings; it does not erase already-visible repetition, invented constraints, or reversed instructions. No root cause is established by this review. Existing B0/B1 semantic equivalence or superiority is NOT established. C/C-off exact equality to B1 establishes preservation of that existing output only. Interpret primary results as throughput for the declared raw-completion compute workload, not correct/useful answers per second. These limitations are recorded without changing frozen workloads, policies or success gates.

Sources: runs/heldout-fixtures-v1/fixtures.json; runs/heldout-reference-v1/ambient/block-{1,2}/{B0,B1}/measured-responses.json. No confirmation performance results were used in this quality review.

---

# Output correctness and quality scope

This study's new-policy correctness requirement is exact deterministic token equality against the frozen NEW_A runtime B1. That check passed the initial policies and all eight `decode-cost-functional-v1` visits. It establishes no new output change on those requests, not general model quality.

The separately recorded B0/B1 difference is real: four of eight exploration outputs differ (indexes 3, 4, 6, 7). First differing token positions are recorded in `evidence/initial-correctness.json`. The raw responses for both runtimes remain in `runs/identity-smoke-v1/ambient/block-1/{B0,B1}`. The original model file and exact input token arrays are unchanged. This study has not established the cause of the pre-existing difference and does not label it harmless rounding.

A qualitative reading of indexes 0, 3, 4, 6 and 7 found limitations in both runtimes:

- Index 0 is identical but the 128-token budget ends during reasoning about the bicycle schedule, before a completed schedule.
- Index 3: B0 proposes an internally confused weather comparison involving rainy days in the dry observation weeks. B1 largely repeats the question and begins meta-commentary instead of completing the requested study design.
- Index 4: B0 echoes the question and empty answer headings; B1 echoes the question and only begins reasoning about the asynchronous-search problem.
- Index 6: B0 repeats definitions and conflates reorder point with safety stock/target level. B1 largely repeats the question and begins meta-commentary.
- Index 7: B0 repeats an operational checklist; B1 produces a different checklist and expresses uncertainty. Neither short output establishes a fully correct rollout procedure.

These are raw completion workloads with a fixed 128-token output budget, not a scored end-task or chat-quality evaluation. No semantic-quality equivalence between B0 and B1 has been established. Report throughput as generated-token processing on the declared workload; do not describe it as a measured increase in correct answers. New candidates must continue matching B1 exactly, and heldout/regression outputs will be preserved and checked separately.
# Regression reference addendum

This addendum concerns regression-reference-v1, not the earlier128-token batch8 exploration. The independent B0/B1 reference contains20 measured outputs: one single-short and one single-longer-input response per runtime, plus eight64-token responses per runtime. New C/C-off outputs are checked against these separate B1 references; they never create their own oracle.

- Single-short128: B0/B1 differ from token index3. B0 gives an incomplete schedule and one displayed work interval inconsistent with the supplied task durations. B1 restates durations and stops before a concrete schedule/bottleneck answer. Neither establishes task success.
- Single-longer-input128: text and tokens are identical between B0/B1. The client supplies a512-token prefix of the documentation, ending mid-table, while the explanation instruction remains at the beginning. Both outputs continue the CLI table, repeat the threads-batch row, and invent/mislabel option spellings. The truncated source format is a limitation of this input-length regression; it is not a complete-document comprehension assessment.
- Batch8 shorter-output64: indices0,1,2,5 match between B0/B1; indices3,4,6,7 differ. Both repeat a thread-safety assertion without the requested concrete fixes, echo several questions, and stop before complete answers. The inventory response in B0 conflates reorder point and safety stock; B1 largely echoes that question. Deployment outputs are different generic checklists without enough content to establish the requested rollback/dependency safeguards.

All these responses stop at the declared token limit. Server `truncated:false` does not mean a complete answer, and it does not undo the client's deliberate512-token input cap. `ignore_eos=True` and raw completion formatting are shared measurement controls. Sentence cutoffs cannot be separated from those limits. There is no semantic-quality equivalence or superiority claim for B0/B1, and no claim about normal chat completion quality. Exact new-policy/B1 equality shows no additional output change on these tested requests.

Raw sources: runs/regression-fixtures-v1/fixtures.json and runs/regression-reference-v1/ambient/block-{1,2,3}/{B0,B1}/measured-responses.json. The reference run's immutable manifest and evidence/regression-reference-audit.json bind these observations to the measured files.

