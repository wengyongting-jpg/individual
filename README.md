# Grounded Enterprise Policy & Procedure Assistant

PE6201 End-of-Course Project — a small, reproducible experiment comparing a traditional keyword-search baseline against a RAG + Foundation Model system for enterprise procurement-policy questions.

---

## At a glance

- **Problem.** Procurement and finance staff must determine the rule that applies to a *specific* purchase — approval threshold, required quotations, goods-vs-services route, exceptions — across 16 scattered documents that include an out-of-date edition and a genuine contradiction. Slow lookups delay decisions; misremembered rules create compliance risk; conflicting editions make decisions inconsistent. Existing search returns passages but cannot say which rule applies, ask for a missing detail, or refuse when no rule exists.
- **Approach.** TF-IDF retrieval over paragraph chunks with deterministic numeric/domain signals → a frozen-threshold **deterministic decision layer** (clarify / abstain / answer) → `openai/gpt-4o-mini` synthesizes an answer **only** from retrieved, cited evidence; output is validated.
- **Evaluation.** 22 frozen test cases (5 normal, 5 boundary, 5 ambiguous, 5 insufficient-evidence, 2 conflicting/superseded); thresholds calibrated on a separate 90-question set and frozen; answer texts human-graded.
- **Key finding.** Routing and grounding are perfect on the frozen set (22/22 actions, 17/17 grounding) versus 54.5% decision accuracy for both baseline methods — but correct retrieval does not guarantee complete disclosure: 2 of 12 answers (TC21/TC22) failed to surface supersession/conflict information even though the relevant evidence was retrieved and cited.
- **Limitations.** Synthetic 16-document corpus (single authorial voice — ceiling risk); 83.33% rests on only 12 answerable cases; ~2.1 s model median latency; external API dependency.

### Evaluation summary — final executed run

All figures are recomputed from `evaluation/results/` by `python evaluation/compare.py` — none is hand-entered.

| Measure | Majority-class baseline | Keyword-search baseline | Final RAG system |
|---|---:|---:|---:|
| Decision correctness (all 22 cases) | **54.5%** (always "ANSWERED") | **54.5%** (returns passages; cannot clarify/abstain) | **100% (22/22)** |
| Non-answerable cases handled (10 cases) | 0/10 | 0/10 | **10/10** (5/5 clarify + 5/5 abstain) |
| Evidence grounding (17 scorable cases) | — | top-1 64.7% / top-3 100% | **100% (17/17)** |
| Citation-grounded answer correctness (12 answerable cases) | — | N/A (no answer text) | **83.33% (10/12)** |
| Retrieval latency (median) | — | 0.117 ms | 2.79 ms |
| Model latency (median / P95) | — | — | **2.09 s / 5.77 s** |
| End-to-end latency (median / P95) | — | — | **1.55 s / 5.55 s** |
| API cost (full 22-case run) | $0 | $0 | **US$0.004831** (15 model calls) |

The 54.5% majority-class figure is computed directly from the frozen label distribution (12 ANSWERED / 5 CLARIFY / 5 ABSTAIN). The majority-class baseline always predicts the most common action, while the keyword-search baseline returns relevant passages without a deterministic mechanism for clarification or abstention. The majority-class baseline therefore misclassifies the five ambiguous and five insufficient-evidence cases, while the keyword-search baseline does not provide those behaviours. P95 uses the nearest-rank method.

---

## 1. Project overview

A **policy-grounded decision-support assistant** for procurement/finance staff: given a question about a specific purchase, it retrieves the applicable internal policy passages, assesses whether the evidence is sufficient, and either answers with citations, asks a clarifying question, or abstains. It is not an autonomous procurement agent — scope is defined in §4a.

## 2. Problem

Purchasing rules are distributed across 16 policy documents. They are numeric and conditional — thresholds differ by dollar value and by goods vs services — and the document set contains one superseded edition plus one genuine cross-document contradiction.

For staff operationalizing purchasing, the recurring questions are concrete:

- What approval is required for a purchase of a given value — and does the route differ for services?
- How many quotations are required at this value?
- Can a purchase be split to stay below a threshold, and what is the exception route?

Three consequences follow from answering these from memory or manual lookup:

- **slow retrieval → delayed decisions** — locating and cross-reading passages holds up purchases;
- **misremembered rules → compliance risk** — applying a wrong threshold or skipping quotations breaches procedure and fails audit;
- **outdated / conflicting documents → inconsistent decisions** — two staff members can open different editions and give different answers to the same question.

