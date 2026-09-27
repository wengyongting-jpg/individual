# Stage 8 / 11 — Failure Analysis

Generated from **actual** results (`stage3_results.json`, `rag_retrieval_results.json`,
`rag_results.json`) via `evaluation/analyze_failures.py`. No cases are
cherry-picked — all 22 are examined. Final answer correctness for
`ANSWERED_ELIGIBLE` cases is **PENDING EXECUTION** (no API key) and is not scored
as pass/fail here.

> **Frozen-asset note:** none of these failures were "fixed" by changing the
> frozen thresholds (`TOP_SCORE_MIN = 0.238864`, `MARGIN_MIN = 0.030034`,
> recalibrated once on 2026-09-19 after the corpus gained a 16th document — see
> `ground_truth.json`'s `_meta.amendment`), the calibration set, ground truth,
> or the baseline. Doing so would be test-set tuning.

## Summary of actual results

| Metric | Value |
|---|---|
| Total cases | 22 |
| Deterministic action failures | 8 |
| — retrieval failures | 3 |
| — decision failures | 5 |
| Failures in `boundary` | 4 |
| Failures in `insufficient_evidence` | 3 |
| Failures in `conflicting_or_outdated_policy` | 1 |
| `ANSWERED_ELIGIBLE` cases pending model | 10 |

Perfect categories: **normal 5/5**, **ambiguous 5/5** (clarification detection).

---

## Failure records

### TC06 — goods purchase of exactly $75,000
- **Expected:** ANSWERED (goods Tier 3)
- **Observed:** ABSTAIN
- **Failure type:** retrieval_failure
- **Likely layer:** retrieval (TF-IDF cosine)
- **Evidence:** expected source `01_goods_thresholds_and_approval.txt` was not the
  top match; "procurement value" phrasing pulled `08_procurement_value_calculation.txt`;
  `top_score` fell below `TOP_SCORE_MIN`.
- **Root cause:** TF-IDF has no numeric/threshold reasoning; the literal tier
  text does not lexically resemble the question, and the exact amount is not a
  distinctive token.
- **Proposed fix:** add a lightweight numeric/threshold-aware retrieval signal or
  a neural embedding backend (behind the existing `Retriever` interface).
- **Retested?** No — proposed only (see `docs/targeted_improvements.md`).

### TC07 — goods purchase of $74,999
- **Expected:** ANSWERED (goods Tier 2) · **Observed:** ABSTAIN
- **Failure type:** retrieval_failure · **Layer:** retrieval
- **Evidence:** same pattern as TC06; boundary amount not lexically present.
- **Root cause / fix / retested:** as TC06. Not retested.

### TC08 — goods purchase of exactly $121,200
- **Expected:** ANSWERED (goods Tier 4) · **Observed:** ABSTAIN
- **Failure type:** retrieval_failure · **Layer:** retrieval
- **Evidence:** `top_score` below threshold; expected goods-tiers doc not focused.
- **Root cause / fix / retested:** as TC06. Not retested.

### TC09 — PPEJ required at exactly $25,000?
- **Expected:** ANSWERED (boundary) · **Observed:** CLARIFICATION_REQUIRED
- **Failure type:** decision_failure · **Layer:** decision (clarification rule)
- **Evidence:** the question mentions a dollar amount and a decision term
  ("required") without the words "goods"/"services", so `is_underspecified`
  fired even though the PPEJ rule is single-track.
- **Root cause:** the general goods-vs-services rule over-triggers on a
  PPEJ/non-competitive question that does not need the distinction.
- **Proposed fix:** narrow the clarification trigger to decisions that genuinely
  diverge by track (approval role / quote count / method), excluding PPEJ-only
  questions — as a **general rule**, not a TC09 special case.
- **Retested?** No — proposed only.

### TC16 — disciplinary action for policy violation
- **Expected:** ABSTAIN · **Observed:** ANSWERED (eligible → pending model)
- **Failure type:** decision_failure · **Layer:** decision (threshold)
- **Evidence:** an out-of-scope question scored above `TOP_SCORE_MIN` on
  tangential conduct/compliance passages (near-miss overlap seen in calibration).
- **Root cause:** cosine similarity cannot tell "topically related" from
  "actually answerable"; the two distributions overlap.
- **Proposed fix:** stricter margin handling or an answerability check; documented
  as future work (not tuned post-hoc).
- **Retested?** No.

### TC17 — supplier appeal process
- **Expected:** ABSTAIN · **Observed:** ANSWERED (eligible → pending model)
- **Failure type:** decision_failure · **Layer:** decision (threshold)
- **Evidence / root cause / fix / retested:** as TC16. Not retested.

### TC19 — record retention period before destruction
- **Expected:** ABSTAIN · **Observed:** ANSWERED (eligible → pending model)
- **Failure type:** decision_failure · **Layer:** decision (threshold)
- **Evidence:** record-keeping chunks ("retrievable for audit") score highly but
  never state a retention period — a classic near-miss.
- **Root cause / fix / retested:** as TC16. Not retested.

### TC21 — Ontario supplier preference under the provincial trade policy
- **Expected:** ANSWERED (current doc, citing the $121,200 cap) · **Observed:** ABSTAIN
- **Failure type:** decision_failure · **Layer:** decision (margin threshold)
- **Evidence:** `top_score` = 0.429246 (comfortably above `TOP_SCORE_MIN`); both
  the current document (`12_provincial_trade_policy.txt`) and the superseded
  2019 edition (`16_provincial_trade_policy_2019_superseded.txt`) are retrieved
  in the top-3, but their scores are close, so `margin` = 0.025416, just below
  the recalibrated `MARGIN_MIN` = 0.030034.
- **Root cause:** the margin signal is designed to catch evidence diffused
  across unrelated documents, but a current-vs-superseded pair of documents on
  the SAME topic produces the identical symptom (two competing sources, close
  scores) for a different reason — here the "competition" is exactly the
  conflict the case is designed to test, not noise.
- **Proposed fix:** none applied (would require distinguishing "diffuse across
  unrelated documents" from "close scores between a current and a document
  explicitly marked SUPERSEDED" — a genuine future-work item, not a threshold
  nudge). See `docs/abstention_methodology.md` §5.
- **Retested?** No — this is a newly-added case (2026-09-19); not proposed for
  a quick fix, since a real fix needs a different signal, not a different
  threshold value.

### TC22 — accepting a gift from a supplier
- **Expected:** ANSWERED (citing the conflict between doc13/doc14) · **Observed:** ANSWERED (eligible → pending model)
- **Outcome:** matches at the deterministic layer — not a failure. Whether the
  model, once executed, actually surfaces the conflict (prompt rule 9) rather
  than picking one side is **PENDING EXECUTION** and will be graded via
  `evaluation/results/rule_accuracy_manual.json`, not assumed.

---

## Cross-cutting observations

1. **Retrieval is the bottleneck for boundary cases.** All 3 retrieval failures
   are boundary dollar-amount questions. A lexical retriever cannot reason that
   "$74,999 falls in Tier 2." This is the strongest argument for a semantic
   embedding retriever or a numeric pre-processor.
2. **The abstention threshold cannot perfectly separate answerable from
   unanswerable** (documented in Stage 3). TC16/17/19 confirm the calibrated
   overlap on real cases.
3. **Clarification is high-precision but slightly over-eager** (TC09). The rule
   is correct on all 5 true ambiguous cases and misfires on one single-track
   boundary case.
4. **The Foundation Model may recover some cases**: TC16/17/19 currently route to
   the model as ANSWERED_ELIGIBLE; a well-prompted model instructed to abstain
   on insufficient evidence could still output ABSTAIN. Whether it does is
   **PENDING EXECUTION** and must be measured, not assumed.
5. **A new failure mode from the 2026-09-19 corpus amendment (TC21):** the
   margin signal cannot tell "diffuse evidence across unrelated documents"
   apart from "close scores between a current document and its own superseded
   edition on the same topic" — both look identical to the signal. This is a
   genuine limitation of a purely score-based concentration signal, reported
   here rather than patched by adjusting the frozen threshold.
