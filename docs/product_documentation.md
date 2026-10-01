# Product Documentation

## 1. Product Overview

The Grounded Enterprise Policy & Procedure Assistant is a decision-support system for procurement and finance staff. It helps users retrieve relevant policy evidence and determine whether the available evidence is sufficient to answer a procurement-related question.

The system does not autonomously approve purchases, reject transactions, place orders, or execute procurement actions.

## 2. Persona

**Primary users:** Procurement and finance staff.

**User need:** Obtain a reliable, traceable answer to policy and procedure questions without manually searching across multiple documents.

## 3. Input

The system accepts a natural-language procurement or policy question.

Example:

> How many quotations are required for a $100,000 goods purchase?

## 4. Output

The system produces one of three high-level outcomes:

- **ANSWER** — sufficient evidence is available and a grounded answer is generated.
- **CLARIFY** — important information is missing and the user should provide additional information.
- **ABSTAIN** — the available evidence is insufficient to support a reliable answer.

For answerable cases, the system provides a citation to the retrieved policy evidence.

## 5. High-Level Product Architecture

```text
User Question
      ↓
TF-IDF Retrieval
+ Numerical / Domain Signals
      ↓
Top-5 Evidence
      ↓
Deterministic Decision Layer
      ↓
 ┌──────────┬───────────┬───────────┐
 │  ANSWER  │  CLARIFY  │  ABSTAIN  │
 └────┬─────┴───────────┴───────────┘
      ↓
Foundation Model
(openai/gpt-4o-mini via OpenRouter)
      ↓
Validation + Citation Checking
      ↓
Grounded Response
```

## 6. Target Metrics

The project targeted:

- Reliable deterministic routing between ANSWER, CLARIFY, and ABSTAIN.
- Strong evidence grounding.
- Citation-grounded answer correctness for answerable questions.
- Appropriate clarification of ambiguous questions.
- Appropriate abstention when evidence is insufficient.
- Low retrieval latency and low model API cost.

A secondary objective was to keep the system transparent and reproducible through deterministic retrieval and routing.

## 7. Metrics Reached

The final frozen evaluation achieved:

| Metric | Result |
|---|---:|
| Deterministic action correctness | 22/22 (100%) |
| Evidence grounding | 17/17 (100%) |
| Citation-grounded answer correctness | 10/12 (83.33%) |
| Ambiguous-case clarification | 5/5 |
| Insufficient-evidence abstention | 5/5 |
| Final Foundation Model calls | 15 |
| Total API cost | ~US$0.004831 |
| Median end-to-end latency | ~1.55 s |

## 8. Human Oversight and Limitations

The system is designed as decision support rather than autonomous procurement automation.

Human verification remains necessary for consequential decisions, particularly when policies conflict, when a policy is superseded, or when the available evidence does not fully support a conclusion.

TC21 and TC22 demonstrate that the current system can retrieve problematic evidence but may fail to explicitly disclose every material supersession or conflict relationship in the final answer.