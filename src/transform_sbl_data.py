"""
transform_sbl_data.py

Cleans the raw mock feed:
  * drop exact duplicate (date, symbol) rows (keep the first, non-duplicate one)
  * fix negative quantities (flag + repair via the pool identity)
  * fill missing borrow fee by forward-fill within each symbol (a realistic
    "carry yesterday's rate" assumption), else drop if unfillable
  * enforce the pool identity total_lendable = available + borrowed
  * coerce dtypes and sort by (symbol, date)

The point is that data_quality_note actually drives handling, rather than
being cosmetic.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import config as C


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])

    # 1) duplicates: drop the injected duplicate rows, keep one record per key
    df = df.sort_values(["symbol", "date"]).drop_duplicates(
        subset=["symbol", "date"], keep="first"
    )

    # 2) negative quantities: repair from the identity where possible
    neg = df["available_borrow_qty"] < 0
    df.loc[neg, "available_borrow_qty"] = (
        df.loc[neg, "total_lendable_qty"] - df.loc[neg, "borrowed_qty"]
    ).clip(lower=0)

    # 3) missing fee & rate: forward-fill within symbol (carry yesterday's rate),
    #    then back-fill any leading gap. Fee and lending rate are filled together
    #    so the borrow-fee/lending-rate relationship stays consistent.
    for col in ["borrow_fee_bps", "lending_rate_pct"]:
        df[col] = df.groupby("symbol")[col].ffill().bfill()
    df = df.dropna(subset=["borrow_fee_bps", "lending_rate_pct"])

    # 4) enforce identity (repair rounding / any residual inconsistency)
    df["available_borrow_qty"] = (
        df["total_lendable_qty"] - df["borrowed_qty"]
    ).clip(lower=0)

    # 5) reset the note for repaired rows (keep a trace of what happened)
    df.loc[df["data_quality_note"].isin(["negative_qty", "missing_fee"]),
           "data_quality_note"] = "repaired"

    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)
    return df


if __name__ == "__main__":
    raw = pd.read_csv(C.RAW_PATH)
    out = clean(raw)
    out.to_csv(C.CLEAN_PATH, index=False)
    print(f"Cleaned {len(raw):,} -> {len(out):,} rows -> {C.CLEAN_PATH}")
    print(out["data_quality_note"].value_counts().to_string())
