# Stage 15 — Final Report Support Material (≤1200-word Business + Technical Trade-off)

> **Status:** structured material / draft outline with the numbers available now.
> Sections that depend on the Foundation Model or a human study are marked
> **PENDING EXECUTION** and must be filled in only after real execution — do not
> write conclusions about RAG answer quality or task-time savings until measured.

Use this as the skeleton for the final ≤1200-word analysis.

## 1. Why this problem matters
Procurement staff must apply the correct policy rule to each purchase; errors
create compliance and audit risk. Rules are spread across 16 documents and
diverge by goods vs services — costly to search manually.

## 2. Why keyword search is the baseline
It is the traditional, zero-cost, fully local method staff already use. It sets a
fair, deterministic floor: retrieval grounding top-3 = **1.00**, median latency
**~0.22 ms**, $0 cost — but it returns passages, not answers, and cannot clarify
or abstain.

## 3. Why RAG was selected
RAG keeps answers **grounded** in retrieved evidence with citations, and enables
two behaviours the baseline structurally lacks: **clarification** of
underspecified questions and **abstention** on unsupported ones.

## 4. Why a Foundation Model is needed
To synthesize a direct, natural-language answer from multiple passages and to
follow the evidence-only / abstain-if-unsupported contract. (Execution PENDING.)

## 5. What stays deterministic / rule-based
Retrieval, the two-signal thresholds, and the clarify/abstain routing are all
deterministic and auditable. The model never overrides an abstain/clarify
decision, and never performs threshold arithmetic.

## 6. Build vs Buy
Build interface/orchestration/retrieval/dataset/evaluation; rent the model API.
(See `docs/cost_latency_tradeoff.md`.)

## 7. Actual cost
Baseline: **$0**. RAG API cost: **PENDING EXECUTION** (methodology documented;
only ANSWERED_ELIGIBLE cases — 10/22 in the current run — incur a model call).
Order-of-magnitude ROI estimate (simple multiplication against the team's
manual-lookup cost benchmark): **PENDING** — see `docs/cost_latency_tradeoff.md`
§3a.

## 8. Latency
Measured (diagnostic only, not the core metric): baseline ~0.22 ms, RAG
retrieval ~0.50 ms. RAG end-to-end (with model): **PENDING EXECUTION**. System
latency is **not** task-completion time and is **not** the core evaluation
metric — see §9.

## 9. Evaluation methodology
Frozen 22-case ground truth (20 original + TC21/TC22, added per reviewer
feedback so the corpus itself, not just a test question, contains a superseded
policy version and a genuine cross-document contradiction); same criteria for
both systems; thresholds calibrated on a **separate** set (10th-percentile
rule) and frozen. **Primary metric: citation-grounded answer correctness**
(answered + correctly cited + human-confirmed correct text) on the fixed set.
Task-completion time is secondary and must be measured by independent
testers, not the document authors. System latency is a tertiary diagnostic
figure only. Four supporting dimensions: action correctness,
ambiguous/insufficient handling, grounding, rule accuracy.

## 10. Baseline vs RAG results
- Retrieval grounding: baseline top-3 **1.00** vs RAG **0.71** (TF-IDF).
- RAG deterministic action accuracy: **14/22** (normal/ambiguous perfect;
  boundary/insufficient/conflicting-or-outdated weaker).
- **Primary metric** (citation-grounded answer correctness) & secondary metric
  (independent-tester task time): **PENDING EXECUTION**.

## 11. Failure analysis
8 deterministic failures: 3 retrieval (boundary dollar amounts), 5 decision (1
over-eager clarification, 3 insufficient-not-abstained, 1 superseded-vs-current
margin collision on TC21). See `docs/failure_analysis.md`. Not fixed by tuning
frozen assets.

## 12. Risks and mitigations
Prompt injection, hallucination, unsupported claims, stale policy, retrieval
failure, silent failure, credential leakage, over-reliance — each with mitigation
and detection in `docs/security_governance.md`.

## 13. Limitations
Small synthetic corpus; lexical retriever lacks numeric reasoning; calibrated
thresholds cannot perfectly separate overlapping distributions (including
sometimes abstaining on a superseded-vs-current case, TC21); model results
and the primary/secondary metrics are pending.

## 14. Why the system should remain human-in-the-loop
It is decision support: it locates evidence, cites sources, and abstains when
unsure — but a person must verify against the current policy and owner before
acting. Grounding + abstention reduce, but do not eliminate, error risk.
