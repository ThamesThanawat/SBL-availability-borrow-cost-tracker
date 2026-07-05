"""
run_pipeline.py

Runs the full LOCAL pipeline end to end (no Postgres server needed):
  generate -> clean -> metrics + sector pressure -> memo -> DuckDB

For the Postgres path (primary storage in the PRD), use load_to_postgres.py
after this, once a Postgres instance is up (see docker-compose.yml).
"""

from __future__ import annotations

import duckdb

import config as C
from generate_mock_data import generate
from transform_sbl_data import clean
from metrics import compute_metrics, sector_pressure, htb_diagnostics
from memo_generator import build_memo, write_memo


def main() -> None:
    raw = generate()
    raw.to_csv(C.RAW_PATH, index=False)
    print(f"[1/5] raw     : {len(raw):,} rows -> {C.RAW_PATH}")

    cleaned = clean(raw)
    cleaned.to_csv(C.CLEAN_PATH, index=False)
    print(f"[2/5] cleaned : {len(cleaned):,} rows -> {C.CLEAN_PATH}")

    metrics = compute_metrics(cleaned)
    metrics.to_csv(C.METRICS_PATH, index=False)
    sect = sector_pressure(metrics)
    sect.to_csv(C.SECTOR_PATH, index=False)
    print(f"[3/5] metrics : {len(metrics):,} rows -> {C.METRICS_PATH}")

    memo = build_memo(metrics)
    write_memo(C.MEMO_PATH, memo)
    print(f"[4/5] memo    : -> {C.MEMO_PATH}")

    # Optional local analytics DB (DuckDB) so SQL / views work without Postgres
    con = duckdb.connect(C.DUCKDB_PATH)
    con.execute("DROP TABLE IF EXISTS sbl_daily_metrics")
    con.register("m", metrics)
    con.execute("CREATE TABLE sbl_daily_metrics AS SELECT * FROM m")
    con.execute("""
        CREATE OR REPLACE VIEW v_latest_snapshot AS
        SELECT * FROM sbl_daily_metrics
        WHERE date = (SELECT MAX(date) FROM sbl_daily_metrics)
    """)
    con.close()
    print(f"[5/5] duckdb  : -> {C.DUCKDB_PATH}")

    # Diagnostics: publish the real HTB axis correlations & firing rates so the
    # "distinct, not independent" claim is backed by numbers on every run.
    htb_diagnostics(metrics)


if __name__ == "__main__":
    main()
