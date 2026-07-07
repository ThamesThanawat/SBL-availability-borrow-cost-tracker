"""
test_short_eligibility.py -- validates period-matched SET100 short eligibility.
"""

import pathlib
import sys

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import config as C  # noqa: E402
from generate_mock_data import generate  # noqa: E402
from metrics import compute_metrics  # noqa: E402
from transform_sbl_data import clean  # noqa: E402


def _metrics() -> pd.DataFrame:
    raw = generate()
    cleaned = clean(raw)
    return compute_metrics(cleaned)


def test_set100_h1_2026_list_has_exactly_100_unique_symbols():
    assert len(C.SET100_H1_2026) == 100
    assert len(set(C.SET100_H1_2026)) == 100


def test_short_eligible_has_no_nulls_and_is_boolean():
    metrics = _metrics()

    assert metrics["short_eligible"].notna().all()
    assert pd.api.types.is_bool_dtype(metrics["short_eligible"])


def test_ori_and_thai_are_short_ineligible():
    metrics = _metrics()
    present = set(metrics["symbol"])

    expected = {"ORI", "THAI"}
    assert expected <= present

    for symbol in expected:
        assert not metrics.loc[metrics["symbol"] == symbol, "short_eligible"].any()


def test_known_set100_universe_names_are_short_eligible():
    metrics = _metrics()
    present = set(metrics["symbol"])

    expected = {"KBANK", "PTT", "ADVANC", "JMART"}
    assert expected <= present

    for symbol in expected:
        assert symbol in C.SET100_H1_2026
        assert metrics.loc[metrics["symbol"] == symbol, "short_eligible"].all()
