# Grounded Enterprise Policy & Procedure Assistant

PE6201 End-of-Course Project — a small, reproducible experiment comparing a traditional keyword-search baseline against a RAG + Foundation Model
system for enterprise procurement-policy questions.

---

## 1. Project overview
A decision-support assistant that answers procurement-policy questions by
retrieving relevant internal policy passages and (for answerable, specific
questions) generating an **evidence-grounded** answer with citations. It is not an autonomous procurement agent.

## 2. Problem
Procurement staff lose time searching scattered policy documents, and risk
acting on a misremembered or out-of-context rule.

## 3. Target user
Enterprise procurement / finance staff who must apply the correct policy rule
(thresholds, approvals, quote counts) to a specific purchase.

## 4. Why AI
Retrieval alone locates documents but does not synthesize an answer, ask for a
missing detail, or say "the policy doesn't cover this." A Foundation Model,
constrained to retrieved evidence, can do all three — the experiment measures
whether that added value justifies the added cost/latency/complexity.

## 5. System architecture
```
Question
  → Retrieval (TF-IDF cosine over paragraph chunks)      rag/retriever.py
  → Signals (top_score, margin)                          rag/signals.py
  → Deterministic decision layer                         rag/decision.py
        CLARIFICATION_REQUIRED  → clarifying question (no model)
        ABSTAIN                 → fixed message (no model)
        ANSWERED_ELIGIBLE       → Foundation Model
  → Prompt contract + evidence                           rag/prompt.py
  → Model client (env-configured)                        rag/model_client.py
  → Output validation → grounded answer + citations      rag/rag_answer.py
```

## 6. Retrieval approach
TF-IDF vectors + cosine similarity (scikit-learn) over paragraph chunks of the
16 documents (15 current policies + 1 deliberately superseded edition, see §7a).
Lightweight, local, deterministic — no PyTorch, no model download.
The `Retriever` interface allows a neural backend to be added later.
`score` = cosine similarity in `[0,1]` (a similarity, **not** a probability).

## 7. Decision / abstention mechanism
Deterministic, clarification-first (`docs/abstention_methodology.md`):
- **CLARIFICATION** if the question asks about a value-dependent decision at a
  dollar amount but does not say goods vs services.
- **ABSTAIN** if `top_score < TOP_SCORE_MIN` or `margin < MARGIN_MIN`.
- Thresholds were calibrated on a **separate** synthetic set (10th-percentile
  rule) and **frozen**: `TOP_SCORE_MIN = 0.238864`, `MARGIN_MIN = 0.030034`
  (recalibrated after the corpus grew to 16 documents — see §15a).

## 7a. Superseded and conflicting policy content
The corpus (`15 policy files/`) deliberately contains two forms of realistic
policy drift, so the system is tested against actual outdated/contradictory
*documents*, not just questions that pretend one exists:
- `16_provincial_trade_policy_2019_superseded.txt` — an old edition of the
  Provincial Trade Policy, explicitly labelled SUPERSEDED, stating a different
  rule than the current `12_provincial_trade_policy.txt`.
- `14_procurement_governance_roles.txt` contains a gift-acceptance clause that
  directly contradicts the absolute gift ban in
  `13_conflict_of_interest_policy.txt`, and says so in its own text.
Prompt rule 9 (`rag/prompt.py`) instructs the model to flag a SUPERSEDED
passage or an unreconciled conflict explicitly, citing both sources, rather
than silently picking one. `ground_truth.json` cases TC21/TC22 test this.

## 8. Foundation Model configuration
OpenAI-compatible (default provider: OpenRouter). The model is called **only**
for `ANSWERED_ELIGIBLE` cases and **only** when an API key is present. With no
key, the system returns **PENDING EXECUTION** — never a fabricated answer.

## 9. Environment variables (see `.env.example`)
```
OPENROUTER_API_KEY=        # your key; leave blank to run offline
MODEL_NAME=openai/gpt-4o-mini
# OPENROUTER_BASE_URL=...  # optional
# LLM_TEMPERATURE=0        # optional (0 for reproducibility)
```

## 10. Installation
```bash
pip install -r requirements.txt
```

## 11. Run the offline components (no key needed)
```bash
python baseline/keyword_search.py                 # baseline demo
python evaluation/run_baseline.py                 # Stage 1 baseline results
python evaluation/run_rag_retrieval.py            # Stage 2 retrieval results
python evaluation/calibration/build_calibration_set.py
python evaluation/calibration/calibrate_thresholds.py   # reproduces frozen thresholds
python evaluation/run_stage3.py                   # Stage 3 decision results
python evaluation/run_rag.py                      # full pipeline (answers PENDING w/o key)
python evaluation/evaluate.py --system baseline
python evaluation/evaluate.py --system rag
python evaluation/compare.py                      # baseline vs RAG
python evaluation/analyze_failures.py             # failure analysis
```

## 12. Run the Streamlit UI
```bash
pip install -r requirements.txt      # includes streamlit
streamlit run app/streamlit_app.py
```

## 13. Reproduce the full evaluation (API key required for the model step)
```bash
pip install -r requirements.txt
cp .env.example .env
# edit .env and set OPENROUTER_API_KEY=... (see §9)
python evaluation/run_rag.py                # executes the Foundation Model on the 22 cases
python evaluation/evaluate.py --system rag  # scores the run against ground truth
python evaluation/compare.py                # regenerates comparison.json incl. cost/latency
```
The committed results in `evaluation/results/` are from an **EXECUTED** run
(`openai/gpt-4o-mini` via OpenRouter). Without a key, `run_rag.py` still runs
the full deterministic pipeline but marks answers `PENDING_EXECUTION` — never
a fabricated answer. Never commit `.env` (it is git-ignored).

