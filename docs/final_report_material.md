# Final Report — Grounded RAG Assistant for Enterprise Procurement-Policy Questions

## 1. Introduction / Problem

Procurement staff must apply the correct policy rule to every purchase: approval thresholds, quotation counts, and methods differ between goods and services and change at specific dollar values. The rules are spread across **16 policy documents — 15 current policy documents + 1 superseded policy edition** — including one genuine cross-document contradiction. Manual lookup is slow and error-prone, and acting on a misremembered or out-of-context rule creates compliance and audit risk. What staff need is not a list of documents but an answer: which rule applies, where it says so, and whether the available evidence is even sufficient. Traditional keyword search cannot provide that.

## 2. Research Question

Can a grounded RAG-based assistant improve enterprise policy question answering compared with a keyword-search baseline while maintaining reliable abstention and evidence grounding?

## 3. System Design

```
Question
  → Chunking (paragraph chunks of the 16 policy documents)
  → Retrieval (TF-IDF cosine, top-5)
  → Evidence signals (top_score, margin)
  → Deterministic decision layer (frozen thresholds, no model)
        CLARIFICATION_REQUIRED → clarifying question (no model call)
        ABSTAIN                → fixed message      (no model call)
        ANSWERED_ELIGIBLE      → Foundation Model
  → Prompt contract (evidence as data; citations required)
  → Foundation Model (openai/gpt-4o-mini via OpenRouter)
  → Output validation
  → Answer / Clarification / Abstain
```

Retrieval, signals, and routing are deterministic and auditable. The Foundation Model only synthesizes answers for answer-eligible questions; it cannot override an abstention, and every answer must cite retrieved evidence.

## 4. Baseline

The baseline (`baseline/keyword_search.py`) is traditional keyword search: zero API cost, fully local, deterministic. On the frozen 22-case set it achieves top-3 retrieval grounding of 1.00 (top-1 0.647) with ~0.117 ms median latency. Its limitations are structural: it cannot synthesize an answer, ask for a missing detail, refuse insufficient evidence, or flag a superseded or contradictory policy — it always returns passages, and for all five insufficient-evidence questions it returns near-misses.

## 5. Proposed RAG System

