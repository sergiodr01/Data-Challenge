# Symrise Data Engineering Challenge — Sergio Diaz

An ETL pipeline that ingests, validates, cleans, and loads Symrise's flavor/fragrance
product, sales, feedback, and ingredient-cost data into SQLite, plus the SQL analysis,
visualizations, and business-question answers built on top of it. See
[`challengers/README.md`](challengers/README.md) for the original challenge brief.

## Overview

The pipeline runs five stages end-to-end: **extract → validate → transform → validate →
load**. Validation runs twice — once on the raw CSVs and once after cleaning — because
`transform.py` follows two ground rules everywhere: never drop a row just because one
field is unrecoverable, and never fabricate a value that can't be derived from other
columns in the same row. Whatever survives cleaning is reported, not silently loaded.
See [`output/data_quality_report.md`](output/data_quality_report.md) for the full
findings and [`output/business_answers.md`](output/business_answers.md) for the 5
business questions.

## Prerequisites

- Python 3.12+ (developed and tested on 3.14)
- No external database server — SQLite ships with Python's standard library

## Setup

```powershell
git clone <https://github.com/sergiodr01/Data-Challenge.git>
cd Sergio-Diaz-symrise-challenge

python -m venv .venv
.venv\Scripts\Activate.ps1        # PowerShell. cmd.exe: .venv\Scripts\activate.bat
                                   # macOS/Linux: source .venv/bin/activate

pip install -r requirements.txt
```

## Running the pipeline

```powershell
python -m src.pipeline
```

This reads `config/pipeline_config.yaml` for file paths, log settings, and the
`quality_thresholds` used to clip out-of-range ratings; reads `config/schema.yaml` for
the data contract (required columns, types, closed vocabularies, numeric floors); and
writes:
- `symrise_data.db` — the loaded SQLite database (dropped and recreated on every run,
  so running the pipeline twice never accumulates duplicate rows)
- `output/pipeline.log` — full run log (console output mirrors it)

If a dataset is missing a required column, has the wrong fundamental type in a column,
or is empty, the pipeline stops immediately with a short, specific message (e.g.
`[products] missing required column 'category'`) instead of a Python traceback — see
*Design Decisions* below.

### Other commands

```powershell
python -m src.visualize        # 5 PNG charts -> output/visualizations/
pytest tests/ -v                # 71 tests across extract/validate/transform/load/pipeline
```

Business-question and exploratory SQL queries are plain `.sql` files
(`sql/queries.sql`, `sql/analysis.sql`); run them with any SQLite client, e.g.:
```powershell
sqlite3 symrise_data.db < sql/queries.sql
```
or open `symrise_data.db` in [DB Browser for SQLite](https://sqlitebrowser.org/) and
paste a query in the "Execute SQL" tab.

### Notebook

[`notebooks/exploratory_analysis.ipynb`](notebooks/exploratory_analysis.ipynb) is a
presentation layer, not a second implementation: it reads the same
`sql/queries.sql` / `sql/analysis.sql` files from disk and calls the same
`src.visualize.generate_all()` used above, so nothing is redefined or hand-copied —
re-running it after `python -m src.pipeline` always reflects the current database.
Open it in VS Code (Jupyter extension) or run
`jupyter nbconvert --to notebook --execute --inplace notebooks/exploratory_analysis.ipynb`
after activating the venv.

## Database schema overview

| Table | Role | Primary key | Foreign key |
|---|---|---|---|
| `products` | Dimension | `product_id` | — |
| `ingredients` | Dimension | `ingredient_id` | — |
| `sales` | Fact | `transaction_id` | `product_id` → `products.product_id` |
| `feedback` | Fact | `feedback_id` | `product_id` → `products.product_id` |

`products.primary_ingredient` links to `ingredients.ingredient_name` **by value**, not
by a declared foreign key — `products.csv` has no `ingredient_id` column, only the
ingredient's name, so that join is validated separately (see the data quality report's
"Additional guardrails"). The full column list, types, and constraints for every table
are declared in [`config/schema.yaml`](config/schema.yaml), the single source of truth
that `validate.py`, `transform.py`, and `load.py` all read from.

## Design decisions

- **Two-tier validation.** `validate.validate_structure()` is a hard gate (missing
  required column, wrong fundamental type, or an empty dataset stops the pipeline
  immediately via `SchemaValidationError`) — a broken structure can't be cleaned or
  aggregated around. `validate.validate_all()` is a soft gate (nulls, duplicates,
  out-of-range values, closed-vocabulary violations, orphaned references) — these get
  logged and cleaned where possible, never used to halt the run.