## 14. Evaluation methodology
The evaluation uses the frozen 22-case `ground_truth.json` and the same criteria
for both systems (`evaluation/evaluate.py`):
- **Primary metric — citation-grounded answer correctness** on the fixed
  22-case set: a case counts as correct only if the system actually answered,
  cited an expected source, AND a human grader confirmed the answer text
  matches `expected_answer`. Median response time is **not** used as the core
  metric — the team wrote the corpus itself and so cannot be the ones timing
  themselves searching it, and a speed-only metric would also reward a fast,
  wrong answer.
- **Secondary metric — independent-tester task-completion time**: human task
  time measured by testers who did **not** write the 16 policy documents.
  Protocol: `docs/user_study_protocol.md`; analysis:
  `evaluation/analyze_user_study.py`.
- **Tertiary/diagnostic — system latency**: compute time only, reported for
  engineering context; never presented as task time or as a core metric.
- Calibration data (threshold selection) is **separate** from the 22-case final
  set (see `evaluation/calibration/`); thresholds are never selected from
  these 22 cases (see `docs/abstention_methodology.md`).

## 15. Frozen assets (do not modify without a disclosed, dated amendment)
`ground_truth.json`, the files in `15 policy files/`, `baseline/`, the Stage 1
results, Stage 2 retrieval results/methodology, the Stage 3 calibration set,
`rag/thresholds.py`, and the Stage 3 methodology.

## 15a. One disclosed exception (2026-09-19)
Per reviewer feedback, two of these frozen assets were intentionally amended
once: the corpus gained one file (`16_provincial_trade_policy_2019_superseded.txt`)
plus a short cross-reference/contradiction paragraph in two existing files, and
`ground_truth.json` gained TC21/TC22. Because the corpus changed, the
calibration set and `rag/thresholds.py` were mechanically regenerated by
re-running the existing, unmodified pipeline scripts (§11) — no scoring rule
or threshold-selection rule was changed. TC01–TC20 and their expected values
are untouched. Full rationale: `ground_truth.json`'s `_meta.amendment`.

## 16. Final results (EXECUTED — Foundation Model ran on all answer-eligible cases)
- **Primary metric — citation-grounded answer correctness: 9/12 (75%)** of
  answerable cases (human-graded; 3 incomplete answers: TC01, TC08, TC10 —
  see `docs/failure_analysis.md`).
- Deterministic action correctness: **22/22 (100%)**.
- Evidence grounding: **17/17 (100%)**.
- Ambiguous → clarification **5/5**; insufficient evidence → abstain **5/5**
  (two-layer defence: 2 deterministic + 3 rejected by the model itself);
  conflicting/outdated policy **2/2**.
- Cost/latency (recomputed by `evaluation/compare.py`): 15 Foundation Model
  calls, total API cost **~US$0.00497**, retrieval median **~4.09 ms**,
  end-to-end median **~2.03 s**.
- Earlier experiment (Stage 3, pre-Foundation-Model, superseded): baseline
  retrieval grounding top-1 0.647 / top-3 1.000; RAG TF-IDF retrieval
  grounding 0.706; deterministic action accuracy 14/22. Retained as
  development history in `docs/failure_analysis.md` §1.

## 17. Remaining pending item
- **Secondary metric** — independent-tester task-completion time and the
  ≥50%-reduction target: protocol, recording template, and analysis script
  are in place (`docs/user_study_protocol.md`,
  `evaluation/results/user_study_results.csv`,
  `evaluation/analyze_user_study.py`); participant data collection is the one
  remaining step. No figures are reported until real measurements exist.

## 18. Known limitations
- TF-IDF cannot reason about numeric thresholds → boundary retrieval misses.
- Calibrated abstention thresholds cannot perfectly separate answerable from
  insufficient (score overlap) → some insufficient cases don't abstain
  deterministically (the Foundation Model layer catches them instead).
- Clarification can slightly over-trigger on single-track boundary questions.
- The margin signal, designed to catch diffuse/competing evidence, can also
  abstain on a genuinely answerable case when a current and a superseded
  document score closely (development-stage finding, TC21 — in the final run
  TC21 was answered correctly; see `docs/abstention_methodology.md` §5).
- Correct retrieval does not guarantee complete synthesis: 3 of 12 final
  answers omitted a material requirement (TC01, TC08, TC10).
- Corpus is synthetic and small (16 docs); results should not be generalized.

## 19. Security considerations
See `docs/security_governance.md`: prompt-injection defence (evidence is data),
no secrets in source, malformed-output rejection, deterministic abstention, and
a human-in-the-loop posture. Verify every answer against current policy.

---

### Repository layout
```
15 policy files/            synthetic corpus (16 .txt — 15 current + 1 superseded)
baseline/                   Stage 1 keyword baseline (frozen)
rag/                        retriever, signals, decision, thresholds (regenerated
                            on the one disclosed corpus change, §15a),
                            prompt, model_client, rag_answer, tests
evaluation/                 runners, evaluate, compare, failure analysis
  calibration/              separate calibration set + calibrator
  results/                  per-stage JSON results
app/                        streamlit_app.py (MVP UI)
docs/                       methodology, failure analysis, cost, security, demo, report
ground_truth.json           22-case evaluation set (20 original + TC21/TC22)
requirements.txt  .env.example  .gitignore  README.md
```
