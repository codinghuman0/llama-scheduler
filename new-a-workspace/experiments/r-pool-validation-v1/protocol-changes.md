# Protocol changes recorded before inference/timing

The original persistent-pool-port-v1/protocol.json is retained unchanged. The current goal authorizes implementing R here; the previous externally-prepared-R waiting condition no longer applies.

A = validated R plus unchanged E, donor pool off. P = A plus exactly the prepared donor pool ownership patch. The oracle becomes validated R/B0, not numerically divergent B1. All paired counts, primary metric, order, cohort assignment, cpu25 budget/range, exclusion rules, bootstrap and decision thresholds remain unchanged. The two old generic arm labels now explicitly mean A/P.

The zero-observation pool draft said simultaneous individual requests. Preserved actual diagnosis and original study use one atomic prompt-array HTTP request. The current goal explicitly preserves that arrival. We correct the draft wording before new observations rather than change the actual workload. Request arrays/settings remain exact.

Gate R additionally separates the old diagnostic singleton (h1 request3, 109 prompt tokens) from the original pool regression singleton (single-short, 132). Neither replaces either eight-request cohort.

No new equivalence tolerance: the fixed target checkpoint gate requires identical inputs/profile, finite logits, identical argmax, zero maxabs and byte equality. This concerns only the tested scope, not general quality or all architectures.