Existing keyword/document search addresses only the first link: it returns passage lists. It cannot determine which conditional rule applies to a specific amount, notice that goods vs services was never specified, flag a superseded edition, say "the policy does not cover this", or reconcile a contradiction. The problem is therefore not *find documents* but *turn the applicable rules into a correct, sourced decision* — reliably, including when the evidence is ambiguous or absent.

## 3. Target user and tasks

The users are enterprise **procurement and finance staff** preparing or approving purchases — not policy authors or the general public. Their tasks are approval-threshold lookup, quotation-requirement checks, goods-vs-services routing, and exception/split-purchase questions. The same user and task frame is used throughout the evaluation: the 22 frozen test cases represent these tasks, and success means the staff member receives the applicable rule together with the source it comes from.

## 4. Why AI is the intervention

The gap in §2 is language understanding plus bounded synthesis: matching a question to the right passages despite wording differences, combining evidence that spans documents, recognising a missing parameter, and expressing the result in plain language with citations. A Foundation Model constrained to retrieved evidence supplies these capabilities; the experiment tests whether evidence grounding, deterministic gating, and abstention can keep such a model suitable for policy work, and at what added cost and latency (§16). The AI is the *intervention* tested against the problem in §2 — the problem does not presuppose it. Implementation detail (retrieval method, decision layer, model) begins at §5.

## 4a. Project scope

**In scope:** policy-grounded decision support — evidence retrieval, evidence sufficiency assessment, clarification of underspecified questions, abstention when policy coverage is absent, and cited grounded answers.

**Out of scope:** the assistant does **not** approve, reject, place, or execute any purchase, and it does not make the final decision. The human purchaser/approver remains the decision-maker; the system supplies the applicable rule, its source, and an explicit signal when evidence is insufficient or conflicting.

## 5. System architecture

```text
Question
  → Retrieval: TF-IDF cosine over paragraph chunks (top-5)
      + deterministic numeric-match (+0.20) / domain-match (+0.15)
        ranking bonuses                              rag/retriever.py
  → Signals (top_score, margin, multi-source flag)   rag/signals.py
  → Deterministic decision layer (frozen thresholds) rag/decision.py
        CLARIFICATION_REQUIRED → clarifying question (no model)
        ABSTAIN                 → fixed message (no model)
        ANSWERED_ELIGIBLE       → Foundation Model
  → Prompt contract + evidence (evidence is data)     rag/prompt.py
  → Model client (env-configured)                     rag/model_client.py
  → Output validation → grounded answer + citations   rag/rag_answer.py
```

Signals and thresholds operate on **raw cosine**; the bonuses affect ranking only. Around the frozen thresholds, two deterministic refinements apply: a structured-evidence override (rank-1 chunk matches both query amount and goods/services domain) and a multi-source carve-out (two strong sources, e.g. current + superseded, are sent to the model instead of triggering a diffuse-evidence abstention). Exact order: `docs/abstention_methodology.md` §2.

## 6. Retrieval approach

TF-IDF vectors + cosine similarity (scikit-learn) over paragraph chunks of the 16 documents (15 current policies + 1 deliberately superseded edition, see §7a). Lightweight, local, deterministic — no PyTorch, no model download.

The `Retriever` interface allows a neural backend to be added later.

`score` = raw cosine similarity in `[0,1]` (a similarity, **not** a probability); a separate `ranking_score` adds the deterministic bonuses.

Measured lexical weaknesses (vocabulary mismatch, two-document and distractor edges) are documented per case in `docs/retrieval_edge_cases.md`.

## 7. Decision / abstention mechanism

Deterministic, clarification-first (`docs/abstention_methodology.md`):

- **CLARIFICATION** if the question asks about a value-dependent decision at a dollar amount but does not say goods vs services.
- **ABSTAIN** if `top_score < TOP_SCORE_MIN`, or if `margin < MARGIN_MIN` without a second strong source.
- **ANSWERED_ELIGIBLE** otherwise — including the structured-evidence override (amount + domain both match) and the multi-source carve-out (two strong sources must be compared by the model).
- Thresholds were calibrated on a **separate** set of 90 questions (66 answerable / 24 deliberately absent) with a pre-declared 10th-percentile rule and **frozen**: `TOP_SCORE_MIN = 0.238864`, `MARGIN_MIN = 0.030034`.

Why these values, and the recall/safety cost of moving them: `docs/abstention_methodology.md` §6 (recalibrated once after the corpus grew to 16 documents — see §15a).

