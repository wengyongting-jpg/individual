# sql-table-join — Computed JOIN paths for Text-to-SQL

The deterministic table-join core of my Enterprise Data Analysis Agent (Text-to-SQL & data workflow design). Instead of letting an LLM guess multi-table JOIN conditions — the largest error source in generated SQL — this tool computes them from a declarative table-relation graph.

## Why this exists

The tool originated in a live enterprise reporting workflow — weekly analytical reports assembled from a relational database — where join hallucination was the dominant Text-to-SQL failure mode. Single-shot Text-to-SQL is reliable on single-table questions but error-prone on multi-table JOINs: the model invents wrong join keys or misses intermediate tables. The agent therefore splits generation into stages — intent parsing → field identification → **join resolution (this tool)** → SQL assembly — so join paths are derived by graph traversal, not model guesswork. In live use, this split produced complex multi-table SQL (filters, aggregation, window functions layered on the deterministic join skeleton) with no join hallucination.

## How it works

- **Relation graph** (`correlation.json` → `nextarc`): each table maps to its neighbours with join keys (`key` = this table's column, `next_key` = the other table's column).
- **Field → table mapping** (`table_column`): every field belongs to exactly one table.
- **Greedy base-table selection** (`SQLBuilder.build_init_`): repeatedly take the table that covers the most still-uncovered requested fields.
- **BFS join-path search** (`algorithm.find_join_path_to_target`): from the already-joined tables, find the shortest join path to the next target table over FK/PK edges.
- **Topological ordering** (`algorithm.topological_sort`): deterministic table order + cycle detection on the relation graph.
- **SQL assembly** (`sql_builder.SQLBuilder`): emits `SELECT` / `FROM` / `LEFT JOIN ... ON ...` with automatic aliases (`T0`, `T1`, ...), early exit once all requested fields are covered, and an explicit error when the requested fields' tables cannot be connected.
- **Syntax validation** (`check_sql_syntax`): generated SQL is parsed with [sqlglot](https://github.com/tobymao/sqlglot) before it is handed on.

Also included: simple `INSERT` / `UPDATE` / `DELETE` builders.

## Usage

```python
from sql_builder import SQLBuilder

s = SQLBuilder()
print(s.build_sql(["SUB_MODEL_ID", "SUB_MODEL_NAME", "VERSION_ID", "VERSION_NAME", "SALES_QTY", "YM_ID"]))
```

To adapt the tool to your own database, edit the `nextarc` relations in `correlation.json`. After the first initialisation, if the join relations have not changed, you can switch `SQLBuilder.__init__()`'s `self.tables` to read the precomputed value directly instead of re-running the topological sort every time.

Dependencies: `pip install sqlglot` (used by the validation step; the deterministic core itself has no third-party dependencies).

## Scope note

This is the reduced public version — only the key core is kept. The full internal project covers additional modules (staged intent parsing, read-only execution, result validation, business-glossary loading) that may not have been fully stripped from these files.

## Related

Module 2 of the **Enterprise AI Assistant Suite** (this repository). Module 1 — the Grounded Enterprise Policy Assistant in the repo root — applies the same design philosophy (deterministic gating before probabilistic generation) to policy Q&A.
