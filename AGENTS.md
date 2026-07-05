# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## What this is

A portfolio-demo analytics stack that simulates daily Stock Borrowing & Lending (SBL) data for
Thai (SET) equities and turns it into front-office decision support: borrow availability, borrow
cost, utilization, a days-to-cover proxy, a hard-to-borrow flag, and sector borrow pressure.
**All borrow/lending figures are simulated** — ticker symbols are real SET names but there is no
real broker/exchange/custodian/client data. Keep any new code on mock data.

## Commands

Run everything **from the repo root** (relative data paths in `config.py` assume it):

```bash
pip install -r requirements.txt

python src/run_pipeline.py      # full local pipeline: CSVs + memo + local DuckDB (no DB needed)
pytest -q                       # run tests
pytest -q tests/test_metrics.py::test_pool_identity_holds   # single test

# Primary storage path (Postgres via Docker):
docker compose up -d
PG_DSN=postgresql+psycopg2://sbl:sbl@localhost:5432/sbl python src/load_to_postgres.py
```

Each `src/*.py` module is also runnable standalone (`python src/metrics.py`, etc.) and reads/writes
its stage's CSVs — useful for iterating on one stage without rerunning the whole pipeline.

## Import convention (important)

Modules import each other and config by **bare name** (`import config as C`, `from metrics import ...`),
relying on `src/` being on `sys.path`. This works because Python adds a script's own directory to the
path, so `python src/<module>.py` and `python src/run_pipeline.py` both resolve. Tests insert `src/`
onto `sys.path` explicitly (see `tests/test_metrics.py`). Do **not** convert these to package-relative
imports (`from src.x import ...`) — it would break the standalone-script and pipeline entry points.

## Architecture

Linear pipeline, one module per stage, all parameters centralized in `src/config.py`:

```
generate_mock_data.generate()  -> raw panel        -> data/raw/mock_sbl_raw.csv
transform_sbl_data.clean()     -> cleaned panel    -> data/processed/sbl_cleaned.csv
metrics.compute_metrics()      -> analytics + ...   -> data/processed/sbl_analytics.csv
metrics.sector_pressure()      -> sector snapshot  -> data/processed/sbl_sector_pressure.csv
memo_generator.build_memo()    -> desk memo        -> reports/sbl_sales_trading_memo.md
load_to_postgres.main()        -> Postgres table + SQL views (sql/schema.sql, sql/views.sql)
Power BI reads the SQL views  (see powerbi/README.md)
```

`run_pipeline.py` chains generate→clean→metrics→memo and also writes a local **DuckDB**
(`sbl_analytics.duckdb`) with a `v_latest_snapshot` view, so SQL/views work without Postgres.
The Postgres path is separate and optional (the DuckDB and Postgres views mirror each other).

### Key domain design (the parts that need multiple files to understand)

- **The data is a persistent panel, not IID draws.** `generate_mock_data.py` evolves per-symbol
  state day over day: utilization is AR(1) mean-reversion on the **logit scale** plus a shared
  per-sector factor; the borrow fee is mean-reverting and **coupled to utilization** (tight supply
  → dearer borrow) with rare "goes special" jumps. This persistence is what makes the day-over-day
  change metrics and hard-to-borrow clustering meaningful rather than noise. Everything is seeded
  (`C.SEED`) for reproducibility.

- **Pool identity `total_lendable = available + borrowed` holds by construction.** Quantities are
  derived from utilization × pool. `transform_sbl_data.clean()` re-enforces it after repairs, and
  `test_pool_identity_holds` asserts it exactly. Preserve this invariant in any change to generation,
  cleaning, or metrics.

- **Data-quality handling is real, not cosmetic.** `generate` deliberately injects missing fees,
  negative quantities, and duplicate `(date, symbol)` rows (rates in `config.py`); `clean` drops
  duplicates, repairs negatives via the pool identity, forward/back-fills fee+rate together, and
  rewrites `data_quality_note` to `repaired`. `data_quality_note` drives the handling.

- **Hard-to-borrow flag = ≥ 2 of 3 *distinct* axes** (util ≥ 85%, fee ≥ 300 bps, days-to-cover
  ≥ 2.0). The three axes are deliberately non-redundant *measurements* — a "low availability" test
  would just be `1 − utilization` again — but they are NOT claimed to be statistically independent:
  fee is coupled to utilization in the generator, so they co-move in stressed names and 2-of-3 acts
  as a confirmation rule (`metrics.htb_diagnostics()` prints the real correlations and firing rates).
  `test_htb_axes_are_distinct` guards this. Availability-drop and fee-spike are **momentum
  escalators** for colour/watchlist only; they do NOT count toward the 2-of-3.

- **Sector pressure normalises before summing.** `sector_pressure()` min-max scales avg utilization,
  avg fee, and HTB ratio **across sectors** first, then takes the equal-weighted sum (`C.SECTOR_WEIGHTS`),
  so the score stays in [0,1] and no raw-scale component dominates. It operates on a single snapshot
  date (default: latest).

Thresholds, weights, universe, and the full data-generating process live in `config.py` — tune there,
not in the stage modules. Metric definitions and the domain rationale are documented in `README.md`.
