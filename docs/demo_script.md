# Stage 14 — Final Demo Script

One clear story:

> **Does a grounded RAG system with a Foundation Model provide useful decision support for procurement-policy questions while remaining evidence-grounded and auditable?**

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
| Citation-grounded answer correctness | **9/12 (75%)** |
| Ambiguous handling | **5/5 (100%)** |
| Insufficient-evidence handling | **5/5 (100%)** |
| Conflicting/outdated-policy handling | **2/2 (100%)** |

Clarify that **9/12 = 75% is the primary answer-correctness result among the 12 cases expected to receive an answer**. It is not the overall accuracy of all 22 cases.

---

## Demo 9 — Show the limitation honestly

Explain that three answerable cases were judged incomplete:

- **TC01:** omitted the standard goods ITQ template requirement.
- **TC08:** omitted Contracting Authority approval and consultation with Central Procurement Services.
- **TC10:** omitted that additional higher-level approval applies in addition to the standard PPEJ process.

The important finding is:

> **The system can retrieve relevant evidence and make the correct routing decision, but the Foundation Model may still omit a material requirement when synthesizing multiple pieces of evidence.**

This is the main remaining improvement area.

---

## Demo 10 — Cost and latency

Show the measured diagnostic latency:

- Baseline retrieval: approximately **0.22 ms median**
- RAG retrieval: approximately **4.09 ms median**

Explain that these are compute/retrieval measurements, **not human task-completion times**.

The baseline has **$0 API cost**.

The RAG system incurs Foundation Model API cost only for answer-generation cases. Exact API cost should be calculated from the recorded token usage and the applicable provider pricing rather than estimated without evidence.

An independent human task-completion study has not yet been conducted.

---

## Closing

The final message should be balanced:

> The project does not show that RAG is automatically better than keyword search. The baseline is cheaper, faster, fully local, and highly transparent for document retrieval.
>
> RAG adds capabilities that keyword search does not provide: grounded answer synthesis, clarification, deterministic abstention, and cited responses.
>
> On the frozen 22-case evaluation, the system achieved **22/22 deterministic action correctness** and **17/17 evidence grounding**. Among the 12 cases expected to receive an answer, **9/12 were judged fully correct**.
>
> The remaining limitation is answer completeness: relevant evidence can be retrieved correctly while the Foundation Model still omits a material requirement.
>
> The prototype should therefore be understood as **grounded decision support with human verification**, rather than an autonomous procurement authority.