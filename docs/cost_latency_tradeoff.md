# Stage 12 — Cost, Latency & Trade-off Analysis

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

## 2. Measured deterministic performance

| Quantity | Value |
|---|---:|
| Baseline keyword retrieval median latency | ~0.22 ms |
| RAG TF-IDF retrieval median latency | ~4.09 ms |
| Decision-layer latency | negligible (regex + comparisons) |
| RAG offline retrieval + decision | milliseconds-level |
| Baseline API cost | **$0** |

These latency figures are compute diagnostics rather than task-completion time. They are not the project's core evaluation metric. The primary evaluation metric is citation-grounded answer correctness on the fixed 22-case evaluation set.

The final RAG run successfully executed the Foundation Model for cases routed to answer generation. External API latency and token usage are recorded in the model results where available, but latency is reported separately from task-completion time because the latter requires an independent human study.

## 3. Foundation Model cost and latency

The Foundation Model was executed during the final evaluation. The system records model usage information, including prompt and completion token counts when returned by the provider, as well as per-call model latency.

The final evaluation contains:

- **12 answerable cases** expected to receive a generated answer;
- **5 clarification cases**, which do not require Foundation Model answer generation;
- **5 insufficient-evidence cases**, which are deterministically abstained before generation.

Therefore, model API usage is driven by the answer-eligible fraction rather than by every incoming question.

The exact dollar cost should be calculated from the recorded token usage together with the model provider's applicable pricing at the time of execution. A dollar amount is not reported here unless it can be reproduced directly from the saved usage data and the documented pricing source.

For an API call:

```text
cost_per_query =
    (input_tokens / 1,000,000 × input_price)
    +
    (output_tokens / 1,000,000 × output_price)
```

End-to-end system latency can be understood as:

```text
retrieval latency
+ decision latency
+ Foundation Model latency
```

However, this is still a system-performance measure rather than a measure of how long a human takes to complete a procurement lookup.

## 3a. Cost and business-value estimate

A simple order-of-magnitude business calculation can be expressed as:

```text
savings_per_query =
    manual_lookup_cost_benchmark - AI_cost_per_query

estimated_period_savings =
    number_of_queries × savings_per_query
```

The calculation should use an externally validated manual-lookup cost benchmark rather than an invented value. If the course team's Problem Statement provides such a benchmark, it can be inserted directly into the calculation together with the measured API cost.

This is intentionally a simple multiplication rather than a detailed financial model.

## 4. Baseline vs RAG trade-offs

| Dimension | Keyword baseline | RAG + Foundation Model |
|---|---|---|
| Answer correctness | N/A — returns passages, not synthesized answers | **9/12 (75%)** on answerable cases |
| Deterministic action correctness | Retrieval only | **22/22 (100%)** |
| Evidence grounding | Top-3 retrieval grounding **1.00** in the baseline diagnostic | **17/17 (100%)** final evidence grounding |
| Retrieval latency | ~0.22 ms | ~4.09 ms median retrieval |
| End-to-end latency | Not applicable | Includes external Foundation Model latency; diagnostic rather than core metric |
| Complexity | Very low | Higher: chunking, retrieval, decision logic, prompt, model, evaluation |
| Explainability | High; direct passage retrieval | Higher than unconstrained generation because responses are tied to retrieved evidence and citations |
| Maintainability | High | Requires prompt, model, retrieval, and policy-version maintenance |
| Hallucination risk | No generated-answer hallucination | Non-zero; mitigated through evidence grounding, deterministic routing, and abstention |
| Ambiguity handling | Cannot clarify | **5/5 correct** on ambiguous cases |
| Insufficient-evidence handling | No explicit abstention mechanism | **5/5 correct** |
| Cost | $0 API cost | Per-token Foundation Model API cost |
| Privacy | Fully local | Query/evidence may be sent to an external API provider |

The **75% answer-correctness result applies only to the 12 cases expected to receive an answer**. It should not be interpreted as a 75% accuracy rate for the entire 22-case system.

## 5. Business and technical trade-off

The baseline has clear advantages in cost, latency, privacy, simplicity, and deterministic behaviour. It is appropriate when the main requirement is locating relevant policy text.

RAG introduces additional infrastructure and API cost, but adds capabilities that keyword retrieval structurally lacks: synthesizing a direct answer, handling underspecified questions through deterministic clarification, abstaining when evidence is insufficient, and providing citations.

The final evaluation shows that the deterministic control layer can achieve **22/22 action correctness** and **17/17 evidence grounding** on the frozen test set. The remaining limitation is Foundation Model answer completeness: three of the 12 answerable cases omitted one or more material requirements even though relevant evidence was available.

This creates a practical trade-off rather than a universally superior architecture. RAG is useful when users need grounded synthesis and decision support; the simpler baseline remains valuable as a low-cost, transparent retrieval fallback.

## 6. When the simpler baseline is still useful

- Very high query volumes where API cost becomes material.
- Environments where policy text cannot be sent to an external API provider.
- Users who only need to locate the relevant document or passage.
- Situations requiring a fully local and deterministic fallback.
- Cases where the Foundation Model service is unavailable.

The final experiment therefore evaluates not only whether RAG can generate answers, but whether the additional synthesis capability justifies the added cost, complexity, and external dependency for the intended enterprise policy-assistance use case.

Human task-completion time remains a separate future measurement because it requires an independent tester study rather than inference from system latency.