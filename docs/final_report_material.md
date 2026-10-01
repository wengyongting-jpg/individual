# Final Report — Grounded RAG Assistant for Enterprise Procurement-Policy Questions

## 1. Problem Statement

Every purchase requires staff to apply the correct rule: how many quotations are needed, whose approval is required, and how both change at specific dollar values and between goods and services. The rules live in **16 policy documents — 15 current + 1 superseded edition — including one genuine cross-document contradiction**.

The affected users are **procurement and finance staff** preparing and approving purchases — policy appliers, not policy authors. Three failure modes follow from manual lookup: **slow retrieval delays purchase decisions**; **misremembered or out-of-context rules create compliance and audit risk**; and **outdated or conflicting editions let two staff members reach different answers to the same question**. Their concrete recurring tasks are approval-threshold lookup, quotation-requirement checks, goods-vs-services routing, and exception/split-purchase questions.

Existing keyword search mitigates none of this reliably: it returns passage lists but cannot determine which conditional rule applies to a specific amount, ask whether the purchase is goods or services, flag a superseded edition, say that no policy covers the question, or reconcile a contradiction. What staff need is not a document list but a correct, sourced decision — including an honest refusal when evidence is ambiguous or absent.

**Scope.** This project is a *policy-grounded decision-support assistant*: it performs retrieval, evidence assessment, clarification, abstention, and grounded answering. It does **not** approve, reject, place, or execute purchases and does not replace the human approver as the final decision-maker. The AI is the intervention tested against this independently established problem (§3–5).

## 2. Research Question

Can a grounded RAG-based assistant improve enterprise policy question answering compared with a keyword-search baseline while maintaining reliable abstention and evidence grounding?

## 3. System Design

```text
Question
  → Chunking (paragraph chunks of the 16 policy documents)
  → Retrieval (TF-IDF cosine, top-5)
  → Evidence signals (top_score, margin)
  → Deterministic decision layer (frozen thresholds, no model)
        CLARIFICATION_REQUIRED → clarifying question (no model call)
        ABSTAIN                 → fixed message       (no model call)
        ANSWERED_ELIGIBLE       → Foundation Model
  → Prompt contract (evidence as data; citations required)
  → Foundation Model (openai/gpt-4o-mini via OpenRouter)
  → Output validation
  → Answer / Clarification / Abstain
```

Retrieval, signals, and routing are deterministic and auditable; the model answers only eligible questions, cannot override an abstention, and must cite retrieved evidence.

## 4. Baseline

The baseline (`baseline/keyword_search.py`) is local, deterministic keyword search: zero API cost, ~0.117 ms median retrieval, top-3 grounding 1.00 (top-1 0.647) on the frozen set. Its limitations are structural — it always returns passages: it cannot synthesize an answer, ask for a missing detail, or deterministically abstain when evidence is insufficient. It also has no explicit mechanism for handling superseded or contradictory policy editions.

## 5. Proposed RAG System

