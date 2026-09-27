# Stage 12 — Cost, Latency & Trade-off Analysis

## 1. Build vs Buy

| Layer | Choice | Rationale |
|---|---|---|
| Interface (Streamlit) | **Build** | Simple MVP; no vendor needed |
| Orchestration (pipeline/decision) | **Build** | Deterministic, must be auditable |
| Foundation Model | **Rent (API)** | Training/hosting a model is out of scope & cost-prohibitive |
| Retrieval (TF-IDF index) | **Build** | 16-doc corpus needs no managed vector DB |
| Dataset (16 synthetic policies, incl. 1 superseded edition) | **Build** | Synthetic corpus authored for the project |
| Evaluation harness | **Build** | Must match the locked ground truth exactly |
| Logging / results | **Build** | JSON result files per stage |

## 2. Measured (deterministic, offline) — EXECUTED

| Quantity | Value |
|---|---|
| Baseline keyword retrieval median latency (diagnostic, not task time) | ~0.22 ms |
| RAG TF-IDF retrieval median latency (diagnostic, not task time) | ~0.50 ms |
| Decision-layer latency | negligible (regex + 2 comparisons) |
| RAG end-to-end **offline** latency (retrieval + decision, no model) | sub-millisecond |
| Baseline API cost | **$0** (standard library only) |

Latency figures come from the saved result files (`baseline_results.json`,
`rag_retrieval_results.json`) and are compute latency only — a diagnostic,
secondary/tertiary figure, never the project's core metric (see
`evaluation/compare.py` and `docs/abstention_methodology.md`). The core
evaluation metric is citation-grounded answer correctness on the fixed
22-case set (`evaluation/evaluate.py`), currently PENDING EXECUTION.

## 3. Foundation Model cost & latency — PENDING EXECUTION

No API key has been used, so **no** token counts, API latency, or dollar cost
have been measured. These are **PENDING EXECUTION** and must not be estimated as
if measured.

**Measurement methodology (for when a key is available):**

- Token usage: read `usage.prompt_tokens` / `usage.completion_tokens` from each
  model response (the client already captures `usage`).
- Cost: `input_tokens/1e6 * input_price + output_tokens/1e6 * output_price`,
  using the selected model's published per-million-token prices **recorded with
  the date and source** at run time. (No price is hard-coded here to avoid
  fabricating a figure that may be stale.)
- API latency: `model_latency_ms` already recorded per call by the client.
- End-to-end RAG latency = retrieval + decision + model latency.

Only ANSWERED_ELIGIBLE cases incur a model call (10 of 22 in the current run), so
cost scales with the answer-eligible fraction, not all questions — abstain and
clarify are free.

## 3a. Cost estimate — order of magnitude (simple multiplication)

**PENDING — needs one figure from the team's Problem Statement.** Course
knowledge point 5 asks for an order-of-magnitude ROI estimate now, via simple
multiplication, using the team's own benchmark for what a manual policy lookup
currently costs (referenced in feedback as "$10 per lookup" but not present in
this codebase, so not filled in here to avoid inventing a number for the
report). Once that figure is confirmed, the calculation is:

```
cost_per_ai_query   = (input_tokens/1e6 * input_price + output_tokens/1e6 * output_price)
                       -- measured once a key is available (see section 3)
savings_per_query    = manual_lookup_cost_benchmark  -  cost_per_ai_query
queries_per_[period]  x  savings_per_query  =  estimated_[period]_savings
```

This is deliberately simple multiplication, not a model — consistent with the
"measure, don't model" rule used throughout this project (see also
`docs/final_report_material.md` §7).

## 4. Baseline vs RAG trade-offs

| Dimension | Keyword baseline | RAG + Foundation Model |
|---|---|---|
| Accuracy (answer) | N/A — returns passages, not answers | PENDING EXECUTION |
| Retrieval grounding (top-3) | 1.00 (measured) | 0.71 (measured, TF-IDF) |
| Latency (diagnostic only) | ~0.22 ms | ~0.50 ms retrieval + model (pending) |
| Complexity | Very low | Higher (chunking, vectors, prompt, model, validators) |
| Explainability | High (exact keyword hits) | Medium (cosine + model reasoning) |
| Maintainability | High | Medium (prompt + model drift + threshold recalibration) |
| Hallucination risk | None (no generation) | Non-zero — mitigated by prompt + abstention |
| Ambiguity handling | None (cannot clarify) | Yes (deterministic clarification) |
| Insufficient-evidence handling | None (always returns passages) | Yes (deterministic abstention) |
| Cost | $0 | Per-token API cost (pending) |
| Privacy | Fully local | Question + evidence sent to API provider |

## 5. When the simpler baseline is still useful

- Very high query volume where per-call API cost dominates.
- Environments where sending policy text to an external API is disallowed
  (privacy/data-residency).
- Users who only need to **locate** the right document, not a synthesized answer.
- As a transparent, deterministic fallback when the model/API is unavailable.

The experiment's purpose is to test whether RAG's added answer synthesis,
clarification, and abstention justify its cost/latency/complexity — a question
that stays **partly PENDING EXECUTION** until the model is run and a human
task-time study is performed.
