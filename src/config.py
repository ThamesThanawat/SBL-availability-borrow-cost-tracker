"""
Central configuration for the SBL Availability & Borrow Cost Tracker.

Everything tunable lives here so the rest of the code stays declarative.
All borrow / lending data produced by this project is SIMULATED. See README.
"""

from __future__ import annotations

# ----------------------------------------------------------------------------
# Reproducibility & horizon
# ----------------------------------------------------------------------------
SEED = 42
START_DATE = "2026-01-01"   # first trading date (mock)
END_DATE = "2026-06-30"     # last trading date (mock)

# ----------------------------------------------------------------------------
# Universe: real SET ticker names, but ALL borrow data below is simulated.
# 4 names per sector, 10 sectors.
# ----------------------------------------------------------------------------
UNIVERSE: dict[str, list[str]] = {
    "Banking":         ["KBANK", "SCB", "BBL", "KTB"],
    "Energy":          ["PTT", "PTTEP", "GULF", "GPSC"],
    "Commerce":        ["CPALL", "HMPRO", "CRC", "BJC"],
    "ICT":             ["ADVANC", "TRUE", "INTUCH", "JMART"],
    "Healthcare":      ["BDMS", "BH", "BCH", "CHG"],
    "Property":        ["LH", "AP", "SPALI", "ORI"],
    "Transportation":  ["AOT", "BEM", "BTS", "THAI"],
    "Food & Beverage": ["CPF", "TU", "OSP", "CBG"],
    "Finance":         ["MTC", "SAWAD", "TIDLOR", "KTC"],
    "Industrials":     ["SCC", "SCGP", "TASCO", "STGT"],
}

# ----------------------------------------------------------------------------
# Data-generating process (see PRD v2 section 7.4)
# ----------------------------------------------------------------------------
# Utilization: AR(1) mean reversion on the LOGIT scale so it stays in (0,1).
UTIL_KAPPA = 0.15           # speed of mean reversion
UTIL_SIGMA = 0.35           # idiosyncratic shock size (logit space)
UTIL_MU_BETA = (2.0, 3.0)   # Beta(a,b) for per-symbol baseline utilization
SECTOR_FACTOR_SIGMA = 0.20  # shared sector shock size (logit space)
SECTOR_FACTOR_LOAD = 0.6    # how strongly a name loads on its sector factor

# Lendable pool: slow random walk (inventory drifting in/out of the pool).
POOL_BASE = (5e6, 8e7)      # per-symbol base lendable shares, log-uniform range
POOL_DRIFT_SIGMA = 0.01     # daily lognormal drift of the pool

# Borrow fee (bps, annualized): mean-reverting, COUPLED to utilization, + jumps.
FEE_BASE = (30.0, 120.0)    # per-symbol structural fee range (GC-ish), scaled by hardness
FEE_KAPPA = 0.20            # mean reversion speed
FEE_SIGMA = 15.0            # daily fee noise (bps)
FEE_UTIL_LAMBDA = 900.0     # coupling: fee target rises when util is above its baseline
FEE_JUMP_PROB = 0.02        # daily prob of a "goes special" jump
FEE_JUMP_SIZE = (150.0, 500.0)  # jump magnitude range (bps)
FEE_FLOOR = 15.0            # minimum borrow fee (bps)

# Lender economics: lender receives fee minus the intermediary's cut.
INTERMEDIARY_SHARE = (0.20, 0.40)  # per-symbol share kept by the agent lender

# Collateral requirement (% of borrowed value), stable per symbol + tiny noise.
COLLATERAL_PCT = (105.0, 150.0)

# Price & liquidity
PRICE_START = (5.0, 400.0)  # per-symbol starting close price (THB)
PRICE_VOL = 0.02            # daily lognormal price vol
ADV_BASE = (6.5e7, 5e9)     # per-symbol average daily traded value (THB), log-uniform
ADV_SIGMA = 0.25            # daily lognormal noise on ADV

# Data-quality injection (so the cleaning step has real work to do)
DQ_MISSING_FEE_RATE = 0.006
DQ_NEGATIVE_QTY_RATE = 0.004
DQ_DUPLICATE_RATE = 0.004

# ----------------------------------------------------------------------------
# Metric thresholds (see PRD v2 section 8)
# ----------------------------------------------------------------------------
# Hard-to-borrow: three INDEPENDENT axes; flag if >= 2 are true.
HTB_UTIL_PCT = 85.0         # Axis A: supply tightness (utilization %)
HTB_FEE_BPS = 300.0         # Axis B: cost
HTB_DTC = 2.0               # Axis C: crowding (days-to-cover proxy)

# Momentum escalators (do NOT count toward 2-of-3; add colour / watchlist)
ESC_AVAIL_DROP_PCT = -15.0  # daily availability change <= -15%
ESC_FEE_JUMP_BPS = 100.0    # daily fee change >= +100 bps

# Sector pressure weights (must sum to 1.0)
SECTOR_WEIGHTS = {"utilization": 1 / 3, "fee": 1 / 3, "htb_ratio": 1 / 3}

# ----------------------------------------------------------------------------
# Paths
# ----------------------------------------------------------------------------
RAW_PATH = "data/raw/mock_sbl_raw.csv"
CLEAN_PATH = "data/processed/sbl_cleaned.csv"
METRICS_PATH = "data/processed/sbl_analytics.csv"
SECTOR_PATH = "data/processed/sbl_sector_pressure.csv"
MEMO_PATH = "reports/sbl_sales_trading_memo.md"
DUCKDB_PATH = "data/processed/sbl_analytics.duckdb"
