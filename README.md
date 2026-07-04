# SBL Availability & Borrow Cost Tracker

A mock analytics stack that turns simulated Stock Borrowing & Lending (SBL) data
for Thai equities into front-office decision support: borrow availability,
borrow cost, utilization, a days-to-cover proxy, a transparent hard-to-borrow
flag, and sector-level borrow pressure — stored in SQL and surfaced through a
Power BI dashboard, with an auto-generated sales-trading memo.

> **This project uses simulated SBL data for portfolio demonstration only. It
> does not use real broker, exchange, custodian, or client data.** Ticker names
> are real SET symbols, but all borrow/lending figures are generated.

## Why this exists

In sales trading and execution, short-selling depends on whether a name can be
borrowed, how much is available, what it costs, and whether it is tightening.
This project shows how that data can be modelled, cleaned, stored, and read by a
desk to spot locate risk, rising borrow cost, and hard-to-borrow names before
short-sale execution or a client conversation.

## What Stock Borrowing & Lending is (in one paragraph)

A short seller must first borrow the shares to deliver them. Lenders (funds,
custodians) put shares into a lendable pool; borrowers pay a fee (in bps of
notional) and post collateral; an agent keeps a spread between what the borrower
pays and what the lender earns. When a large share of the pool is already on
loan (**high utilization**) or demand is high, the name gets **expensive** and
can become **hard to borrow** — which is exactly what a desk needs to see early.

## Pipeline

```
generate_mock_data.py   ->  data/raw/mock_sbl_raw.csv
transform_sbl_data.py   ->  data/processed/sbl_cleaned.csv
metrics.py              ->  data/processed/sbl_analytics.csv (+ sector CSV)
load_to_postgres.py     ->  PostgreSQL  (primary storage)  + SQL views
memo_generator.py       ->  reports/sbl_sales_trading_memo.md
Power BI                ->  reads the SQL views (see powerbi/README.md)
```

## How to run

Bash / macOS / Linux:

```bash
pip install -r requirements.txt

# 1) full local pipeline (no database needed): CSVs + memo + local DuckDB
python src/run_pipeline.py

# 2) tests
pytest -q

# 3) primary storage: Postgres via Docker, then load
docker compose up -d
PG_DSN=postgresql+psycopg2://sbl:sbl@localhost:5432/sbl python src/load_to_postgres.py

# 4) dashboard: open Power BI Desktop and follow powerbi/README.md
```

Windows PowerShell:

```powershell
python -m pip install -r requirements.txt

# 1) full local pipeline (no database needed): CSVs + memo + local DuckDB
python src/run_pipeline.py

# 2) tests
python -m pytest -q

# 3) primary storage: Postgres via Docker, then load
docker compose up -d
$env:PG_DSN = "postgresql+psycopg2://sbl:sbl@localhost:5432/sbl"
python src/load_to_postgres.py

# 4) dashboard: open Power BI Desktop and follow powerbi/README.md
```

## Metric definitions

| Metric | Definition | Note |
|---|---|---|
| `utilization_pct` | `100 × borrowed_qty / total_lendable_qty` | Share of the pool on loan. |
| `available_borrow_value` | `available_borrow_qty × close_price` | Borrow left, in THB. |
| `borrowed_value` | `borrowed_qty × close_price` | Current borrow demand, in THB. |
| `days_to_cover_proxy` | `borrowed_value / avg_daily_value` | Crowding gauge. **Proxy**, not true short interest (see below). |
| `daily_available_change_pct` | day-over-day % change in available qty | Needs a persistent series (per-symbol LAG). |
| `daily_fee_change_bps` | day-over-day change in fee | Momentum in cost. |
| `intermediary_spread_bps` | `borrow_fee_bps − lending_rate_bps` | Agent's cut; borrower pays ≥ lender earns. |
| `hard_to_borrow_flag` | ≥ 2 of 3 axes true | See below. |
| `sector_pressure_score` | weighted sum of **normalised** avg utilization, avg fee, HTB ratio | Components min-max'd across sectors first. |

### Hard-to-borrow: three independent axes (flag if ≥ 2 true)

- **A — supply tightness:** `utilization_pct ≥ 85`
- **B — cost:** `borrow_fee_bps ≥ 300`
- **C — crowding:** `days_to_cover_proxy ≥ 2.0`

Momentum escalators (colour / watchlist only, not counted): availability drop
`≤ −30%`, fee jump `≥ +100 bps`.

*Why three separate axes:* under the pool identity, availability ratio is just
`1 − utilization`, so a "low availability" test would be the same signal as the
utilization test. The three axes here answer genuinely different questions —
how much of the pool is used, how expensive it is, how crowded it is versus
liquidity — so "2 of 3" is meaningful. (Measured axis correlations on the mock
data are modest, confirming they are not redundant.)

## Data-generating process (the important part)

Data is a **panel** with persistent, autocorrelated series, not IID random
draws — otherwise the daily-change metrics and HTB clustering would be noise.
Utilization follows a mean-reverting AR(1) process on the logit scale with a
shared **sector factor**; the borrow fee is mean-reverting and **coupled to
utilization** (tight supply → dearer borrow) with occasional "goes special"
jumps; quantities are derived from utilization and the pool so that
`total_lendable = available + borrowed` holds by construction. See
`src/config.py` for every parameter and `src/generate_mock_data.py` for the
equations.

## Repo structure

```
├── docker-compose.yml        # local Postgres
├── requirements.txt
├── sql/                      # schema.sql, views.sql
├── src/                      # config, generate, transform, metrics, memo, loaders
├── powerbi/                  # dashboard build guide + .pbix + screenshots
├── reports/                  # generated sales-trading memo
├── data/{raw,processed}/     # generated CSVs + local DuckDB
└── tests/                    # metric validation (pool identity, HTB, etc.)
```

## Design decisions

These are the main engineering choices behind the project:

- **Why days-to-cover, not short interest:** true short interest is short shares
  / float; borrowed volume includes settlement and arbitrage, and there is no
  float here — so borrowed notional / average daily value (a days-to-cover
  intuition) is the honest proxy.
- **Why the HTB flag changed:** two of the original conditions were the same
  variable in disguise once the pool identity is applied; the flag now uses
  three independent dimensions.
- **Why mean-reverting data:** daily-change and hard-to-borrow clustering only
  make sense on a persistent series; fee is coupled to utilization so tightness
  and cost move together, and a sector factor makes sector pressure a real
  signal.
- **Architecture:** Python pipeline → Postgres (via Docker) → SQL views → Power
  BI. Views push logic into SQL and keep the DAX simple.

## Note on real Thai rules

Any reference to real short-sale / SBL rules on SET (short-sale eligibility,
price rules, TSD/broker routing) should be verified against current SET / SEC
Thailand sources; those rules have changed recently. The analytics here stay on
mock data.
