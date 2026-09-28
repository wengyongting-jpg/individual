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
| Citation-grounded answer correctness | **10/12 (83.33%)** |
| Ambiguous handling | **5/5 (100%)** |
| Insufficient-evidence handling | **5/5 (100%)** |
| Conflicting/outdated-policy handling | **2/2 (100%)** |

The 83.33% primary answer-correctness result is calculated only over the **12 cases expected to receive an answer**. It should therefore not be interpreted as an overall 83.33% accuracy rate for all 22 cases.

Failures fall into three distinct layers, and the final run cleanly separates them:

1. **Retrieval failures** — the expected source is not retrieved (development-stage examples: TC06/TC07/08 vocabulary mismatch, distractors, two-document retrieval). In the final run: **none** (evidence grounding 17/17).
2. **Decision-layer failures** — the wrong action is chosen (development-stage examples: TC09 over-eager clarification, TC16/17/19 threshold near-misses). In the final run: **none** (action correctness 22/22).
3. **Generation / synthesis failures** — retrieval was correct and the deterministic action was correct, but the Foundation Model's answer failed a disclosure requirement. In the final run: **2 cases** (TC21, TC22), detailed in §3.

The final evaluation shows that the main residual problem is no longer retrieval or deterministic routing: the routing layer achieved 22/22 action correctness. The remaining errors occur at the **answer-disclosure stage** on exactly the two cases (superseded policy, cross-document conflict) that make this corpus realistic.

---

## 3. Final answer-level failures

Two of the 12 cases expected to receive an answer were judged incorrect in
the manual rule-accuracy review (`evaluation/results/rule_accuracy_manual.json`).

| Case | Problem |
|---|---|
| TC21 | omitted the disclosure that the cited 2019 Provincial Trade Policy edition is SUPERSEDED (answer stated only the current regional preference) |
| TC22 | answered "No." without disclosing the unreconciled gift-policy conflict between `13_conflict_of_interest_policy.txt` and `14_procurement_governance_roles.txt`, and without recommending verification with the policy owner |

### TC21 — Ontario supplier preference (current vs superseded policy)

- **Expected:** the current Provincial Trade Policy gives Ontario-based suppliers a regional preference below $121,200, **and** the answer must flag that a 2019 edition of the same policy is superseded and must not be used.
- **Observed:** the model correctly stated the current regional preference and its threshold, and cited both the current and the superseded document — but did not state that the 2019 edition is superseded or that it must not be relied on.
- **Failure type:** answer disclosure / completeness (supersession handling).
- **Retrieval status:** both the current and the superseded policy chunks were retrieved and cited (grounding objective met).
- **Routing note:** TC21's evidence margin (0.0229) was below the frozen `MARGIN_MIN`, but the decision layer's multi-source carve-out (`rag/decision.py`) routes such cases to the model with a disclosure hint instead of abstaining — the routing action itself was correct.
- **Root cause:** the model synthesized the substantive current rule but treated the superseded source as background rather than flagging it, even though it appeared in the citations.

### TC22 — Accepting a gift from a supplier (documented conflict)

- **Expected:** the corpus contains two unreconciled rules; the answer must disclose the conflict explicitly, cite both sources, and recommend verification with the policy owner.
- **Observed:** the model answered only "No." — consistent with the absolute ban in `13_conflict_of_interest_policy.txt`, and it cited both conflicting sources, but it did not disclose that the corpus contains unreconciled rules and did not recommend escalation.
- **Failure type:** answer disclosure / completeness (conflict handling).
- **Retrieval status:** both conflicting policy chunks were retrieved and cited (grounding objective met).
- **Root cause:** the model silently selected one side of a documented conflict instead of surfacing the conflict — precisely the behaviour prompt rule 9 and the Stage 6 validator are designed to prevent, showing the residual risk when the model ignores the contract.

---

## 4. What the final failures show

The two final failures share an important pattern:

> **The system can retrieve all relevant — including conflicting — evidence and make the correct deterministic routing decision, but retrieval correctness does not guarantee that the Foundation Model's answer discloses supersession and conflicts.**

