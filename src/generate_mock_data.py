"""
generate_mock_data.py  --  PRD v2 section 7.4

Generates a PANEL (one row per symbol per business day) of SIMULATED SBL data.
Series are persistent (autocorrelated), not redrawn each day, so that the
daily-change metrics and hard-to-borrow clustering downstream are meaningful.

Key modelling choices:
  * utilization  : AR(1) mean reversion on the logit scale + a shared SECTOR
                   factor, so names in a stressed sector tighten together.
  * pool         : slow lognormal random walk (inventory drift).
  * quantities   : DERIVED from utilization & pool so the identity
                   total_lendable = borrowed + available always holds.
  * borrow fee   : mean-reverting AND coupled to utilization (tight supply ->
                   dearer borrow) with occasional "goes special" jumps.
  * lending rate : borrow fee minus the intermediary's cut.
  * price / ADV  : geometric random walks.
Finally we inject a small amount of dirty data so the cleaning step is real.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import config as C


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def _logit(p: float) -> float:
    p = min(max(p, 1e-4), 1 - 1e-4)
    return float(np.log(p / (1 - p)))


def _loguniform(rng, lo, hi, size=None):
    return np.exp(rng.uniform(np.log(lo), np.log(hi), size=size))


def generate() -> pd.DataFrame:
    rng = np.random.default_rng(C.SEED)

    symbols = [(s, sec) for sec, names in C.UNIVERSE.items() for s in names]
    sectors = list(C.UNIVERSE.keys())
    dates = pd.bdate_range(C.START_DATE, periods=C.N_DAYS)

    # --- per-symbol structural parameters -----------------------------------
    params = {}
    for sym, sec in symbols:
        hardness = rng.beta(*C.UTIL_MU_BETA)          # 0..1, higher = tighter name
        params[sym] = dict(
            sector=sec,
            mu=hardness,                               # baseline utilization
            base_fee=C.FEE_BASE[0] + hardness * (C.FEE_BASE[1] - C.FEE_BASE[0]),
            pool=float(_loguniform(rng, *C.POOL_BASE)),
            interm=rng.uniform(*C.INTERMEDIARY_SHARE),
            collat=rng.uniform(*C.COLLATERAL_PCT),
            price=float(_loguniform(rng, *C.PRICE_START)),
            adv=float(_loguniform(rng, *C.ADV_BASE)),
        )

    # --- shared sector factor path (logit space) ----------------------------
    sector_factor = {sec: 0.0 for sec in sectors}

    # --- initialise state at each symbol's baseline -------------------------
    state = {}
    for sym, sec in symbols:
        p = params[sym]
        state[sym] = dict(
            x=_logit(p["mu"]),                         # utilization (logit)
            fee=p["base_fee"],
            pool=p["pool"],
            price=p["price"],
        )

    rows = []
    for d in dates:
        # advance the sector factors (their own AR(1)-ish shocks)
        for sec in sectors:
            sector_factor[sec] = (
                0.7 * sector_factor[sec]
                + rng.normal(0.0, C.SECTOR_FACTOR_SIGMA)
            )

        for sym, sec in symbols:
            p, st = params[sym], state[sym]
            mu_logit = _logit(p["mu"])

            # utilization: mean-revert to baseline + load on sector factor + noise
            st["x"] += (
                C.UTIL_KAPPA * (mu_logit - st["x"])
                + C.SECTOR_FACTOR_LOAD * sector_factor[sec]
                + rng.normal(0.0, C.UTIL_SIGMA)
            )
            util = float(_sigmoid(st["x"]))            # 0..1

            # pool drifts slowly
            st["pool"] *= float(np.exp(rng.normal(0.0, C.POOL_DRIFT_SIGMA)))
            total_lendable = int(round(st["pool"]))
            borrowed = int(round(util * total_lendable))
            available = total_lendable - borrowed       # identity holds by construction

            # fee: target coupled to utilization gap, mean-revert, + rare jump
            theta = p["base_fee"] + C.FEE_UTIL_LAMBDA * (util - p["mu"])
            jump = 0.0
            if rng.random() < C.FEE_JUMP_PROB:
                jump = rng.uniform(*C.FEE_JUMP_SIZE)
            st["fee"] += (
                C.FEE_KAPPA * (theta - st["fee"])
                + rng.normal(0.0, C.FEE_SIGMA)
                + jump
            )
            st["fee"] = max(st["fee"], C.FEE_FLOOR)
            fee_bps = round(st["fee"], 1)

            lending_rate_pct = round(fee_bps * (1 - p["interm"]) / 100.0, 4)

            # price / liquidity random walks
            st["price"] *= float(np.exp(rng.normal(0.0, C.PRICE_VOL)))
            close_price = round(st["price"], 2)
            adv = round(p["adv"] * float(np.exp(rng.normal(0.0, C.ADV_SIGMA))), 0)

            rows.append(dict(
                date=d.date(),
                symbol=sym,
                sector=sec,
                available_borrow_qty=available,
                total_lendable_qty=total_lendable,
                borrowed_qty=borrowed,
                borrow_fee_bps=fee_bps,
                lending_rate_pct=lending_rate_pct,
                collateral_requirement_pct=round(p["collat"], 1),
                close_price=close_price,
                avg_daily_value=adv,
                data_quality_note="clean",
            ))

    df = pd.DataFrame(rows)
    df = _inject_dirty(df, rng)
    return df


def _inject_dirty(df: pd.DataFrame, rng) -> pd.DataFrame:
    """Deliberately corrupt a few rows so the cleaning step is real."""
    n = len(df)

    miss = rng.random(n) < C.DQ_MISSING_FEE_RATE
    df.loc[miss, "borrow_fee_bps"] = np.nan
    df.loc[miss, "lending_rate_pct"] = np.nan  # keep fee & rate consistent
    df.loc[miss, "data_quality_note"] = "missing_fee"

    neg = rng.random(n) < C.DQ_NEGATIVE_QTY_RATE
    df.loc[neg, "available_borrow_qty"] = -1 * df.loc[neg, "available_borrow_qty"].abs()
    df.loc[neg, "data_quality_note"] = "negative_qty"

    dup_idx = df.index[rng.random(n) < C.DQ_DUPLICATE_RATE]
    dupes = df.loc[dup_idx].copy()
    dupes["data_quality_note"] = "duplicate"
    df = pd.concat([df, dupes], ignore_index=True)

    return df


if __name__ == "__main__":
    out = generate()
    out.to_csv(C.RAW_PATH, index=False)
    print(f"Wrote {len(out):,} raw rows -> {C.RAW_PATH}")
    print(out["data_quality_note"].value_counts().to_string())
