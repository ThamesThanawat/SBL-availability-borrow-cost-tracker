"""
load_to_postgres.py  --  PRD v2 section 12 (primary storage)

Loads the computed metrics into PostgreSQL and (re)creates the views that
Power BI reads. Connection is read from PG_DSN or the individual PG* env vars
(see docker-compose.yml for a ready-to-run local instance).

    export PG_DSN=postgresql+psycopg2://sbl:sbl@localhost:5432/sbl
    python src/load_to_postgres.py

Requires: sqlalchemy, psycopg2-binary  (see requirements.txt)
"""

from __future__ import annotations

import os
import pathlib

import pandas as pd
from sqlalchemy import create_engine, text

import config as C

TABLE = "sbl_daily_metrics"


def _dsn() -> str:
    if os.getenv("PG_DSN"):
        return os.environ["PG_DSN"]
    user = os.getenv("PGUSER", "sbl")
    pwd = os.getenv("PGPASSWORD", "sbl")
    host = os.getenv("PGHOST", "localhost")
    port = os.getenv("PGPORT", "5432")
    db = os.getenv("PGDATABASE", "sbl")
    return f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{db}"


def main() -> None:
    metrics = pd.read_csv(C.METRICS_PATH, parse_dates=["date"])
    engine = create_engine(_dsn())

    schema_sql = pathlib.Path("sql/schema.sql").read_text()
    views_sql = pathlib.Path("sql/views.sql").read_text()

    with engine.begin() as con:
        con.execute(text(f"DROP TABLE IF EXISTS {TABLE} CASCADE"))
        for stmt in filter(str.strip, schema_sql.split(";")):
            con.execute(text(stmt))

    # append rows (table already created by schema.sql)
    metrics.to_sql(TABLE, engine, if_exists="append", index=False)

    with engine.begin() as con:
        for stmt in filter(str.strip, views_sql.split(";")):
            con.execute(text(stmt))

    print(f"Loaded {len(metrics):,} rows into Postgres table '{TABLE}' and rebuilt views.")


if __name__ == "__main__":
    main()
