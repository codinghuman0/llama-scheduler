# Completed scoped R / E / pool research

{
  "R": "COMPATIBLE_IN_TESTED_SCOPE",
  "E-R": "COMPATIBLE_IN_TESTED_SCOPE",
  "Pool integration": "MODEL_VALIDATED",
  "Pool pilot": "REGRESSION",
  "Adoption": "REJECT_OR_HOLD",
  "note": "All required functional gates completed; limited prespecified pilot analyzed, not confirmation or B0 performance proof.",
  "pool_attempts": [
    {
      "revision": "prepared-P",
      "status": "FUNCTIONAL_FAIL",
      "evidence": "results/functional-heldout-1-P",
      "cause": "Null-padded override array rejected before HTTP readiness",
      "completed_HTTP_requests": 0
    },
    {
      "revision": "P-padding-fix",
      "status": "MODEL_VALIDATED",
      "patch": "patches/P-padding-compatibility.patch",
      "timing_observations": 8,
      "timing_campaign": "pilot-v1"
    }
  ],
  "diagnostic_attempts": [
    {
      "observer": "v1",
      "A": "PASS",
      "P": "INSTRUMENTATION_FAIL_MISSING_GETTER",
      "evidence": "results/lifecycle-P"
    },
    {
      "observer": "v2",
      "A": "PASS",
      "P": "PASS",
      "candidate_runtime_changed": false
    }
  ]
}

Fixed pilot completed; no extra pairs. R/A compatible in the declared model/fixtures/checkpoints; corrected P lifecycle validated. Results: integration-summary.md and results/pilot-v1/analysis.json. Original P and observer-v1 failures retained. Protected checkpoints: evidence/R-checkpoint.json and evidence/AP-functional-checkpoint.json. Protection and cleanup PASS.

Next explicit research step: A/B0 direct comparison protocol, not automatically run. Reproduce: ./reproduce.sh verify or ./reproduce.sh smoke. Review package metadata: review-zip.json.
