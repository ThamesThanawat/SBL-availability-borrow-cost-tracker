"""
test_sector_pressure_parity.py -- keeps Python and SQL sector pressure in sync.
"""

import pathlib
import sys

import duckdb
import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from generate_mock_data import generate  # noqa: E402
from metrics import compute_metrics, sector_pressure  # noqa: E402
from transform_sbl_data import clean  # noqa: E402


ROOT = pathlib.Path(__file__).resolve().parents[1]


def _sql_statements(path: pathlib.Path) -> list[str]:
    sql = path.read_text(encoding="utf-8")
    uncommented = "\n".join(line.split("--", 1)[0] for line in sql.splitlines())
    return [stmt.strip() for stmt in uncommented.split(";") if stmt.strip()]


def test_sector_pressure_matches_sql_view():
    raw = generate()
    cleaned = clean(raw)
    metrics_df = compute_metrics(cleaned)

    con = duckdb.connect(":memory:")
    con.register("metrics_df", metrics_df)
    con.execute("CREATE TABLE sbl_daily_metrics AS SELECT * FROM metrics_df")

    for stmt in _sql_statements(ROOT / "sql" / "views.sql"):
        con.execute(stmt)

    sql_df = con.execute("""
        SELECT sector, sector_pressure_score
        FROM v_sector_pressure
    """).df()
    py_df = sector_pressure(metrics_df)[["sector", "sector_pressure_score"]]

    merged = py_df.merge(sql_df, on="sector", suffixes=("_python", "_sql"))

    assert len(merged) == len(py_df) == len(sql_df)
    np.testing.assert_allclose(
        merged["sector_pressure_score_python"],
        merged["sector_pressure_score_sql"],
        rtol=0,
        atol=1e-6,
    )

    py_ranking = py_df.sort_values(
        "sector_pressure_score", ascending=False
    )["sector"].tolist()
    sql_ranking = sql_df.sort_values(
        "sector_pressure_score", ascending=False
    )["sector"].tolist()
    assert py_ranking == sql_ranking
