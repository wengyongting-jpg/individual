# Stage 14 — Final Demo Script

One clear story:

> Does a grounded RAG system with a Foundation Model provide useful decision support for procurement-policy questions while remaining evidence-grounded and auditable?

The committed results are from an **EXECUTED** Foundation Model run
(`openai/gpt-4o-mini` via OpenRouter). Reproduce the evaluation:
```bash
pip install -r requirements.txt
cp .env.example .env        # set OPENROUTER_API_KEY=...
python evaluation/run_rag.py
python evaluation/evaluate.py --system rag
python evaluation/compare.py
```
Without an API key the pipeline still runs deterministically but answers are
marked `PENDING_EXECUTION` — never fabricated.

The demo should show both the system's capabilities and its measured limitations. Do not claim that RAG is universally better than keyword search.

---

## Demo 1 — The problem (30s)

Show the 16 policy files, including one deliberately superseded edition.

Explain that procurement rules vary by procurement type, monetary threshold, approval role, and exception. Relevant information can also be distributed across multiple documents.

The practical problem is not simply finding a keyword. The user needs to determine whether the evidence is sufficient, identify the applicable rule, and receive a grounded answer with a source citation.

---

## Demo 2 — Baseline: keyword search

Run:

```bash
python baseline/keyword_search.py "How many quotations for a $100,000 goods purchase?"
```

Show:

- ranked passages;
- source document;
- matched keywords;
- retrieval latency.

Explain that the baseline is fully local and has **$0 API cost**. Its measured top-3 retrieval grounding is **1.00** in the baseline diagnostic.

However, keyword search returns passages rather than a synthesized answer. It also has no explicit clarification or abstention mechanism.

---

## Demo 3 — RAG + Foundation Model

Run:

```bash
streamlit run app/streamlit_app.py
```

Ask the same question:

> "How many quotations for a $100,000 goods purchase?"

Show:

- retrieved evidence;
- deterministic action;
- generated answer;
- source citation.

Explain that the deterministic layer first decides whether the question is answerable. Only answer-eligible cases are passed to the Foundation Model.

The Foundation Model is therefore used for **answer synthesis**, not for overriding the deterministic routing decision.

---

## Demo 4 — Ambiguous question

Ask:

> "Who approves a $50,000 purchase?"

Show:

> **NEEDS CLARIFICATION**

Explain that the applicable approval rule depends on the procurement track, so the system asks for the missing context instead of guessing.

The final evaluation achieved:

**Ambiguous handling: 5/5 (100%)**

---

## Demo 5 — Insufficient evidence

Ask:

> "What insurance must a supplier carry to bid?"

Show:

> **ABSTAINED**

Explain that the corpus does not provide sufficient evidence for this question, so the system does not invent a policy requirement.

The final evaluation achieved:

**Insufficient-evidence handling: 5/5 (100%)**

---

## Demo 6 — Evidence and citation grounding

Show a normal answered case and open the retrieved source passage.

Point out that the answer is generated from retrieved policy evidence rather than from unsupported model knowledge.

The final evaluation achieved:

**Evidence grounding: 17/17 (100%)**

Then explain that grounding and answer completeness are different measurements: a response can use the correct evidence but still omit one material requirement.

---

## Demo 7 — Conflicting and superseded policy

First ask:

> "What is the Ontario supplier preference under the provincial trade policy?"

Explain that the corpus contains both a current policy and an explicitly superseded 2019 edition.

The final evaluation correctly handled the conflicting/outdated-policy category at the deterministic level:

**2/2 (100%)**

The system is designed to avoid silently treating a superseded policy as current. Where conflicting evidence remains unresolved, the prompt requires the model to surface the relevant sources and recommend policy-owner confirmation.

Then ask:

> "Can an employee accept a gift from a supplier?"

Explain that the corpus contains a genuine cross-document conflict. The system is designed to surface both relevant pieces of evidence rather than silently choosing one.

---

## Demo 8 — Final evaluation

Show the final evaluation results.

### Final results

| Metric | Result |
|---|---:|
| Deterministic action correctness | **22/22 (100%)** |
| Evidence grounding | **17/17 (100%)** |
| Citation-grounded answer correctness | **10/12 (83.33%)** |
| Ambiguous handling | **5/5 (100%)** |
| Insufficient-evidence handling | **5/5 (100%)** |
| Conflicting/outdated-policy handling | **2/2 (100%)** |

Clarify that **10/12 = 83.33% is the primary answer-correctness result among the 12 cases expected to receive an answer**. It is not the overall accuracy of all 22 cases.

---

## Demo 9 — Show the limitation honestly

Explain that two answerable cases were judged incorrect on disclosure:

- **TC21:** the answer stated the current Ontario supplier preference but did not disclose that the cited 2019 Provincial Trade Policy edition is SUPERSEDED.
- **TC22:** the answer was a bare "No." — it did not disclose the unreconciled gift-policy conflict between the two cited sources, nor recommend verification with the policy owner.

The important finding is:

> **The system can retrieve all relevant — including conflicting — evidence and route correctly, but the Foundation Model may still fail to disclose supersession or conflicts in its answer.**

This is the main remaining improvement area.

---

## Demo 10 — Cost and latency

Show the measured diagnostic latency:

- Baseline keyword retrieval: approximately **0.117 ms median**
- RAG TF-IDF retrieval: approximately **2.79 ms median**
- Foundation Model median latency (answered cases): approximately **2.09 s**
- End-to-end median latency (all 22 cases): approximately **1.55 s**

Explain that these are compute/retrieval measurements, **not human task-completion times**.

The baseline has **$0 API cost**.

The RAG system incurs Foundation Model API cost only for answer-generation cases. The final run: 15 FM calls across 22 cases, total API cost approximately **US$0.00483**, recomputed by `evaluation/compare.py` from the saved per-call usage data — not estimated.

An independent human task-completion study is an **optional extension and was not required for the current evaluation**; the protocol (`docs/user_study_protocol.md`), recording template (`evaluation/results/user_study_results.csv`), and analysis script (`evaluation/analyze_user_study.py`) are in place.

---

## Closing

The final message should be balanced:

> The project does not show that RAG is automatically better than keyword search. The baseline is cheaper, faster, fully local, and highly transparent for document retrieval.
>
> RAG adds capabilities that keyword search does not provide: grounded answer synthesis, clarification, deterministic abstention, and cited responses.
>
> On the frozen 22-case evaluation, the system achieved **22/22 deterministic action correctness** and **17/17 evidence grounding**. Among the 12 cases expected to receive an answer, **10/12 were judged fully correct**.
>
> The remaining limitation is answer disclosure: relevant and even conflicting evidence can be retrieved correctly while the Foundation Model still fails to disclose supersession or conflict information.
>
> The prototype should therefore be understood as **grounded decision support with human verification**, rather than an autonomous procurement authority.