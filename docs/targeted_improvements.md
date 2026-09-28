# Stage 9 — Targeted Improvements

This document records targeted improvements identified from the development-stage failure analysis. The improvements are separated from the final evaluation results: a proposed improvement is not described as effective unless it was actually implemented and retested.

> **Frozen-asset constraint:** the final reported evaluation uses the frozen thresholds (`TOP_SCORE_MIN = 0.238864`, `MARGIN_MIN = 0.030034`), frozen calibration set, frozen ground truth, and frozen baseline. No post-hoc threshold tuning was performed against the final 22-case results.

## Improvement 1 — Numeric/threshold-aware retrieval signal

- **Problem identified:** the TF-IDF retriever struggled with boundary-value procurement questions because the relationship between a numerical amount and a policy tier is not well represented by lexical similarity.
- **Development-stage examples:** TC06, TC07, and TC08.
- **Proposed change:** add a general retrieval feature that detects a monetary amount in the question and boosts policy chunks containing tier ranges that bracket that amount.
- **Implementation status:** **Not applied to the final frozen pipeline.**
- **Future evaluation:** the feature should first be evaluated on a separate calibration/development set and, if adopted, new thresholds should be calibrated before evaluation on a new test set.
- **Reason for retaining as future work:** changing the retrieval signal would alter the frozen Stage-2/Stage-3 retrieval behaviour and would make direct comparison with the reported final results inappropriate.

## Improvement 2 — Optional neural embedding retriever

- **Problem identified:** TF-IDF provides lexical similarity but limited semantic matching for procurement roles, procedural relationships, and near-miss questions.
- **Proposed change:** implement a `SentenceTransformerRetriever` behind the existing retriever interface, allowing a neural embedding backend to be selected without rewriting the downstream pipeline.
- **Implementation status:** **Not applied to the final evaluation.**
- **Trade-off:** embeddings may improve semantic retrieval but introduce model dependencies, additional computation, and a new similarity distribution.
- **Evaluation requirement:** a new backend would require a separate calibration procedure using the same documented calibration principle before any test-set comparison.
- **Status:** **Future work.**

## Improvement 3 — Narrow the clarification trigger

- **Problem identified:** the development-stage clarification rule could over-trigger when a question contains a monetary amount and a decision term but does not actually require a goods-versus-services distinction.
- **Proposed change:** restrict clarification to decisions whose applicable rule genuinely diverges by procurement track, such as approval role, quotation requirements, or procurement method.
- **Implementation status:** **Not applied to the final frozen evaluation.**
- **Reason:** the final evaluation already achieved **5/5 correct handling on the ambiguous cases**, so changing the clarification rule solely to improve the historical TC09 case would constitute post-hoc tuning against the development/test cases.
- **Future evaluation:** test the refined rule on a separate development set containing both genuinely ambiguous and single-track questions.

## Improvement 4 — Additional answerability check

- **Problem identified:** development-stage near-miss cases could receive sufficiently high similarity scores to enter the Foundation Model path even when the evidence did not directly answer the question.
- **Proposed change:** add a second answerability check based on question-to-evidence coverage, or require the Foundation Model to perform an explicit evidence-sufficiency check before answering.
- **Final evaluation evidence:** the deterministic action layer ultimately handled all five insufficient-evidence cases correctly, achieving **5/5** on the final evaluation. Therefore, the reported system already demonstrates correct abstention behaviour on the frozen insufficient-evidence set.
- **Implementation status:** **No additional answerability mechanism was added after the final evaluation.**
- **Reason:** the final result does not justify post-hoc modification of the frozen decision thresholds or routing logic.
- **Future work:** evaluate a separate evidence-coverage check on an independent test set, particularly for near-miss questions.

## Improvement 5 — Conflict/supersession disclosure validation

The final Foundation Model evaluation revealed a different class of errors from the earlier deterministic-stage failures: two answerable cases were routed correctly with all relevant evidence cited, but the generated answer failed a disclosure requirement.

- **Observed final cases:** TC21 and TC22.
- **Problem:** TC21 cited the superseded 2019 policy edition without flagging it as superseded; TC22 cited both sides of a documented gift-policy conflict but answered with a bare "No." instead of disclosing the unreconciled conflict and recommending verification with the policy owner.
- **Proposed change:** add a deterministic post-generation validation step that requires the answer to disclose supersession and explicitly documented conflicts whenever such evidence is retrieved, with one constrained regeneration on failure.
- **Implementation status:** **Not applied to the reported final evaluation.**
- **Importance:** this is the main improvement area suggested by the final 10/12 citation-grounded answer correctness result.
- **Future evaluation:** test disclosure validation on a new set of conflicting/superseded policy questions rather than tuning it against TC21 or TC22.

## What was actually changed during development

The project added non-frozen components during Stages 4 onward, including the Foundation Model prompt, model client, answer pipeline, evaluation/comparison/failure-analysis scripts, tests, UI, and documentation.

One bug in the new `evaluation/evaluate.py` was fixed during development so that deterministic abstention messages were not incorrectly compared against expected answer text for rule-accuracy grading.

No frozen evaluation asset was modified to improve the final score, and no post-hoc threshold retuning was performed after the final 22-case evaluation.

## Overall status

The targeted improvements should be interpreted as **future engineering directions rather than hidden changes to the reported system**.

The final evaluation indicates that the deterministic routing layer is already strong on the frozen test set:

- **Action correctness: 22/22 (100%)**
- **Evidence grounding: 17/17 (100%)**
- **Citation-grounded answer correctness: 10/12 (83.33%)**

Consequently, future work should focus less on tuning the reported test-set thresholds and more on independent evaluation of retrieval robustness, version-aware evidence handling, and especially **guaranteeing conflict/supersession disclosure in the final answer**.