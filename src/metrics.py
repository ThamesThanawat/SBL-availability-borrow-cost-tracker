"""
metrics.py  --  PRD v2 section 8 (corrected logic)

Computes the analytics layer:
  * utilization, available/borrowed value, days-to-cover proxy
  * daily availability & fee changes (need a persistent series -> LAG per symbol)
  * intermediary spread (borrow fee vs lending rate)
  * hard-to-borrow flag on THREE DISTINCT (non-redundant) axes: v1's conditions
    were the SAME measurement (availability ratio == 1 - utilization under the
    pool identity); v2's axes measure genuinely different things (supply
    tightness, cost, crowding) that are EXPECTED to be positively correlated in
    stressed names, so 2-of-3 acts as a confirmation rule
  * sector borrow-pressure score with cross-sector NORMALISATION before summing
"""

from __future__ import annotations

import pandas as pd

import config as C


def compute_metrics(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)
    set100_h1_2026 = set(C.SET100_H1_2026)
    df["short_eligible"] = df["symbol"].isin(set100_h1_2026)

    # --- levels -------------------------------------------------------------
    df["utilization_pct"] = 100.0 * df["borrowed_qty"] / df["total_lendable_qty"]
    df["available_borrow_value"] = df["available_borrow_qty"] * df["close_price"]
    df["borrowed_value"] = df["borrowed_qty"] * df["close_price"]

    # days-to-cover proxy (renamed from "short interest proxy": borrowed
    # notional vs average daily traded value ~ days of volume to buy back)
    df["days_to_cover_proxy"] = df["borrowed_value"] / df["avg_daily_value"]

    # borrow fee vs lending rate -> intermediary spread
    df["lending_rate_bps"] = df["lending_rate_pct"] * 100.0
    df["intermediary_spread_bps"] = df["borrow_fee_bps"] - df["lending_rate_bps"]

    # --- daily changes (per-symbol LAG) -------------------------------------
    g = df.groupby("symbol", sort=False)
    prev_avail = g["available_borrow_qty"].shift(1)
    df["daily_available_change_pct"] = 100.0 * (
        df["available_borrow_qty"] / prev_avail - 1.0
    )
    df["daily_fee_change_bps"] = df["borrow_fee_bps"] - g["borrow_fee_bps"].shift(1)

    # --- hard-to-borrow: three distinct axes, flag if >= 2 true -------------
    # Distinct = different measurements, NOT uncorrelated. Fee is coupled to
    # utilization in the generator, so A and B are expected to co-move in
    # stressed names; 2-of-3 is a confirmation rule (see htb_diagnostics()).
    axis_a = df["utilization_pct"] >= C.HTB_UTIL_PCT          # supply tightness
    axis_b = df["borrow_fee_bps"] >= C.HTB_FEE_BPS            # cost
    axis_c = df["days_to_cover_proxy"] >= C.HTB_DTC           # crowding
    df["hard_to_borrow_flag"] = (
        axis_a.astype(int) + axis_b.astype(int) + axis_c.astype(int)
    ) >= 2

    esc_drop = df["daily_available_change_pct"] <= C.ESC_AVAIL_DROP_PCT
    esc_fee = df["daily_fee_change_bps"] >= C.ESC_FEE_JUMP_BPS
    df["hard_to_borrow_reason"] = [
        _reason(a, b, c, ed, ef, u, f, dtc)
        for a, b, c, ed, ef, u, f, dtc in zip(
            axis_a, axis_b, axis_c, esc_drop.fillna(False), esc_fee.fillna(False),
            df["utilization_pct"], df["borrow_fee_bps"], df["days_to_cover_proxy"],
        )
    ]

    return df


def _reason(a, b, c, esc_drop, esc_fee, util, fee, dtc) -> str:
    parts = []
    if a:
        parts.append(f"supply tight (util {util:.0f}%)")
    if b:
        parts.append(f"expensive ({fee:.0f} bps)")
    if c:
        parts.append(f"crowded (DTC {dtc:.1f})")
    if esc_drop:
        parts.append("availability dropping fast")
    if esc_fee:
        parts.append("fee spiking")
    return "; ".join(parts) if parts else "normal"