- **TF-IDF retrieval with deterministic signals** — paragraph chunks ranked by cosine similarity plus auditable bonuses (+0.20 when the query amount lies in a chunk's stated range; +0.15 goods/services match); top-5 evidence pool.
- **Deterministic decision layer** — frozen thresholds (`TOP_SCORE_MIN = 0.238864`, `MARGIN_MIN = 0.030034`), calibrated on 90 disjoint questions and never tuned on test cases, route each question to answer, clarify, or abstain; a structured-evidence override and a multi-source carve-out handle numeric-boundary and current/superseded edges.
- **Grounded LLM generation** — openai/gpt-4o-mini answers only from retrieved evidence under a prompt contract; output is validated before display.
- **Clarification and abstention** — value-dependent goods-vs-services questions trigger clarification; weak evidence triggers abstention, with the model itself as a second line of defence.

## 6. Evaluation Methodology

The 16 documents (15 current + 1 superseded) were hand-authored with edge cases planted directly in the text (`docs/data_generation.md`). The evaluation set is 22 frozen cases: 5 normal, 5 boundary, 5 ambiguous, 5 insufficient-evidence, 2 conflicting/outdated. Thresholds were calibrated on 90 disjoint questions (66 answerable / 24 deliberately absent) via a pre-declared 10th-percentile rule; the 22 test cases were never used to tune them. Three metrics are reported separately with the course-required trivial baselines alongside: **decision/routing correctness**, **evidence grounding**, and human-graded **citation-grounded answer correctness** (primary). Per-case retrieval edges: `docs/retrieval_edge_cases.md`.

## 7. Results

Final executed run (all figures recomputed by `evaluation/compare.py`):

| Layer | Metric | Result |
|---|---|---:|
| Decision | Deterministic action correctness | **22/22 (100%)** |
| Baselines | Majority-class / keyword decision accuracy | 54.5% / 54.5% |
| Retrieval/evidence | Evidence grounding (RAG) | **17/17 (100%)** |
| Retrieval/evidence | Baseline top-3 / top-1 grounding | 1.00 / 0.647 |
| Answer | Citation-grounded answer correctness (primary) | **10/12 (83.33%)** |
| Behaviour | Ambiguous → clarification | 5/5 |
| Behaviour | Insufficient evidence → abstain | 5/5 |
| Behaviour | Conflicting/outdated policy (action level) | 2/2 |

The majority-class and keyword-search baselines both achieve 54.5% decision accuracy on the frozen label distribution. The majority-class baseline always predicts the most common action and therefore misclassifies the five ambiguous and five insufficient-evidence cases, while the keyword-search baseline returns passages without a deterministic mechanism for clarification or abstention. The remaining RAG errors are answer-disclosure omissions, not routing or retrieval errors.

All five insufficient-evidence cases ended as ABSTAIN: two stopped at the deterministic threshold layer (no model call); three passed it but were rejected by the model itself — a two-layer defence.

**Target vs measured.** The pre-registered secondary target — ≥50% reduction in median human task-completion time vs manual search — requires independent participants (the team authored the corpus and cannot time itself). **Participant data collection is pending; no participant data have been collected**, so no task-time result is measured or claimed. All figures above come from the executed automated evaluation.

## 8. Failure Analysis

The two final-answer failures share one pattern: the correct evidence — including the conflicting and superseded sources — was retrieved and cited, and routing was correct, but the generated answer failed a disclosure requirement.

| Case | Failure |
|---|---|
| TC21 | stated the current Ontario supplier preference but did not disclose that the cited 2019 policy edition is SUPERSEDED |
| TC22 | answered a bare "No." without disclosing the unreconciled gift-policy conflict between the two cited sources or recommending escalation |

So 83.33% is not a retrieval or routing failure but incomplete disclosure by the model on exactly the supersession/conflict cases that make the corpus realistic: grounding guarantees evidence reaches the model, not that it surfaces all of it. A deterministic post-generation disclosure check is the natural mitigation — future work, not tuned against these two cases.

## 9. Cost / Latency / Trade-off

Measured final run: 15 model calls over 22 cases (the deterministic layer resolves 7 with no call), total **US$0.004831** (45,246 tokens).

Assumed usage = 100 policy questions per workday × 250 workdays  
             = 25,000 questions/year

Observed model-call rate = 15/22 ≈ 68%  
                         → ~17,000 model calls/year

US$0.00022 is the observed amortised API cost per incoming question across the frozen 22-case evaluation set, including the 7 cases resolved without a model call.

Annual model API cost = 25,000 questions × US$0.00022 per question  
                      ≈ US$5.5 per year.

Latency: RAG retrieval ~2.79 ms; model median ~2,090 ms (P95 ~5,765 ms); end-to-end median ~1.55 s (P95 ~5.55 s). At this assumed workload, latency and API dependency, rather than the API bill, are the main operational constraints.

This buys what the baseline structurally lacks: cited answers, clarification (5/5), two-layer abstention (5/5), and conflict routing (2/2). Trade-off: answer completeness ↔ latency ↔ cost ↔ complexity.

## 10. Limitations

- The corpus is synthetic and small (16 documents); results should not be generalised.
- The evaluation set is small (22 frozen cases); 83.33% is measured on 12 answerable cases, so single cases move the number by 8 points.
- Foundation-model generation can omit required disclosures even when the conflicting or superseded evidence is retrieved and cited (TC21/TC22).
- Model latency (~2.1 s median, P95 ~5.8 s) is far above the baseline's; queries leave the organisation via the API, and with no key the system degrades to PENDING rather than answering.
- Task-time effectiveness is unmeasured: participant data collection for the pre-registered ≥50% target is pending (§7); claims cover correctness and system latency, not user productivity.

## 11. Conclusion

The results support a qualified answer to the research question. The assistant turns passage lists into cited answers (10/12 correct), clarifies underspecified questions (5/5), and abstains through two independent layers (5/5), with perfect routing (22/22) and grounding (17/17), compared with 54.5% decision accuracy for the baseline methods — at ~US$0.005 and ~1.6 s median per run. The honest boundary: grounding does not guarantee disclosure; both residual failures were supersession/conflict omissions. It is therefore best deployed as **grounded decision support with human verification**, retaining keyword search as the zero-cost fallback.