- **TF-IDF retrieval with deterministic signals** — paragraph chunks ranked by cosine similarity plus auditable bonuses (+0.20 when the query amount falls inside a chunk's stated range; +0.15 for goods/services domain match); the top 5 chunks form the evidence pool.
- **Deterministic decision layer** — frozen thresholds (`TOP_SCORE_MIN = 0.238864`, `MARGIN_MIN = 0.030034`), calibrated on 90 disjoint questions and never tuned on the test cases, route each question to answer, clarify, or abstain; a structured-evidence override rescues low-cosine numeric-boundary matches, and a multi-source carve-out routes current-vs-superseded evidence to the model instead of abstaining.
- **Grounded LLM generation** — openai/gpt-4o-mini answers only from retrieved evidence under a prompt contract; output is validated before display.
- **Citation grounding, clarification, and abstention** — answers must cite expected sources; value-dependent goods-vs-services questions trigger clarification; weak evidence triggers abstention, with the model itself as a second line of defence.

## 6. Evaluation Methodology

The corpus is 16 policy documents (15 current + 1 superseded edition), hand-authored with the edge cases planted in the documents themselves (`docs/data_generation.md`). The evaluation set is 22 frozen test cases: 5 normal, 5 boundary, 5 ambiguous, 5 insufficient-evidence, 2 conflicting/outdated. Thresholds were calibrated on a separate set of 90 disjoint questions (66 answerable / 24 deliberately absent) using a pre-declared 10th-percentile rule and frozen before final evaluation. Metrics are deliberately kept separate, and the course-required trivial baselines are reported alongside: **decision/routing correctness** (right action?), **evidence grounding** (expected source retrieved/cited?), and **citation-grounded answer correctness** (human-graded answer text) as the primary metric. Retrieval edge cases are measured per case in `docs/retrieval_edge_cases.md`.

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

The trivial baselines both equal 54.5% on the frozen label distribution (12 answerable / 5 clarify / 5 abstain): always predicting the majority action is exactly what a passage-returning search box does, and it fails all 10 non-answerable cases. The remaining RAG errors are answer-disclosure omissions on two cases, not routing or retrieval errors.

All five insufficient-evidence cases were ultimately handled as ABSTAIN: two were rejected by the deterministic threshold layer (no model call), and three passed that layer but were rejected by the Foundation Model itself because the retrieved evidence was insufficient — a two-layer defence.

## 8. Failure Analysis

The two final-answer failures share one pattern: the correct evidence — including the conflicting and superseded sources — was retrieved and cited, and routing was correct, but the generated answer failed a disclosure requirement.

| Case | Failure |
|---|---|
| TC21 | stated the current Ontario supplier preference but did not disclose that the cited 2019 policy edition is SUPERSEDED |
| TC22 | answered a bare "No." without disclosing the unreconciled gift-policy conflict between the two cited sources or recommending escalation |

So 83.33% is not a retrieval or routing problem — it is incomplete disclosure by the Foundation Model on exactly the supersession/conflict cases that make this corpus realistic. Grounding guarantees the evidence reaches the model, not that the model surfaces everything the evidence contains. A deterministic post-generation disclosure check is the natural mitigation, prepared as future work rather than tuned against these two cases.

## 9. Cost / Latency / Trade-off

Measured final run: 15 Foundation Model calls over 22 cases, total API cost **US$0.004831** (45,246 tokens) — about US$0.00022 per question amortised, since the deterministic layer resolves 7 of 22 questions with no model call. Latency: baseline retrieval ~0.117 ms; RAG retrieval ~2.79 ms; model median ~2,090 ms (P95 ~5,765 ms); end-to-end median ~1.55 s (P95 ~5.55 s). A scale estimate using the measured unit cost (100 questions/workday × 250 days = 25,000/year) implies ~US$5.5/year of inference cost — single-digit dollars, so latency and dependency, not the bill, are the binding trade-off; renting an API is ~20–100× cheaper than a small hosted endpoint at this volume. Against that, the system buys capabilities the baseline structurally lacks: cited answers, clarification (5/5), two-layer abstention (5/5), and correct routing on conflict cases (2/2 at action level). The trade-off is answer completeness ↔ latency ↔ API cost ↔ engineering complexity.

## 10. Limitations

- The corpus is synthetic and small (16 documents); results should not be generalised.
- The evaluation set is small (22 frozen cases); 83.33% is measured on 12 answerable cases, so single cases move the number by 8 points.
- Foundation-model generation can omit required disclosures even when the conflicting or superseded evidence is retrieved and cited (TC21/TC22).
- Model latency (~2.1 s median, P95 ~5.8 s) is far above the baseline's; queries leave the organisation via the API, and with no key the system degrades to PENDING rather than answering.
- Evaluation is automated and corpus-based: no independent human task-time measurement was conducted (human-subject evaluation was outside the required scope), so claims are limited to correctness and system latency, not user productivity.

## 11. Conclusion

Against the research question: yes, with a precise boundary. The grounded RAG assistant improves enterprise policy question answering relative to keyword search — it turns passage lists into cited answers (10/12 fully correct), handles underspecified questions via clarification (5/5), and abstains reliably on insufficient evidence through two independent layers (5/5), with perfect routing (22/22) and grounding (17/17) on the frozen set. The cost is modest in dollars (~US$0.005 per evaluation run) but real in latency (~1.6 s) and dependency. The honest boundary: grounding does not guarantee disclosure — the two residual failures were supersession and conflict omissions. The system is therefore best deployed as **grounded decision support with human verification**, with the keyword baseline retained as the zero-cost fallback. That conclusion is measured, not assumed.