- **One data contract, three consumers.** `config/schema.yaml` declares every column's
  type, required-ness, allowed values, and numeric floor once. `validate.py` enforces
  it, `transform.py` reads the same closed vocabularies to normalize region names, and
  `load.py` derives its SQLite column types from the same `dtype` values — so the
  database schema can never silently disagree with the validation contract. Primary
  keys, foreign keys, and `NOT NULL` constraints stay hand-declared in `load.py`
  instead, since those are database-structure decisions, not data-quality ones (a
  column can be "required" for quality-gate purposes while still carrying a known,
  allowed `NULL` in the database — see the report for `feedback.quality_rating`).
- **Fact vs. dimension ID conflicts are handled differently.** A repeated
  `transaction_id`/`feedback_id` with different content is an ID collision, not a
  duplicate — renamed (`T011` → `T011-DUP1`) instead of dropped, since nothing else
  references those IDs as foreign keys. A repeated `product_id`/`ingredient_id`/
  `ingredient_name` with different content is riskier to rename, since other tables
  already reference the original ID — if the conflicting rows agree on everything
  else, they're merged safely (logged as `info`); if they genuinely disagree, the
  first occurrence is kept and the conflict is logged loudly (`warning`), since
  guessing which version is "correct" isn't the pipeline's call to make.
  (See `transform._resolve_dimension_conflicts`.)
- **Orphan references are surfaced, not hidden.** `sales`/`feedback` rows referencing
  `product_id = 'P999'` (which doesn't exist in `products.csv`) are kept — dropping
  real revenue/feedback to make the table "clean" would understate the numbers. SQL
  queries bucket them explicitly (e.g. Q1's `'Unknown/Unmatched Product'` via
  `LEFT JOIN`) instead of letting them silently vanish from a join.
- **Config-driven thresholds, not hardcoded ones.** Rating bounds
  (`quality_thresholds.rating_min/max`) come from `pipeline_config.yaml`; changing them
  changes clipping behavior without touching code.
- **Clean failure messages for expected problems.** `pipeline.py` catches a specific
  set of "your data/config is broken" exceptions (`SchemaValidationError`,
  `FileNotFoundError`, `KeyError`, malformed/empty CSVs) at the CLI entry point and
  prints one short, actionable line instead of a full traceback — genuine bugs still
  surface with their full stack trace.
- **Idempotent load.** `load.py` drops and recreates the schema on every run inside a
  single transaction, so a failure partway through rolls back cleanly instead of
  leaving a half-loaded database.

## Assumptions

- **Feedback region** isn't a column in `customer_feedback.csv`. It's inferred by
  matching each feedback row to a sales transaction sharing the same
  `(customer_id, product_id)` pair, assuming a customer buys a given product from one
  consistent region — true everywhere it could be checked in this dataset (Q2).
- **"Last 2 quarters"** (Q4, declining sales trend) is computed **per product**, from
  whichever two quarters that product actually has sales in — not a fixed calendar
  window. A hardcoded range would misclassify products launched or discontinued
  outside that window as neither improving nor declining.
- **Ingredient cost** (Q5, profit margin) is based only on each product's single
  `primary_ingredient`, since `products.csv` records one ingredient per product, not
  the full bill of materials implied by `num_ingredients`. It's a directional estimate
  of formulation cost, not the true fully-loaded cost.

## Known limitations

- **Profit margin is likely overstated.** Only one ingredient's cost is counted per
  product (see above) — a product with 12 ingredients still only has 1 costed. The
  real margin is almost certainly lower. Fixing this exactly would require a
  product-to-ingredient bill-of-materials table that doesn't exist in the provided
  data — a data limitation, not something the pipeline can resolve.
- **The `P999` orphan reference** (2 rows across `sales`/`feedback`) can't be resolved
  from the data available; it's surfaced, not silently dropped or guessed at.
- **No `CORR()` in SQLite.** Q3's complexity-vs-satisfaction correlation is computed
  in `pandas` (`.corr()`) on the raw pairs; `sql/queries.sql` still provides the
  grouped-average view directly in SQL as a sanity check.
- **Scope.** This is a local batch pipeline over 4 CSVs run on demand — no
  scheduling, no incremental/streaming ingestion, no auth, no CI. Out of scope for
  this challenge, but the first things a production version would need.
