# Evaluation Materials

This directory contains the evaluation datasets, calibration materials, baseline implementations, and result files used to evaluate the Grounded Enterprise Policy & Procedure Assistant.

## 1. Final Evaluation Set

The final evaluation uses 22 frozen test cases stored in `ground_truth.json`.

The cases cover five behavioural groups:

- 5 normal answerable cases
- 5 boundary cases
- 5 ambiguous cases
- 5 insufficient-evidence cases
- 2 conflicting or superseded-policy cases

The final test set was frozen before the final evaluation and was kept separate from the calibration data.

The evaluation measures:

1. **Deterministic action correctness** — whether the system selected ANSWER, CLARIFY, or ABSTAIN correctly.
2. **Evidence grounding** — whether the retrieved evidence supports the expected case.
3. **Citation-grounded answer correctness** — whether the generated answer is correct and supported by its cited evidence.

## 2. Calibration Set

The calibration set contains 90 questions and is separate from the final 22-case evaluation set.

It was used to determine the deterministic routing thresholds for retrieval score and score margin.

The calibration set contains both in-corpus and out-of-corpus questions and was used before the final evaluation. The resulting thresholds were frozen before testing.

Final calibrated thresholds:

- `TOP_SCORE_MIN = 0.238864`
- `MARGIN_MIN = 0.030034`

The calibration procedure is described in `docs/abstention_methodology.md`.

## 3. Ground Truth

The ground-truth file defines the expected action, relevant evidence, and expected answer characteristics for the final evaluation cases.

It is used as the reference for calculating evaluation metrics.

## 4. Baselines

Two baselines are included:

### Majority-Class Baseline

This baseline always predicts the most common action in the frozen evaluation set.

It provides a simple reference point for decision accuracy.

### Keyword-Search Baseline

This baseline uses local keyword matching to retrieve relevant policy passages without the deterministic routing and Foundation Model generation layers.

It demonstrates the difference between retrieving relevant text and deciding whether the evidence is sufficient for an answer.

## 5. Evaluation Scripts

The evaluation scripts in this directory are used to reproduce the reported results.

They cover:

- final RAG evaluation
- retrieval evaluation
- deterministic decision evaluation
- baseline comparison
- failure analysis
- edge-case analysis

Please refer to the project `README.md` for environment setup and execution instructions.

## 6. Result Interpretation

The final results should not be interpreted as a single overall system accuracy.

Action correctness measures routing behaviour, while citation-grounded answer correctness measures the quality of generated answers on answerable cases.

The final evaluation achieved:

- 22/22 deterministic action correctness
- 17/17 evidence grounding
- 10/12 citation-grounded answer correctness
- 5/5 ambiguous-case clarification
- 5/5 insufficient-evidence abstention

The two answer-level failures are documented in the project's failure-analysis materials.