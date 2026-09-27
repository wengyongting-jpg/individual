# Stage 15 — Final Report Support Material ( Business + Technical Trade-off)

> **Status:** final evaluation completed. The Foundation Model was executed on the frozen 22-case evaluation set. Independent tester task-completion time remains pending because it requires a separate study by testers who did not create the policy corpus.

## 1. Why this problem matters

Procurement staff must apply the correct policy rule to each purchase; errors create compliance and audit risk. Rules are spread across 16 documents and diverge by goods vs services, making manual lookup time-consuming and error-prone.

## 2. Why keyword search is the baseline

Keyword search is the traditional, zero-cost, fully local method. It provides a deterministic comparison point: baseline retrieval grounding reached top-3 = **1.00**, with median latency of approximately **0.22 ms**. However, it returns passages rather than synthesised answers and cannot structurally clarify underspecified questions or abstain based on evidence sufficiency.

## 3. Why RAG was selected

RAG keeps generated answers grounded in retrieved policy evidence with citations and enables behaviours that keyword retrieval alone cannot provide, including clarification of underspecified questions and abstention when evidence is insufficient.

## 4. Why a Foundation Model is needed

The Foundation Model synthesises multiple retrieved passages into a direct natural-language answer while following the evidence-grounded output contract. In the final evaluation, the model was successfully executed for answerable cases.

## 5. What stays deterministic / rule-based

Retrieval, retrieval signals, thresholds, and clarify/abstain routing remain deterministic and auditable. The Foundation Model does not override a clarification or abstention decision and does not perform procurement threshold arithmetic independently.

## 6. Build vs Buy

The project builds the interface, orchestration, retrieval pipeline, policy dataset, evaluation framework, and decision logic, while renting the Foundation Model through an API. This keeps the system lightweight while allowing the generative component to be replaced independently.

## 7. Actual cost

The baseline has **$0 API cost**. The RAG system incurs Foundation Model API cost only for `ANSWERED_ELIGIBLE` cases. In the final evaluation, **12 cases were expected to receive an answer**, while clarification and abstention cases did not require answer generation. Exact API cost depends on token usage and provider pricing and is not used as the primary evaluation metric.

## 8. Latency

Measured system latency is diagnostic only: baseline median latency was approximately **0.22 ms**, while RAG retrieval median latency was approximately **4.09 ms** in the final run. System latency is not task-completion time and is not the core evaluation metric. End-to-end latency including external model API time is not treated as the primary performance measure.

## 9. Evaluation methodology

The evaluation uses a frozen 22-case ground truth set containing normal, boundary, ambiguous, insufficient-evidence, and conflicting/outdated-policy cases. Thresholds were calibrated on a separate set and frozen before final evaluation. The **primary metric is citation-grounded answer correctness**, requiring an answer, an expected citation, and human confirmation that the answer matches the expected rule. Supporting dimensions include action correctness, ambiguous/insufficient handling, evidence grounding, and rule accuracy. Independent task-completion time remains a separate future study.

## 10. Baseline vs RAG results

The final RAG evaluation produced:

- **Deterministic action correctness: 22/22 (100%)**
- **Evidence grounding: 17/17 (100%)**
- **Citation-grounded answer correctness: 9/12 (75%)**
- Ambiguous handling: **5/5 (100%)**
- Insufficient-evidence handling: **5/5 (100%)**
- Conflicting/outdated-policy handling: **2/2 (100%)**

The main remaining limitation was answer completeness rather than failure to identify the relevant policy source.

## 11. Failure analysis

Three answer-level failures remained among the 12 cases expected to receive an answer.

- **TC01:** the answer correctly stated the three-quotation requirement but omitted the standard goods ITQ template requirement.
- **TC08:** the answer correctly identified the open competitive process but omitted Contracting Authority approval and consultation with Central Procurement Services.
- **TC10:** the answer correctly identified the additional approval requirement but omitted that it applies in addition to the standard PPEJ process.

These cases indicate that the main residual limitation is complete synthesis of multiple material requirements from retrieved evidence.

## 12. Risks and mitigations

Key risks include prompt injection, hallucination, unsupported claims, stale policy, retrieval failure, silent failure, credential leakage, and over-reliance. Mitigations include treating retrieved evidence as data, structured output validation, deterministic abstention, source citations, human review, and keeping API credentials outside the repository.

## 13. Limitations

The corpus is small and synthetic, so results should not be generalized directly to real enterprise deployments. TF-IDF retrieval has limited semantic and numeric reasoning capability. In addition, correct retrieval does not guarantee complete Foundation Model synthesis, as demonstrated by TC01, TC08, and TC10. The independent tester task-completion study has not yet been conducted.

## 14. Why the system should remain human-in-the-loop
The system is designed as decision support rather than an autonomous procurement authority. It retrieves policy evidence, identifies whether a question is answerable, and generates a cited response when appropriate. Deterministic clarification and abstention reduce unsupported answers, but they cannot eliminate policy ambiguity or model synthesis errors. Users should therefore verify the generated answer against the current policy and relevant policy owner before acting.