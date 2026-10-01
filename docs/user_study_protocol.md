# Independent User Study Protocol

> **Purpose.** The primary evaluation metric (citation-grounded answer
> correctness) measures the *system*. This protocol measures the *user*:
> whether the RAG assistant actually helps a procurement/finance staff member
> complete a policy-lookup task **faster and at least as accurately** as
> manual keyword search. This is the project's **secondary metric** — median
> task-completion time — and it must be measured on independent testers, not
> on the project team.

> **Status: TARGET ONLY — DATA COLLECTION PENDING.** This protocol is
> prepared, but **no participants have been recruited and no participant data
> have been collected**. The ≥50% task-time reduction is a pre-registered
> **target**, not a measured result; nothing in the repository reports it as
> achieved. All committed results come from the executed automated
> evaluation. The study can be run as a future extension using the procedure
> below.

## 1. Why the team cannot run this on itself

The 16 policy documents were written by this team. The team already knows
where every rule lives, so any timing measured on team members would
understate manual search time and bias the comparison. Participants must
therefore be people who:

- did **not** author, review, or edit any of the 16 policy documents, and
- have **no prior familiarity** with the corpus structure.

A minimum planned sample of 3 participants is used for this pilot study.
More participants are preferable; a small sample is reported honestly as a limitation, not padded.
More is better; a small sample is reported honestly as a limitation, not padded.

## 2. Design (within-subject, counterbalanced)

Each participant answers the same fixed set of procurement-policy questions
**twice**: once with manual keyword search over the policy corpus
(`python baseline/keyword_search.py`, or reading the `.txt` files directly),
and once with the RAG assistant (`streamlit run app/streamlit_app.py`).

To cancel out ordering/learning effects, the method order is counterbalanced
across participants:

| Participant | Round 1     | Round 2     |
|-------------|-------------|-------------|
| P1          | Manual search | RAG       |
| P2          | RAG           | Manual search |
| P3          | Manual search | RAG       |

Use **answerable and boundary questions** from the frozen ground truth
(e.g. TC01–TC10) as the study questions — questions where a correct,
checkable answer exists. Do not use abstain/clarify cases for timing
comparisons; they measure a different capability.

Rules during the study:

1. Read the question aloud, start the timer when the participant begins.
2. Stop the timer when the participant states a final answer they would act
   on (including the citation/policy section they relied on).
3. Record the answer as correct/incorrect against `ground_truth.json`'s
   `expected_answer`. Correctness is judged against the same ground truth as
   the automated evaluation — no separate, softer standard.
4. The participant may not ask the facilitator for help. If they give up,
   record the elapsed time and mark `correct = false`.
5. No participant sees the same question twice under the same method; each
   question is answered once per method, per participant.

## 3. Data recording

Record one row per (participant, question, method) attempt in
`evaluation/results/user_study_results.csv`:

| Column | Meaning |
|---|---|
| `participant_id` | P1, P2, P3, ... |
| `question_id` | ground-truth case ID (e.g. TC03) |
| `method` | `manual` or `rag` |
| `completion_time_seconds` | wall-clock seconds from question start to final answer |
| `correct` | `true` / `false` against `expected_answer` |

The committed CSV contains **headers only** until the study is actually run.
No rows are ever invented to reach a target number.

## 4. Analysis

Run:

```bash
python evaluation/analyze_user_study.py
```

This reads the CSV and writes `evaluation/results/user_study_summary.json`
with:

- participants, per-method attempt counts;
- **median manual-search time** and **median RAG time** (seconds);
- **median time reduction %** = (manual − RAG) / manual × 100;
- per-method **accuracy** (fraction of attempts marked correct);
- whether the project target (**≥ 50% median time reduction**) was met.

`evaluation/compare.py` then picks the summary up automatically and reports
it under `secondary_metric_task_completion_time`.

## 5. Honesty rule

The target is a hypothesis to test, **not a number to hit**. If the measured
median time reduction is below 50% — or even negative — the measured value is
reported as-is, with the small sample size acknowledged as a limitation.
Cherry-picking questions, participants, or runs to reach 50% would invalidate
the study and is explicitly out of scope.