## 7a. Superseded and conflicting policy content

The corpus — **16 policy documents: 15 current policy documents + 1 superseded policy edition**, stored in `15 policy files/` — deliberately contains two forms of realistic policy drift, so the system is tested against actual outdated/contradictory *documents*, not just questions that pretend one exists:

- `16_provincial_trade_policy_2019_superseded.txt` — an old edition of the Provincial Trade Policy, explicitly labelled SUPERSEDED, stating a different rule than the current `12_provincial_trade_policy.txt`.
- `14_procurement_governance_roles.txt` contains a gift-acceptance clause that directly contradicts the absolute gift ban in `13_conflict_of_interest_policy.txt`, and says so in its own text.

Prompt rule 9 (`rag/prompt.py`) instructs the model to flag a SUPERSEDED passage or an unreconciled conflict explicitly, citing both sources, rather than silently picking one. `ground_truth.json` cases TC21/TC22 test this.

## 8. Foundation Model configuration

OpenAI-compatible (default provider: OpenRouter). The model is called **only** for `ANSWERED_ELIGIBLE` cases and **only** when an API key is present. If you re-run without a key, the system marks answers `PENDING_EXECUTION` — never a fabricated answer.

**The committed results in this repository are from an already-executed run** (`openai/gpt-4o-mini` via OpenRouter, 15 calls, 22 cases); see §16.

## 9. Environment variables (see `.env.example`)

```text
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
python evaluation/calibration/calibrate_thresholds.py  # reproduces frozen thresholds
python evaluation/run_stage3.py                   # Stage 3 decision results
python evaluation/run_rag.py                      # full pipeline (answers PENDING w/o key)
python evaluation/evaluate.py --system baseline
python evaluation/evaluate.py --system rag
python evaluation/compare.py                      # baseline vs RAG + cost/latency
python evaluation/analyze_failures.py             # failure analysis
python evaluation/analyze_edge_cases.py           # retrieval edge-case scores
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
python evaluation/run_rag.py               # executes the Foundation Model on the 22 cases
python evaluation/evaluate.py --system rag # scores the run against ground truth
python evaluation/compare.py               # regenerates comparison.json incl. cost/latency
```

The committed results in `evaluation/results/` are from this executed run (see §8). Without a key, `run_rag.py` still runs the full deterministic pipeline but marks answers `PENDING_EXECUTION` — never a fabricated answer.

Never commit `.env` (it is git-ignored).

## 14. Evaluation methodology

The evaluation uses the frozen 22-case `ground_truth.json` and the same criteria for both systems (`evaluation/evaluate.py`):

- **Primary metric — citation-grounded answer correctness** on the fixed 22-case set: a case counts as correct only if the system actually answered, cited an expected source, **and** a human grader confirmed the answer text matches `expected_answer`. Median response time is **not** used as the core metric — the team wrote the corpus itself and so cannot be the ones timing themselves searching it, and a speed-only metric would also reward a fast, wrong answer.
- **Tertiary/diagnostic — system latency:** compute time only (median **and** P95), reported for engineering context; never presented as task time or as a core metric.
- **Secondary target — task-time reduction: TARGET ONLY, NOT MEASURED.** A ≥50% reduction in median human task-completion time vs manual keyword search was pre-registered as the secondary evaluation target (`docs/user_study_protocol.md`). It requires independent participants because the team authored the corpus and cannot time itself. **Participant data collection is pending — no participant data have been collected** — so no task-time figure is reported anywhere, and the ≥50% target must not be read as an achieved result. All reported results come from the executed automated evaluation above.
- Calibration data (threshold selection) is **separate** from the 22-case final set (90 disjoint calibration questions; see `evaluation/calibration/`); thresholds are never selected from these 22 cases (see `docs/abstention_methodology.md`).
- Retrieval edge cases (vocabulary mismatch, two-document, distractor, absent-but-plausible) are analysed with measured scores in `docs/retrieval_edge_cases.md`; synthetic-data construction and its ceiling effects are documented in `docs/data_generation.md`.

## 15. Frozen assets (do not modify without a disclosed, dated amendment)

`ground_truth.json`, the 16 files in `15 policy files/` (15 current + 1 superseded), `baseline/`, the Stage 1 results, Stage 2 retrieval results/methodology, the Stage 3 calibration set, `rag/thresholds.py`, and the Stage 3 methodology.

## 15a. One disclosed exception (2026-09-19)

