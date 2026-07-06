"""
memo_generator.py  --  PRD v2 section 10 / dashboard page 4

Turns the latest snapshot into a short, plain-English desk memo.
All figures are derived from the simulated dataset.
"""

from __future__ import annotations

import pandas as pd

import config as C
from metrics import sector_pressure


def build_memo(metrics: pd.DataFrame) -> str:
    latest_date = metrics["date"].max()
    snap = metrics[metrics["date"] == latest_date].copy()

    declining = int((snap["daily_available_change_pct"] <= C.ESC_AVAIL_DROP_PCT).sum())
    n_htb = int(snap["hard_to_borrow_flag"].sum())

    sect = sector_pressure(metrics, latest_date)
    top_sector = sect.iloc[0]["sector"]

    htb = snap[snap["hard_to_borrow_flag"]]
    if len(htb):
        top_name = htb.sort_values("utilization_pct", ascending=False).iloc[0]
        top_name_txt = (
            f"{top_name['symbol']} ({top_name['sector']}) — "
            f"{top_name['hard_to_borrow_reason']}"
        )
    else:
        top_name_txt = "none flagged today"

    fee_move = snap.sort_values("daily_fee_change_bps", ascending=False).iloc[0]
    avail_move = snap.sort_values("daily_available_change_pct").iloc[0]

    lines = [
        f"# SBL Sales-Trading Memo — {pd.to_datetime(latest_date).date()}",
        "",
        "*Simulated data for portfolio demonstration only. Not real broker, "
        "exchange, custodian, or client data.*",
        "",
        "## Market summary",
        f"- Borrow availability declined sharply (≤ {C.ESC_AVAIL_DROP_PCT:.0f}%) "
        f"for **{declining}** name(s) today.",
        f"- **{n_htb}** name(s) currently flagged hard-to-borrow "
        f"(≥ 2 of: utilization ≥ {C.HTB_UTIL_PCT:.0f}%, fee ≥ {C.HTB_FEE_BPS:.0f} bps, "
        f"days-to-cover ≥ {C.HTB_DTC:.1f}).",
        f"- Highest sector borrow pressure: **{top_sector}**.",
        "",
        "## Names to watch",
        f"- Top hard-to-borrow name: **{top_name_txt}**.",
        f"- Largest borrow-fee increase: **{fee_move['symbol']}** "
        f"({fee_move['daily_fee_change_bps']:+.0f} bps).",
        f"- Largest availability decline: **{avail_move['symbol']}** "
        f"({avail_move['daily_available_change_pct']:+.0f}%).",
        "",
        "## Execution implication",
        "- Check borrow availability and cost before discussing short exposure "
        "or structured trades on the flagged names.",
        "- Short-sale execution implications apply only to short-eligible names; "
        "flagged names that are not short-eligible are informational only.",
        "- Names with tightening availability or spiking fees may require "
        "pre-locate discussion ahead of short-sale execution.",
    ]
    return "\n".join(lines)


def write_memo(path: str, memo: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(memo)


if __name__ == "__main__":
    metrics = pd.read_csv(C.METRICS_PATH)
    memo = build_memo(metrics)
    write_memo(C.MEMO_PATH, memo)
    print(f"Wrote memo -> {C.MEMO_PATH}\n")
    print(memo)
