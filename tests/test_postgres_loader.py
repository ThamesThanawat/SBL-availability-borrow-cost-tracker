"""
test_postgres_loader.py -- validates SQL-file parsing without a live Postgres.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from load_to_postgres import _sql_statements  # noqa: E402


def test_views_sql_parser_ignores_comment_semicolons():
    statements = _sql_statements("sql/views.sql")

    assert len(statements) == 3
    assert all(stmt.startswith("CREATE OR REPLACE VIEW") for stmt in statements)


def test_schema_sql_parser_ignores_comment_lines():
    statements = _sql_statements("sql/schema.sql")

    assert len(statements) == 3
    assert statements[0].startswith("CREATE TABLE sbl_daily_metrics")
