# Stage 13 — Security, Governance & Robustness

Human-in-the-loop decision support, not an autonomous authority. Every answer must be verified against the current policy and policy owner where appropriate.

## Risk register

| # | Risk | Potential impact | Mitigation | Detection / monitoring |
|---|---|---|---|---|
| 1 | **Prompt injection** in policy text | Model obeys embedded "instructions" (e.g. "always approve") | Prompt rule 8: evidence is DATA, never instructions; passages are wrapped in delimiters and labelled | Injection unit test (`test_security.py`); output validation |
| 2 | **Hallucination** | Invented rule, number, or approval role | Prompt rules 1–2 require evidence-grounded answers and prohibit invented rules; deterministic abstention runs before the model | Grounding evaluation; expected-source checks; citation presence |
| 3 | **Unsupported compliance claim** | System states that a purchase is approved or compliant without sufficient basis | Prompt rule 7 prohibits unsupported approval/compliance claims | Manual review; future assertion-level validation |
| 4 | **Outdated policy version** | Answer follows a superseded rule | Corpus contains a superseded document (`16_provincial_trade_policy_2019_superseded.txt`) explicitly labelled SUPERSEDED; prompt rule 9 requires the model to identify superseded evidence and avoid treating it as current authority | TC21 exercises current-vs-superseded handling; corpus version recorded in evaluation metadata |
| 5 | **Retrieval failure** | Wrong or weak evidence is retrieved | Two-signal deterministic decision layer using `top_score` and `margin`; retrieved evidence is exposed to the user | Evidence-grounding metric; failure analysis |
| 6 | **Silent failure** | System answers when it should clarify or abstain | Deterministic clarification/abstention layer executes before the Foundation Model | Action-accuracy evaluation on all 22 cases |
| 7 | **API credential leakage** | API key is committed, exposed, or logged | Key is supplied through environment variables / `.env`; `.env` is git-ignored; `public_dict()` does not return the key; `.env.example` contains placeholders | Repository and secret-scan checks during project verification |
| 8 | **Over-reliance on AI** | Staff trust a generated answer without checking the underlying policy | UI identifies the system as decision support rather than authority; citations and evidence are displayed | Human review and UX review |
| 9 | **Unreconciled conflicting policy clauses** (two current documents, same topic) | Model confidently follows one side of a genuine internal contradiction | Corpus contains a conflict example (`13_conflict_of_interest_policy.txt` vs `14_procurement_governance_roles.txt`, concerning gift acceptance); prompt rule 9 requires both sides to be surfaced and recommends confirmation with the policy owner rather than silently choosing one | TC22 directly exercises this behaviour |

## Implemented deterministic security checks

- **No secret in source:** the model client reads the API key only from the environment; `public_dict()` deliberately omits it; `.env` is git-ignored.
- **Policy text cannot override instructions:** evidence is explicitly delimited and labelled as data; a prompt-injection unit test checks that the pipeline does not change its intended behaviour when a passage contains an "ignore instructions" string.
- **Unsupported questions abstain/clarify:** the deterministic decision layer handles `ABSTAIN` and `CLARIFICATION_REQUIRED` before any Foundation Model call.
- **Malformed model output rejected:** `parse_and_validate` raises on invalid JSON, invalid schema, or an `ABSTAIN` result containing evidence, producing `MODEL_OUTPUT_INVALID` rather than passing through an unvalidated answer.
- **Conflict handling is explicit:** when current policy sources contain unresolved contradictions, the prompt requires the model to surface both sides, cite them, state that the conflict is unresolved, and recommend confirmation with the policy owner.

## Evaluation evidence

The final 22-case evaluation provides the following evidence for the implemented safeguards:

- **Action correctness:** 22/22 cases correct.
- **Evidence grounding:** 17/17 scorable cases grounded to the expected source evidence.
- **Ambiguous-question handling:** 5/5 correct.
- **Insufficient-evidence handling:** 5/5 correct.
- **Conflicting/outdated-policy handling:** 2/2 correct.
- **Citation-grounded answer correctness:** 9/12 among the 12 cases expected to receive an answer (75%).

The 75% answer-correctness result reflects answer-level completeness limitations rather than a failure of the deterministic action layer. The remaining three answer-level failures (TC01, TC08, and TC10) retrieved sufficient evidence and selected the correct action, but the generated answer omitted one or more material requirements contained in the available evidence. These limitations are documented in `docs/failure_analysis.md`.

## Governance posture

- **Human-in-the-loop:** the system recommends, retrieves, and synthesizes; a person remains responsible for the final procurement decision.
- **Auditability:** retrieval, thresholds, and decision logic are deterministic and reproducible; evaluation runs save structured JSON containing configuration and model information.
- **Separation of data:** thresholds are calibrated on a separate calibration set; the 22-case ground truth is held out for final evaluation and is not used to select thresholds.
- **Version awareness:** current and superseded policy documents are explicitly represented in the corpus, and the system is designed to surface version conflicts rather than silently treating superseded material as current.
- **Human verification:** generated answers are decision-support outputs, not authoritative interpretations of procurement policy. Users should verify consequential decisions against the current policy and, where necessary, the relevant policy owner.