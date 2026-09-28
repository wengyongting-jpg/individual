# Stage 12 — Cost, Latency & Trade-off Analysis

> **Reproducibility.** Every measured figure in §2–§3 is recomputed from the
> saved per-case results in `evaluation/results/` by
> `python evaluation/compare.py` (see `api_token_cost` and
> `tertiary_diagnostic_system_latency_ms_measured` in
> `evaluation/results/comparison.json`). No number below is hand-calculated;
> re-running `compare.py` regenerates them.

## 1. Build vs Buy

| Layer | Choice | Rationale |
|---|---|---|
| Interface (Streamlit) | **Build** | Simple MVP; no vendor needed |
| Orchestration (pipeline/decision) | **Build** | Deterministic and auditable |
| Foundation Model | **Rent (API)** | Training/hosting a model is outside the project scope and would add substantial infrastructure cost |
| Retrieval (TF-IDF index) | **Build** | The 16-document corpus does not require a managed vector database |
| Dataset | **Build** | Synthetic policy corpus authored for the project |
| Evaluation harness | **Build** | Must match the frozen ground truth and evaluation criteria |
| Logging / results | **Build** | JSON result files are generated for each stage |
| Hosting | **Local (use existing hardware)** | A prototype Streamlit app needs no cloud; all non-model components run on a laptop |

## 2. Final measured results (EXECUTED run)

The final evaluation executed the Foundation Model on the frozen 22-case set
(`evaluation/results/rag_results.json`, `model_execution = EXECUTED`,
model `openai/gpt-4o-mini` via OpenRouter):

| Metric | Final result |
|---|---:|
| Test cases | 22 |
| Foundation Model calls | 15 |
| Total FM API cost | ~US$0.00483 |
| Total tokens (prompt + completion) | 45,246 (42,722 + 2,524) |
| Baseline keyword retrieval median latency | ~0.117 ms |
| RAG retrieval median latency | ~2.79 ms |
| FM model median latency | ~2,090.2 ms |
| FM model P95 latency | ~5,765.4 ms |
| End-to-end median latency (all 22 cases) | ~1.55 s |

End-to-end latency is `retrieval_latency_ms + model_latency_ms` per case
(model latency is 0 for the 7 cases resolved without a model call). The cost
figure is the sum of the per-call `usage.cost` values returned by the
provider and saved in `rag_results.json` — aggregated by
`evaluation/compare.py`, not estimated from a price list.

These latency figures are **compute diagnostics**, not task-completion time,
and are not the project's core evaluation metric (that is citation-grounded
answer correctness). Human task-completion time is measured separately by the
independent user study (`docs/user_study_protocol.md`).

## 3. Why only 15 of 22 cases incur model cost

Model API usage is driven by the answer-eligible fraction, not by every
incoming question:

- **12 answerable cases** routed to the Foundation Model for answer
  generation;
- **5 ambiguous cases** resolved by deterministic clarification — no model
  call;
- **2 insufficient-evidence cases** (TC18, TC20) abstained by the
  deterministic threshold layer — no model call;
- **3 insufficient-evidence cases** (TC16, TC17, TC19) passed the
  deterministic threshold, so the model was called — and the model itself
  returned ABSTAIN because the retrieved evidence was insufficient (a second
  line of defence; see `docs/failure_analysis.md`).

So the deterministic layer absorbs 7 of 22 questions entirely, and the model
layer adds a further safety check on borderline evidence.

## 3a. Cost and business-value estimate

A simple order-of-magnitude business calculation can be expressed as:

```text
savings_per_query =
    manual_lookup_cost_benchmark - AI_cost_per_query

estimated_period_savings =
    number_of_queries × savings_per_query
```

With the measured final run, `AI_cost_per_query` ≈ US$0.00483 / 22 ≈
**US$0.00022 per question** amortised, and the measured cost per Foundation
Model call is 0.004831 / 15 ≈ **US$0.00032** (the deterministic layer handled
7 of 22 questions with no call, an observed call rate of ~68%). The
manual-lookup side should use an externally validated benchmark rather than
an invented value; if the course team's Problem Statement provides one, it
can be inserted directly. This is intentionally a simple multiplication
rather than a detailed financial model.

## 3b. Scale model — lifetime volume, annual cost, break-even

Using the **measured** per-question cost and clearly labelled usage
assumptions (not measured):

