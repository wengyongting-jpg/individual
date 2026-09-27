# Stage 8 / 11 — Failure Analysis

This document records both the pre-Foundation-Model deterministic-stage findings and the final evaluation results. All 22 evaluation cases are examined; no cases are cherry-picked.

> **Frozen-asset note:** none of the reported final failures were fixed by changing the frozen thresholds (`TOP_SCORE_MIN = 0.238864`, `MARGIN_MIN = 0.030034`), calibration set, ground truth, or baseline after final evaluation. The thresholds were recalibrated once on 2026-09-19 after the corpus gained a 16th document and TC21/TC22 were added, as documented in `ground_truth.json` and the Stage 3 methodology. Further post-hoc threshold tuning would constitute test-set tuning.

---

## 1. Pre-Foundation-Model deterministic-stage findings

Before Foundation Model execution, the deterministic RAG pipeline had **8 action failures out of 22 cases**:

| Metric | Stage 3 result |
|---|---:|
| Total cases | 22 |
| Deterministic action failures | 8 |
| Retrieval failures | 3 |
| Decision failures | 5 |
| Normal | 5/5 |
| Ambiguous | 5/5 |

The three retrieval failures were TC06, TC07, and TC08, all boundary-value goods procurement questions. TC09 was a clarification over-trigger, TC16/17/19 were near-miss cases that passed the answerability threshold, and TC21 exposed a limitation of the margin signal when current and superseded versions of the same policy were both retrieved.

These findings were retained as part of the system-development history rather than being hidden or tuned away.

---

## 2. Final evaluation results

After Foundation Model execution, the deterministic routing layer was evaluated against the frozen 22-case ground truth:

| Metric | Final result |
|---|---:|
| Total cases | 22 |
| Deterministic action correctness | **22/22 (100%)** |
| Evidence grounding | **17/17 (100%)** |
| Citation-grounded answer correctness | **9/12 (75%)** |
| Ambiguous handling | **5/5 (100%)** |
| Insufficient-evidence handling | **5/5 (100%)** |
| Conflicting/outdated-policy handling | **2/2 (100%)** |

The 75% primary answer-correctness result is calculated only over the **12 cases expected to receive an answer**. It should therefore not be interpreted as an overall 75% accuracy rate for all 22 cases.

The final evaluation shows that the main residual problem is no longer deterministic routing: the routing layer achieved 22/22 action correctness. The remaining errors occur at the **answer synthesis and completeness** stage.

---

## 3. Final answer-level failures

Three of the 12 cases expected to receive an answer were judged incorrect in the manual rule-accuracy review.

### TC01 — Three quotations for goods procurement

- **Expected:** answer should identify the requirement for three quotations and the applicable standard goods ITQ template.
- **Observed:** the model correctly stated the three-quotation requirement but omitted the standard goods ITQ template requirement.
- **Failure type:** answer completeness / synthesis.
- **Retrieval status:** relevant evidence was available.
- **Root cause:** the model produced a partially correct summary but did not surface every material requirement contained in the retrieved evidence.

### TC08 — Open competitive procurement at $121,200

- **Expected:** formal tender or Request for Proposal, with approval by the Contracting Authority in consultation with Central Procurement Services.
- **Observed:** the model correctly identified the open competitive procurement process but omitted the approval and consultation requirements.
- **Failure type:** answer completeness / synthesis.
- **Retrieval status:** the relevant policy chunk was available.
- **Root cause:** the model selected the central procurement-method requirement but failed to include additional approval requirements from the same evidence.

### TC10 — Non-competitive consulting engagement at $1,000,000 or more

- **Expected:** additional Vice President or Executive Procurement Committee approval, in addition to the standard PPEJ process.
- **Observed:** the model correctly identified the additional higher-level approval but omitted that it applies in addition to the standard PPEJ process.
- **Failure type:** answer completeness / cross-passage synthesis.
- **Retrieval status:** the relevant higher-level approval evidence was retrieved, while the standard PPEJ context was represented elsewhere in the policy.
- **Root cause:** the model generated a correct core requirement but did not combine all material procedural conditions into the final answer.

---

## 4. What the final failures show

The three final failures share an important pattern:

> **The system can retrieve relevant evidence and make the correct deterministic routing decision, but retrieval correctness does not guarantee complete Foundation Model synthesis.**

The errors are therefore different from the earlier Stage 3 retrieval/decision failures. They are not primarily cases where the system selected the wrong action. Instead, the model produced answers that were substantively correct but incomplete.

This distinction is important for interpreting the 75% primary metric.

---

## 5. Cross-cutting observations

### 5.1 Retrieval and routing

The earlier Stage 3 failures show that lexical TF-IDF retrieval has difficulty with numerical boundary questions and that score-based answerability thresholds cannot perfectly separate near-miss evidence from genuinely answerable evidence.

However, these weaknesses did not translate into final deterministic action errors in the frozen 22-case evaluation. The final action layer achieved **22/22**.

### 5.2 Clarification

The clarification rule achieved **5/5** on the intentionally ambiguous cases. The earlier TC09 over-trigger is retained as a development-stage finding: a PPEJ-specific question was once classified as requiring clarification because the general goods-versus-services rule was broader than necessary.

The final evaluation should therefore report the measured 5/5 ambiguous handling result rather than presenting TC09 as a final action failure.

### 5.3 Insufficient evidence

All five insufficient-evidence cases were handled correctly in the final deterministic evaluation: **5/5**.

This supports the design choice to keep clarification and abstention outside the Foundation Model rather than asking the model to make the initial answerability decision.

### 5.4 Conflicting and outdated policy

Both conflicting/outdated-policy cases were routed correctly: **2/2**.

TC21 remains useful as a documented development-stage limitation. The margin signal can treat a current policy and its superseded edition as competing high-scoring evidence because both documents concern the same topic. This illustrates why a score-margin signal alone is not sufficient to distinguish conflicting versions from unrelated evidence.

TC22 was correctly routed to the Foundation Model. Manual grading subsequently confirmed whether the model surfaced the documented policy conflict rather than silently selecting one source.

---

## 6. Implications for future improvement

The final failures suggest improvements should focus on **answer completeness and evidence synthesis**, rather than simply lowering or raising the deterministic thresholds.

Potential future improvements include:

1. Explicitly require the model to enumerate all material requirements contained in retrieved evidence.
2. Add a checklist-style answer validation step for approval authority, procurement method, thresholds, exceptions, and procedural prerequisites.
3. Improve retrieval for multi-part procedural questions so related requirements are more consistently included in the model context.
4. Add a version-aware retrieval signal that distinguishes current policy from explicitly superseded documents.
5. Evaluate any future changes on a separate test set rather than tuning against the final 22 cases.

No such post-hoc changes were applied to the final reported results.

---

## 7. Final conclusion

The final evaluation indicates that the system's deterministic control layer is reliable on the frozen test set, achieving **22/22 action correctness** and **17/17 evidence grounding**. The principal remaining limitation is Foundation Model answer completeness: **9/12 answerable cases were judged fully correct**, while three answers omitted one or more material requirements despite relevant evidence being available.

The results therefore support the system's use as a **grounded decision-support prototype**, while also showing why human verification remains necessary before applying procurement policy in practice.