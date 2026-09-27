# Stage 14 — Final Demo Script

One clear story: *does RAG + a Foundation Model add measurable value over a
keyword-search baseline for procurement-policy questions?*

> If no API key is set, Demo 3's answer step shows **PENDING EXECUTION** — say so
> honestly; do not fake a model answer.

### Demo 1 — The problem (30s)
Show the 16 policy files (including one deliberately superseded edition). Point out that goods and services have different rules
at the same dollar value, spread across multiple documents. A person must find
the right file and the right tier.

### Demo 2 — Baseline (keyword search)
```bash
python baseline/keyword_search.py "How many quotations for a $100,000 goods purchase?"
```
Show ranked passages + source + matched keywords + latency. Note: it returns
**passages**, not an answer, and it cannot tell you when the corpus has no answer.

### Demo 3 — RAG (same question)
Run the Streamlit UI (`streamlit run app/streamlit_app.py`) and ask the same
question. Show: action = ANSWERED (or PENDING EXECUTION with no key), the
retrieved evidence, and the **source citation**.

### Demo 4 — Ambiguous question
Ask: *"Who approves a $50,000 purchase?"* → **NEEDS CLARIFICATION** (goods vs
services). The system asks rather than guessing.

### Demo 5 — Insufficient evidence
Ask: *"What insurance must a supplier carry to bid?"* → **ABSTAINED** with the
fixed message. The system refuses to invent a rule.

### Demo 6 — Evaluation
Show `evaluation/results/comparison.json`:
- retrieval grounding: baseline vs RAG (measured, diagnostic);
- RAG deterministic action accuracy 14/22 (measured);
- **primary metric** (citation-grounded answer correctness) and
  **secondary metric** (independent-tester task-completion time): **PENDING EXECUTION**.

### Demo 7 — Superseded and conflicting policy (new, TC21/TC22)
Ask: *"What is the Ontario supplier preference under the provincial trade
policy?"* → the corpus contains both the current rule ($121,200 cap) and a
2019 edition explicitly labelled SUPERSEDED with a different rule. Point out
that TF-IDF alone can rank the superseded document first (TC21 currently
ABSTAINs at the deterministic layer for exactly this reason — see
`docs/failure_analysis.md`). Then ask: *"Can an employee accept a gift from a
supplier?"* → the corpus contains a genuine unreconciled contradiction between
the conflict-of-interest ban and the governance-roles nominal-gift exception
(TC22). The Foundation Model, once executed, is instructed (prompt rule 9) to
surface both rather than silently pick one — say plainly that this is
**PENDING EXECUTION**, not yet observed.

**Closing:** RAG structurally adds clarify/abstain and cited answers; the
answer-quality and time savings remain to be measured. Do not claim RAG is
better merely because it is more advanced — report the measured trade-offs.