# ----------------------------------------------------------------------------
# Sector borrow-pressure (PRD v2 section 8.8) -- normalise, THEN sum
# ----------------------------------------------------------------------------
def _minmax(s: pd.Series) -> pd.Series:
    lo, hi = s.min(), s.max()
    if hi - lo < 1e-12:
        return pd.Series(0.0, index=s.index)
    return (s - lo) / (hi - lo)


def sector_pressure(df: pd.DataFrame, on_date=None) -> pd.DataFrame:
    """Sector pressure on a single snapshot date (default: latest)."""
    if on_date is None:
        on_date = df["date"].max()
    snap = df[df["date"] == on_date]

    agg = snap.groupby("sector").agg(
        avg_utilization=("utilization_pct", "mean"),
        avg_fee_bps=("borrow_fee_bps", "mean"),
        htb_ratio=("hard_to_borrow_flag", "mean"),
    ).reset_index()

    # normalise each component ACROSS sectors before weighting
    agg["n_util"] = _minmax(agg["avg_utilization"])
    agg["n_fee"] = _minmax(agg["avg_fee_bps"])
    agg["n_htb"] = _minmax(agg["htb_ratio"])

    w = C.SECTOR_WEIGHTS
    # 0-100 scale must match sql/views.sql::v_sector_pressure.
    agg["sector_pressure_score"] = (
        100.0
        * (
            w["utilization"] * agg["n_util"]
            + w["fee"] * agg["n_fee"]
            + w["htb_ratio"] * agg["n_htb"]
        )
    )
    agg["date"] = on_date
    return agg.sort_values("sector_pressure_score", ascending=False).reset_index(drop=True)


# ----------------------------------------------------------------------------
# Hard-to-borrow diagnostics: publish the REAL numbers behind the "distinct,
# not independent" framing -- the pairwise correlations of the three axes and
# the firing rate of each axis (share of rows where its condition is true), on
# the full panel and on the latest snapshot. run_pipeline calls this so the
# figures print on every run; they change if config.py changes.
# ----------------------------------------------------------------------------
def htb_diagnostics(df: pd.DataFrame) -> dict:
    axis_cols = ["utilization_pct", "borrow_fee_bps", "days_to_cover_proxy"]
    corr = df[axis_cols].corr()

    def _firing(frame: pd.DataFrame) -> dict:
        return {
            f"A  util >= {C.HTB_UTIL_PCT:.0f}%":   float((frame["utilization_pct"] >= C.HTB_UTIL_PCT).mean()),
            f"B  fee  >= {C.HTB_FEE_BPS:.0f} bps": float((frame["borrow_fee_bps"] >= C.HTB_FEE_BPS).mean()),
            f"C  dtc  >= {C.HTB_DTC:.1f}":         float((frame["days_to_cover_proxy"] >= C.HTB_DTC).mean()),
        }

    latest_date = df["date"].max()
    panel_firing = _firing(df)
    latest_firing = _firing(df[df["date"] == latest_date])

    print("\nHTB axis correlations (full panel) -- distinct measurements, "
          "expected to co-move, not orthogonal:")
    print(corr.round(3).to_string())
    print("\nHTB axis firing rates (share of rows where the condition is true):")
    print(f"  {'axis':20s}{'full panel':>12s}{'latest snap':>14s}")
    for key in panel_firing:
        print(f"  {key:20s}{panel_firing[key]:>12.3f}{latest_firing[key]:>14.3f}")

    return {
        "correlations": corr,
        "firing_panel": panel_firing,
        "firing_latest": latest_firing,
        "latest_date": latest_date,
    }


if __name__ == "__main__":
    clean = pd.read_csv(C.CLEAN_PATH)
    metrics = compute_metrics(clean)
    metrics.to_csv(C.METRICS_PATH, index=False)

    sect = sector_pressure(metrics)
    sect.to_csv(C.SECTOR_PATH, index=False)

    latest = metrics[metrics["date"] == metrics["date"].max()]
    print(f"Metrics -> {C.METRICS_PATH} ({len(metrics):,} rows)")
    print(f"Latest date {metrics['date'].max()}: "
          f"{int(latest['hard_to_borrow_flag'].sum())} hard-to-borrow names")
    print("\nTop sectors by pressure:")
    print(sect[["sector", "sector_pressure_score"]].head(3).to_string(index=False))

    htb_diagnostics(metrics)