```text
Assumed usage  = 100 policy questions per workday x 250 workdays
               = 25,000 questions/year
Observed model-call rate = 15/22 ~= 68%  -> ~17,000 model calls/year
Annual model API cost = 25,000 x US$0.00022 ~= US$5.5 per year
```

So even at a busy-department volume the inference bill stays in the
single-digit dollars per year with the chosen model; the API cost is not the
binding constraint at this scale. Two other scale considerations dominate:

1. **Latency, not dollars, is the real per-query cost.** ~2.1 s median
   (P95 ~5.8 s) per answered question bounds interactive throughput and UX;
   at 25,000 questions/year this is fine for a lookup tool, not for
   synchronous embedding in a high-volume transaction flow.
2. **Build/maintenance vs rental break-even.** Renting the model costs
   ~US$5.5/year here. Operating even a small always-on hosted inference
   endpoint typically runs on the order of US$10–50/month
   (≈ US$120–600/year — verify current provider pricing before quoting), so
   renting is roughly 20–100× cheaper at this volume. Self-hosting only
   approaches break-even at orders of magnitude more traffic, or when
   data-residency rules forbid an external API — in which case the baseline
   still provides a fully local fallback.

The formula is the deliverable: replace the 100/day assumption and
US$0.00022 unit cost with any deployment's figures and the annual cost and
break-even follow mechanically.

## 4. Baseline vs RAG trade-offs

| Dimension | Keyword baseline | RAG + Foundation Model |
|---|---|---|
| Answer correctness | N/A — returns passages, not synthesized answers | **10/12 (83.33%)** on answerable cases |
| Deterministic action correctness | Retrieval only | **22/22 (100%)** |
| Evidence grounding | Top-3 retrieval grounding **1.00** in the baseline diagnostic | **17/17 (100%)** final evidence grounding |
| Retrieval latency | ~0.117 ms median | ~2.79 ms median retrieval |
| End-to-end latency | Not applicable | ~1.55 s median (dominated by external model API latency) |
| API cost (22-case run) | **$0** | ~US$0.00483 total (15 calls) |
| Complexity | Very low | Higher: chunking, retrieval, decision logic, prompt, model, evaluation |
| Explainability | High; direct passage retrieval | Higher than unconstrained generation because responses are tied to retrieved evidence and citations |
| Maintainability | High | Requires prompt, model, retrieval, and policy-version maintenance |
| Hallucination risk | No generated-answer hallucination | Non-zero; mitigated through evidence grounding, deterministic routing, and abstention |
| Ambiguity handling | Cannot clarify | **5/5 correct** on ambiguous cases |
| Insufficient-evidence handling | No explicit abstention mechanism | **5/5 correct** (two-layer defence) |
| Privacy | Fully local | Query/evidence may be sent to an external API provider |

The **83.33% answer-correctness result applies only to the 12 cases expected to
receive an answer**. It should not be interpreted as an 83.33% accuracy rate for
the entire 22-case system.

## 5. Business and technical trade-off

The baseline has clear advantages in cost, latency, privacy, simplicity, and
deterministic behaviour. It is appropriate when the main requirement is
locating relevant policy text.

RAG introduces additional infrastructure and API cost, but adds capabilities
that keyword retrieval structurally lacks: synthesizing a direct answer,
handling underspecified questions through deterministic clarification,
abstaining when evidence is insufficient, and providing citations.

The final evaluation shows that the deterministic control layer can achieve
**22/22 action correctness** and **17/17 evidence grounding** on the frozen
test set. The remaining limitation is Foundation Model answer disclosure:
two of the 12 answerable cases (TC21, TC22) failed to disclose supersession
and conflict information even though the relevant evidence was retrieved and
cited.

This creates a practical trade-off rather than a universally superior
architecture. RAG is useful when users need grounded synthesis and decision
support; the simpler baseline remains valuable as a low-cost, transparent
retrieval fallback.

## 6. When the simpler baseline is still useful

- Very high query volumes where API cost becomes material.
- Environments where policy text cannot be sent to an external API provider.
- Users who only need to locate the relevant document or passage.
- Situations requiring a fully local and deterministic fallback.
- Cases where the Foundation Model service is unavailable.

The final experiment therefore evaluates not only whether RAG can generate
answers, but whether the additional synthesis capability justifies the added
cost, complexity, and external dependency for the intended enterprise
policy-assistance use case.

Human task-completion time remains a separate measurement: the protocol and
analysis tooling are in place (`docs/user_study_protocol.md`,
`evaluation/analyze_user_study.py`), and the study is run by independent
testers rather than inferred from system latency.
