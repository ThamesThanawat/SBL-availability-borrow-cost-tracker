"""
test_metrics.py  --  validates the corrected PRD v2 logic.

Run from the repo root:   pytest -q
"""

import sys
import pathlib

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import config as C                       # noqa: E402
from generate_mock_data import generate  # noqa: E402
from transform_sbl_data import clean     # noqa: E402
from metrics import compute_metrics, sector_pressure  # noqa: E402
from memo_generator import build_memo, write_memo  # noqa: E402


@pytest.fixture(scope="module")
def data():
    raw = generate()
    cleaned = clean(raw)
    metrics = compute_metrics(cleaned)
    return metrics


def test_pool_identity_holds(data):
    # total_lendable = available + borrowed, exactly, after cleaning
    lhs = data["available_borrow_qty"] + data["borrowed_qty"]
    assert (lhs == data["total_lendable_qty"]).all()


def test_utilization_in_range(data):
    assert data["utilization_pct"].between(0, 100).all()


def test_no_negative_quantities(data):
    assert (data["available_borrow_qty"] >= 0).all()
    assert (data["borrowed_qty"] >= 0).all()


def test_days_to_cover_non_negative(data):
    assert (data["days_to_cover_proxy"] >= 0).all()


def test_intermediary_spread_non_negative(data):
    # borrower always pays >= what the lender receives
    assert (data["intermediary_spread_bps"] >= -1e-6).all()


def test_htb_flag_matches_two_of_three(data):
    a = data["utilization_pct"] >= C.HTB_UTIL_PCT
    b = data["borrow_fee_bps"] >= C.HTB_FEE_BPS
    c = data["days_to_cover_proxy"] >= C.HTB_DTC
    expected = (a.astype(int) + b.astype(int) + c.astype(int)) >= 2
    assert (data["hard_to_borrow_flag"] == expected).all()


def test_htb_axes_are_not_redundant(data):
    # sanity: the three axes should not be near-perfectly correlated,
    # which is the whole point of the v1 -> v2 fix.
    corr = data[["utilization_pct", "borrow_fee_bps", "days_to_cover_proxy"]].corr()
    off_diag = corr.values[np.triu_indices(3, k=1)]
    assert (np.abs(off_diag) < 0.98).all()


def test_sector_pressure_normalised(data):
    sect = sector_pressure(data)
    # equal-weight sum of three min-max [0,1] components -> within [0,1]
    assert sect["sector_pressure_score"].between(-1e-9, 1 + 1e-9).all()
    assert len(sect) == len(C.UNIVERSE)


def test_daily_change_uses_lag(data):
    # first observation per symbol has no previous day -> NaN change
    first = data.sort_values(["symbol", "date"]).groupby("symbol").head(1)
    assert first["daily_available_change_pct"].isna().all()


def test_memo_write_handles_unicode_symbols(data, tmp_path):
    memo = build_memo(data)
    assert "≤" in memo
    assert "≥" in memo

    path = tmp_path / "memo.md"
    write_memo(path, memo)

    assert path.read_text(encoding="utf-8") == memo
