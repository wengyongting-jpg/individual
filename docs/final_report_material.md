# Final Report — Grounded Procurement-Policy Assistant (Business + Technical Trade-off)

## 1. Problem

Procurement staff must apply the correct policy rule to every purchase:
approval thresholds, quotation counts, and methods diverge by goods versus
services and by dollar value, and the rules are spread across 16 documents —
including one deliberately superseded edition and one genuine cross-document
contradiction. Manual lookup is slow and error-prone; acting on a
misremembered or out-of-context rule creates compliance and audit risk. The
practical need is not keyword matching but an answer: which rule applies,
where it says so, and whether the evidence is even sufficient.

## 2. Baseline

The baseline is traditional keyword search (`baseline/keyword_search.py`):
zero API cost, fully local, deterministic. On the frozen 22-case ground truth
it reaches top-3 retrieval grounding of **1.00** with ~0.117 ms median
latency. But it structurally cannot synthesize an answer, ask for a missing
detail, or say "the policy doesn't cover this" — it returns near-miss
passages for all 5 insufficient-evidence questions.

## 3. RAG architecture

```
Question
  → Chunking (paragraph chunks of the 16 policy files)
  → Retrieval (TF-IDF cosine, top-5)
  → Evidence signals (top_score, margin)
  → Deterministic decision layer (frozen thresholds, no model)
        CLARIFICATION_REQUIRED → clarifying question (no model call)
        ABSTAIN                → fixed message      (no model call)
        ANSWERED_ELIGIBLE      → Foundation Model
  → Prompt contract (evidence treated as data; citations required)
  → Foundation Model (openai/gpt-4o-mini via OpenRouter)
  → Output validation
  → Answer / Clarification / Abstain
```

Retrieval, thresholds, and routing stay deterministic and auditable; the
Foundation Model only synthesizes answers for answer-eligible questions and
cannot override an abstention. Thresholds (`TOP_SCORE_MIN = 0.238864`,
`MARGIN_MIN = 0.030034`) were calibrated on a separate synthetic set by a
pre-declared 10th-percentile rule and frozen before final evaluation — never
tuned on the 22 test cases.

## 4. Evaluation

The frozen set contains 22 cases: 5 normal, 5 boundary, 5 ambiguous, 5
insufficient-evidence, 2 conflicting/outdated. The **primary metric** is
citation-grounded answer correctness: correct only if the system answered,
cited an expected source, and a human grader confirmed the answer text
against the expected rule.

Final executed results:

| Metric | Result |
|---|---:|
| Deterministic action correctness | **22/22 (100%)** |
| Evidence grounding (expected source retrieved) | **17/17 (100%)** |
| Citation-grounded answer correctness (primary) | **9/12 (75%)** |
| Ambiguous → clarification | 5/5 |
| Insufficient evidence → abstain | 5/5 |
| Conflicting/outdated policy | 2/2 |

The 75% is over the 12 answerable cases: 9 correct, 3 incomplete — TC01
(omitted the standard goods ITQ template), TC08 (omitted Contracting
Authority approval in consultation with Central Procurement Services), TC10
(omitted that extra approval applies *in addition to* the standard PPEJ
process). In all three, retrieval was correct and the routing decision was
correct; the model's synthesis was incomplete.

A notable strength: all five insufficient-evidence cases were ultimately
handled as ABSTAIN. Two were abstained by the deterministic threshold layer;
three were initially eligible for generation under that threshold but were
subsequently rejected by the Foundation Model itself because the retrieved
evidence was insufficient — a genuine two-layer defence.

## 5. User study

Machine metrics alone cannot show that the assistant makes procurement work
faster; that requires independent testers. The study protocol
(`docs/user_study_protocol.md`) is fully prepared: 2–3 participants who did
not author the corpus, each answering the same questions under both methods
in counterbalanced order (P1 manual→RAG, P2 RAG→manual, P3 manual→RAG),
recording per-question completion time and correctness
(`evaluation/results/user_study_results.csv`), analysed by
`evaluation/analyze_user_study.py` into median manual time, median RAG time,
median time reduction, and accuracy.

**Status: data collection is the one remaining step — no participant data
exists yet, so no figures are reported here rather than invented.** Whatever
is measured will be reported as-is, even if the median time reduction falls
short of the 50% target.

## 6. Cost and latency (measured, reproducible)

Recomputed by `evaluation/compare.py` from the saved per-case results:

| Metric | Final result |
|---|---:|
| Test cases | 22 |
| Foundation Model calls | 15 |
| Total FM API cost | ~US$0.00497 |
| Total tokens | 34,744 |
| Baseline retrieval median latency | ~0.117 ms |
| RAG retrieval median latency | ~4.09 ms |
| FM model median latency | ~2.34 s |
| FM model P95 latency | ~3.67 s |
| End-to-end median latency (all cases) | ~2.03 s |

The deterministic layer absorbs 7 of 22 questions with no model call at all,
so the amortised API cost is roughly US$0.00023 per question. The dominant
cost is not dollars but latency: ~2 s end-to-end, driven by the external API.

## 7. Limitations

- **Retrieval ranking**: TF-IDF is lexical; development-stage failures on
  numeric boundary questions (TC06–08) show exact dollar strings retrieve
  weakly. The final run grounded all 17 scorable cases, but the weakness is
  structural.
- **Incomplete synthesis**: 3 of 12 answers omitted a material requirement
  despite correct evidence and routing — the main residual risk.
- **Model latency**: ~2.3 s median per answered question versus ~0.1 ms for
  the baseline.
- **API dependency**: queries and policy excerpts leave the organisation;
  the system degrades to PENDING (never a fabricated answer) with no key.
- **User-study sample**: the independent study is small (2–3 participants)
  and not yet executed; time-saving claims await that data.
- The corpus is synthetic and small (16 documents); results should not be
  generalised to real deployments.

## 8. Business and technical trade-off

Is the added cost worth it? The baseline is cheaper (~$0), ~17,000× faster,
fully private, and perfectly transparent — and remains the right tool when
the need is simply to locate a document. The RAG system pays ~US$0.00023 per
question, ~2 s of latency, an external dependency, and substantially more
engineering complexity. What that buys is something the baseline structurally
cannot do: a direct, cited answer (9/12 fully correct), clarification instead
of guessing on underspecified questions (5/5), and refusal rather than
confabulation on unanswerable ones (5/5, via two independent layers).

For an enterprise policy assistant, an incorrect invented rule is far more
expensive than a slow honest one. The measured profile — perfect routing and
grounding, with residual risk concentrated in answer completeness — supports
deploying the system as **grounded decision support with human verification**,
with the baseline kept as the low-cost fallback where synthesis is
unnecessary or the API is unavailable.