Per reviewer feedback, two of these frozen assets were intentionally amended once: the corpus gained one file (`16_provincial_trade_policy_2019_superseded.txt`) plus a short cross-reference/contradiction paragraph in two existing files, and `ground_truth.json` gained TC21/TC22. Because the corpus changed, the calibration set and `rag/thresholds.py` were mechanically regenerated by re-running the existing, unmodified pipeline scripts (§11) — no scoring rule or threshold-selection rule was changed. TC01–TC20 and their expected values are untouched. Full rationale: `ground_truth.json`'s `_meta.amendment`.

## 16. Final results (EXECUTED — Foundation Model ran on all answer-eligible cases)

The headline numbers are in the **Evaluation summary** table at the top.

Component detail:

- **Primary metric — citation-grounded answer correctness: 10/12 (83.33%)** of answerable cases (human-graded; 2 disclosure failures: TC21 — superseded edition not flagged, TC22 — unreconciled gift-policy conflict reduced to a bare "No." — see `docs/failure_analysis.md` §3).
- Deterministic action correctness: **22/22 (100%)**, compared with 54.5% for both baseline methods (see `trivial_baselines_decision_metric` in `evaluation/results/comparison.json`).
- Evidence grounding: **17/17 (100%)**.
- Ambiguous → clarification **5/5**; insufficient evidence → abstain **5/5** (two-layer defence: 2 deterministic + 3 rejected by the model itself); conflicting/outdated policy **2/2** at the action level (both answer texts failed the conflict/supersession disclosure — see `docs/failure_analysis.md` §3).
- Cost/latency (recomputed by `evaluation/compare.py`): 15 Foundation Model calls, total API cost **~US$0.00483**, retrieval median **~2.79 ms**, model median/P95 **~2.09 s / ~5.77 s**, end-to-end median/P95 **~1.55 s / ~5.55 s**.
- **Scale estimate (assumption-based):** assuming 100 policy questions per workday × 250 workdays = 25,000 incoming questions/year, and applying the observed average API cost of approximately **US$0.00022 per incoming question** across the frozen 22-case evaluation set, the estimated annual Foundation Model API cost is approximately **US$5.5/year**. The 100-questions-per-day workload is an assumption, not a measured usage level.
- Earlier experiment (Stage 3, pre-Foundation-Model, superseded): baseline retrieval grounding top-1 0.647 / top-3 1.000; RAG TF-IDF retrieval grounding 0.706; deterministic action accuracy 14/22. Retained as development history in `docs/failure_analysis.md` §1.

## 17. Known limitations

- TF-IDF cannot reason about numeric thresholds → weak raw cosine on boundary questions (TC06–08 as low as 0.087); deterministic numeric/domain signals compensate for the measured cases, but the lexical weakness is structural (`docs/retrieval_edge_cases.md`).
- Calibrated abstention thresholds cannot perfectly separate answerable from insufficient (score overlap) → some insufficient cases do not abstain deterministically (the Foundation Model layer catches them instead).
- Clarification can slightly over-trigger on single-track boundary questions.
- The margin signal is dual-purpose and can misfire on genuinely joint current/superseded evidence (TC21: margin 0.0229 < `MARGIN_MIN`; the multi-source carve-out kept the routing action correct, but the answer text failed the supersession disclosure — `docs/abstention_methodology.md` §5).
- Correct retrieval does not guarantee complete disclosure: 2 of 12 final answers failed to disclose supersession/conflict information even though the evidence was retrieved and cited (TC21, TC22).
- Corpus is synthetic and small (16 docs, single authorial voice); results should not be generalized — see `docs/data_generation.md` §5.

## 18. Security considerations

See `docs/security_governance.md`: prompt-injection defence (evidence is data), no secrets in source, malformed-output rejection, deterministic abstention, and a human-in-the-loop posture. Verify every answer against current policy.

---

### Repository layout

```text
15 policy files/            synthetic corpus (16 .txt — 15 current + 1 superseded)
baseline/                   Stage 1 keyword baseline (frozen)
rag/                        retriever, signals, decision, thresholds (regenerated
                            on the one disclosed corpus change, §15a),
                            prompt, model_client, rag_answer, tests
evaluation/                 runners, evaluate, compare, failure analysis
  calibration/              separate calibration set + calibrator
  results/                   per-stage JSON results
app/                        streamlit_app.py (MVP UI)
docs/                       methodology, retrieval edge cases, data generation,
                            failure analysis, cost/scale trade-off, security, report
ground_truth.json            22-case evaluation set (20 original + TC21/TC22)
requirements.txt  .env.example  .gitignore  README.md
```