The errors are therefore different from the earlier Stage 3 retrieval/decision failures. They are not cases where the system selected the wrong action or missed the evidence. Instead, the model produced answers that were substantively defensible but omitted the disclosure that makes them safe to act on.

This distinction is important for interpreting the 83.33% primary metric.

---

## 5. Cross-cutting observations

### 5.1 Retrieval and routing

The earlier Stage 3 failures show that lexical TF-IDF retrieval has difficulty with numerical boundary questions and that score-based answerability thresholds cannot perfectly separate near-miss evidence from genuinely answerable evidence.

However, these weaknesses did not translate into final deterministic action errors in the frozen 22-case evaluation. The final action layer achieved **22/22**.

### 5.2 Clarification

The clarification rule achieved **5/5** on the intentionally ambiguous cases. The earlier TC09 over-trigger is retained as a development-stage finding: a PPEJ-specific question was once classified as requiring clarification because the general goods-versus-services rule was broader than necessary.

The final evaluation should therefore report the measured 5/5 ambiguous handling result rather than presenting TC09 as a final action failure.

### 5.3 Insufficient evidence

All five insufficient-evidence cases were ultimately handled as **ABSTAIN**: **5/5**.

Two of these (TC18, TC20) were abstained by the deterministic threshold layer
without any model call. Three (TC16, TC17, TC19) were initially eligible for
generation under the deterministic threshold but were subsequently rejected by
the Foundation Model because the retrieved evidence was insufficient — a
second line of defence.

This supports the design choice to keep clarification and abstention outside
the Foundation Model rather than asking the model to make the initial
answerability decision, and it shows that the model layer adds an additional
safety check for borderline evidence.

### 5.4 Conflicting and outdated policy

Both conflicting/outdated-policy cases were routed correctly to the Foundation Model: **2/2** at the action level — but both final **answers** were graded incorrect on disclosure (see §3).

TC21 remains useful as a documented limitation with two facets. First, the margin signal can treat a current policy and its superseded edition as competing high-scoring evidence (margin 0.0229, below `MARGIN_MIN`); the decision layer's multi-source carve-out routes such cases to the model with a disclosure hint instead of abstaining, so the routing action was still correct. Second, the generated answer failed to flag the supersession — so the safety net moved the case to the model, but the model did not complete the disclosure.

TC22 was also correctly routed, and both conflicting sources were cited, but the model's one-word answer did not disclose the unreconciled conflict or recommend escalation. Together these two cases locate the system's residual risk precisely: not in finding the right documents, but in guaranteeing that generated answers surface supersession and conflicts.

---

## 6. Implications for future improvement

The final failures suggest improvements should focus on **answer disclosure and completeness** (conflict/supersession surfacing), rather than simply lowering or raising the deterministic thresholds.

Potential future improvements include:

1. Add a deterministic post-generation check that requires explicit conflict/supersession disclosure whenever such evidence is retrieved, with one constrained regeneration on failure.
2. Explicitly require the model to enumerate all material requirements contained in retrieved evidence.
3. Add a checklist-style answer validation step for approval authority, procurement method, thresholds, exceptions, and procedural prerequisites.
4. Add a version-aware retrieval signal that distinguishes current policy from explicitly superseded documents.
5. Evaluate any future changes on a separate test set rather than tuning against the final 22 cases.

No such post-hoc changes were applied to the final reported results.

---

## 7. Final conclusion

The final evaluation indicates that the system's deterministic control layer is reliable on the frozen test set, achieving **22/22 action correctness** and **17/17 evidence grounding**. The principal remaining limitation is Foundation Model answer disclosure: **10/12 answerable cases were judged fully correct**, while two answers (TC21, TC22) failed to disclose supersession/conflict information despite the relevant — and conflicting — evidence being retrieved and cited.

The results therefore support the system's use as a **grounded decision-support prototype**, while also showing why human verification remains necessary before applying procurement policy in practice.