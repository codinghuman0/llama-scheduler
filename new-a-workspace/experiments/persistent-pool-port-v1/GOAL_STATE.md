# Persistent pool selective-port investigation

Status: WAITING_NUMERICAL_BASELINE.

The explicitly permitted investigation/model-free/source-preparation scope is finished. Current candidate is overlay/ only and is not installed in runtime/. B0/B1/E identities, historical pool results, four immutable donor/public pins, lifecycle/state reuse and actual DSO/marker binding were checked. See result-summary.md and integration-delta.md.

Applicable model-free gates passed in reproduce-1. HINT OFF full context still fails identically in original E and candidate; this inherited defect is disclosed. Initial failed harness attempt remains in regressions-1. Model-based functional/pilot observations: zero. No performance gain claimed.

Protected numerical runtime/source/model remain unchanged. Explicit user-requested workspace maintenance changed archive representation and seven non-numerical metadata/wrapper paths; evidence/protection-after.json reconciles these changes. No generated unit binaries or test processes remain; cleanup.json records the checks.

Frozen review contents: REVIEW-MANIFEST.json. ZIP validation and completion audit are external sidecars review-zip.json and completion-audit.json, generated after the content freeze; they are not recursively embedded in the ZIP. These sidecars are authoritative for packaging completion.

Recheck: bash experiments/persistent-pool-port-v1/reproduce.sh verify
Model-free replay: bash experiments/persistent-pool-port-v1/reproduce.sh model-free --output experiments/persistent-pool-port-v1/results/my-check-001

One next step: complete the separate R numerical compatibility baseline gate (next-step.md). Do not execute R work, model inference, a scheduler change, or performance confirmation as a continuation of this review-only package.
