# Stage 3 — Deterministic Abstention & Clarification Methodology

This document explains how the RAG system decides, **without any Foundation Model**, whether to answer a procurement-policy question, ask for clarification, or abstain. It is written so the design can be reproduced and defended in the final report.

> **Scope note.** Stage 3 adds only the **decision layer** on top of the Stage-2 TF-IDF retriever. It does **not** generate answers (no LLM/API), does not use Streamlit, and does not re-tune retrieval. The 22 locked ground-truth cases (20 original + TC21/TC22, added 2026-09-19 per reviewer feedback -- see `ground_truth.json`'s `_meta.amendment`) are used **only** for final measurement, never to choose any parameter.

---

## 1. The three actions

Every question is routed to exactly one action:

| Action | Meaning |
|---|---|
| `ANSWERED` (internally `ANSWERED_ELIGIBLE`) | Evidence is strong and focused enough, and the question is specific enough, that a later stage *may* generate a grounded answer. Stage 3 itself does not write the answer. |
| `CLARIFICATION_REQUIRED` | Relevant evidence exists, but the question is underspecified (does not say goods vs services, where the rules genuinely diverge). |
| `ABSTAIN` | The retrieved evidence is too weak or too diffuse to support any answer. Returns a fixed message. |

Fixed abstention message (matches the ground-truth wording):

> Insufficient evidence was found in the available procurement policies to answer this question reliably. Please verify with the relevant policy owner.

---

## 2. Decision logic (exact, ordered)

Clarification is checked **before** abstention, because an underspecified question can retrieve strong evidence yet still must not be answered.

```text
retrieve top-k passages (k = 5)           # evaluation/run_rag.py
compute signals: top_score, margin        # rag/signals.py

STEP 1 — CLARIFICATION (question property, score-independent)
    if is_underspecified(question):
        -> CLARIFICATION_REQUIRED

STEP 2 — ABSTENTION (evidence property, frozen thresholds)
    if top_score < TOP_SCORE_MIN:  -> ABSTAIN
    if margin    < MARGIN_MIN:     -> ABSTAIN

STEP 3 — otherwise
    -> ANSWERED_ELIGIBLE
```

### Retrieval signals (`rag/signals.py`)

* **`top_score`** — cosine similarity of the best-ranked chunk. Absolute strength of the single best piece of evidence.
* **`margin`** — `top_score` minus the best score from a **different source document**. Measures how *concentrated* the evidence is in one policy. If all retrieved passages share one source, `margin = top_score` (maximally concentrated).

Two signals are used because Stage 2 showed a single cosine cutoff cannot separate answerable from unanswerable questions (their score ranges overlap).

> **Important:** cosine similarity is a lexical/semantic similarity in `[0, 1]`. It is **not** a probability or a calibrated confidence, and is never described as one.

### Clarification rule (`is_underspecified`, `rag/decision.py`)

The corpus's genuine fault line is **goods vs services** (approval role, quote count, and method differ between the two tracks at the same dollar value). The rule is:

```text
is_underspecified(q) =
       mentions_amount(q)          # a "$" or procurement-sized number
   AND mentions_decision(q)        # approve / quote / threshold / method / ...
   AND NOT names_track(q)          # neither a goods term nor a services term
```

Decision terms are matched as **regex fragments** (e.g. `approv\w*`, `sign(s|ed|ing)?[ -]off`, `quot\w*`) so common inflections are handled generically. The vocabulary is general procurement language, **fixed in advance**, and contains **no test-case IDs**.

---

## 3. How the thresholds were calibrated (no test-set tuning)

The crucial requirement: thresholds must **not** be chosen by searching for the value that maximises the 22-case score. They are chosen on a **separate calibration set** using a **pre-declared rule**.

### 3.1 Separate calibration set (`evaluation/calibration/`)

`build_calibration_set.py` deterministically generates `calibration_questions.json` — **disjoint from ground truth** (the 22 ground-truth questions are never read):

* **`in_corpus` (should be answerable)** — 66 questions built mechanically from the policy paragraphs themselves (headings / first sentences fed into fixed templates). Grounded in real chunks, so strong retrieval is expected. Defines the "genuine hit" distribution.
* **`out_of_corpus` (should abstain)** — 24 questions on procurement-adjacent themes known to be **absent** from the corpus (warranty, payment terms, travel reimbursement, etc.), from a fixed hand-authored theme list. Written to be plausible-but-absent; **not** copies of the ground-truth ABSTAIN questions.

The set carries a SHA-256 content hash for provenance.

### 3.2 Pre-declared selection rule

Declared **before** any numbers were seen:

```text
TOP_SCORE_MIN = 10th percentile of the in_corpus top_score distribution
MARGIN_MIN    = 10th percentile of the in_corpus margin  distribution
```

Rationale: *accept evidence at least as strong as the weakest 90% of genuine in-corpus hits.* The **rule** is fixed in advance; whatever values it yields are frozen without adjustment. `calibrate_thresholds.py` applies the rule mechanically and writes the frozen values into `rag/thresholds.py` with full provenance (calibration hash, counts, rule, date).

### 3.3 Frozen values

```text
TOP_SCORE_MIN = 0.238864
MARGIN_MIN    = 0.030034
```

These are compiled into `rag/thresholds.py` and are **not** hand-edited. Re-running the two calibration scripts reproduces them.

---

## 4. Why this avoids test-set tuning

1. **Disjoint data** — thresholds come only from the calibration set; the 22 GT cases are held out and used once, for measurement.
2. **Pre-declared rule** — "10th percentile of the in_corpus distribution" was fixed before seeing numbers, so a cutoff cannot be reverse-engineered from GT outcomes.
3. **Reproducible** — calibration generation and threshold selection are fully deterministic (fixed templates, fixed theme list, numpy-free percentile).
4. **No case-specific logic** — clarification uses general vocabulary; abstention uses two frozen numbers. There is no `if test_case_id == …` anywhere.
5. **Honest about limits** — the calibration distributions overlap, so the rule is expected to misclassify some cases. Those are reported as results/failures, not tuned away.

---

## 5. Known limitations (reported, not fixed by tuning)

* The `in_corpus` and `out_of_corpus` score distributions **overlap**, so a threshold rule cannot perfectly separate answerable from unanswerable questions. Some out-of-corpus questions score above `TOP_SCORE_MIN`.
* Boundary questions with literal dollar amounts (e.g. "$74,999", "$121,200") retrieve weakly under TF-IDF because those exact strings are not in the corpus, so they can be abstained on.
* The clarification rule can fire on a specific single-track question that omits the goods/services word but is not truly ambiguous.
* **The margin signal is dual-purpose and can, in principle, misfire on a genuinely answerable superseded-vs-current case (development-stage finding, TC21).** Margin measures whether evidence is concentrated in one document, but a genuine cross-document conflict or supersession can also produce a small margin. During Stage 3 development this was flagged as a risk for TC21: closely scoring current and superseded documents could reduce the margin enough to trigger `ABSTAIN` before the Foundation Model's conflict-handling rule could be applied. In the **final** evaluation TC21 was in fact routed to `ANSWERED` (margin 0.4295, well above `MARGIN_MIN = 0.030034`) and answered correctly — but the structural limitation of using one margin signal for both purposes remains, and is reported here rather than tuned away.

These are genuine trade-offs of a deterministic, non-LLM decision layer and are carried forward to the final failure analysis in `docs/failure_analysis.md`.