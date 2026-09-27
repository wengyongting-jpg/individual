# Stage 9 — Targeted Improvements (Proposed)

Derived **only** from the Stage 8 failure analysis of actual results. Each item
is a small, general change — no test-case IDs, no post-hoc threshold tuning.

> **Constraints honored:** the current frozen thresholds (`0.238864` /
> `0.030034`, recalibrated once on 2026-09-19 after the disclosed corpus
> amendment -- see `ground_truth.json`'s `_meta.amendment`), calibration set,
> ground truth, baseline, and Stage 1-3 results are **not** modified by any
> improvement below. Any improvement that would alter a frozen asset is listed
> as future work, to be calibrated on the separate calibration set — never on
> the 22 cases.
>
> **No improvement is claimed to work until retested.** Because the abstention
> thresholds are frozen and no Foundation Model has been executed, every retest
> below is **PENDING EXECUTION**. Un-retested changes have NOT been applied to
> the frozen pipeline.

## Improvement 1 — Numeric/threshold-aware retrieval signal

- **Targets:** TC06/07/08 (retrieval failures on boundary dollar amounts).
- **Before:** TF-IDF cosine ranks the value-calculation doc above the goods-tiers
  doc; exact amounts (`$74,999`) are not distinctive tokens; `top_score` < min → ABSTAIN.
- **Change (proposed, general):** add a retrieval feature that detects a dollar
  amount in the question and boosts chunks containing tier ranges that bracket
  that amount (e.g. "$75,000 to $121,199.99"). Implemented behind the existing
  `Retriever` interface so the baseline and frozen Stage-2 results are untouched.
- **After:** PENDING EXECUTION — would be evaluated on the calibration set first,
  then measured on the 22 cases without changing thresholds.

## Improvement 2 — Swap the retrieval backend to neural embeddings

- **Targets:** boundary + near-miss cases generally.
- **Before:** lexical similarity only; no semantic understanding of tiers/roles.
- **Change (proposed):** add a `SentenceTransformerRetriever` implementing the
  `Retriever` ABC (e.g. `all-MiniLM-L6-v2`), selectable by config. Requires a
  model download (~90 MB) + `sentence-transformers`; heavier, so kept optional.
- **After:** PENDING EXECUTION. Note: thresholds are calibrated for TF-IDF cosine;
  a new backend would require **re-running the calibration procedure** (same
  10th-percentile rule) to derive new frozen thresholds. Not done here.

## Improvement 3 — Narrow the clarification trigger

- **Targets:** TC09 (decision failure — over-eager clarification).
- **Before:** `is_underspecified = amount AND decision AND NOT track`. It fires on
  a PPEJ/non-competitive question that does not actually diverge by goods/services.
- **Change (proposed, general):** restrict the "decision" trigger for
  clarification to the rules that genuinely diverge by track (approval role,
  quote count, procurement method), and exclude PPEJ/exemption-only phrasing.
  This is a vocabulary refinement, not a TC09 special case.
- **After:** PENDING EXECUTION — would be checked on hand-written development
  questions (not the 22 cases) before adoption.

## Improvement 4 — Answerability check to reduce false non-abstention

- **Targets:** TC16/17/19 (insufficient-evidence cases not abstaining).
- **Before:** near-miss passages score above `TOP_SCORE_MIN`; the system routes
  them to the model as ANSWERED_ELIGIBLE.
- **Change (proposed):** rely on the Stage-4 prompt's rule 5 (model must ABSTAIN
  on insufficient evidence) as a second line of defence, and/or add a
  question-vs-topic coverage check. The prompt path already exists; whether the
  model actually abstains is measurable once a key is available.
- **After:** PENDING EXECUTION.

## What was actually changed in code during Stages 4–9

Only **non-frozen, additive** components were built (prompt, model client, answer
pipeline, evaluation/comparison/failure scripts, tests, UI, docs). One bug in the
**new** `evaluation/evaluate.py` was fixed during development (rule-accuracy must
not compare a deterministic abstention message to an expected answer). No frozen
asset was modified. No threshold was retuned.
