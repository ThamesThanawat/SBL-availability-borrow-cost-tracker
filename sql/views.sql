-- Views that Power BI reads (keeps DAX simple; logic lives in SQL)
CREATE OR REPLACE VIEW v_latest_snapshot AS
SELECT * FROM sbl_daily_metrics
WHERE date = (SELECT MAX(date) FROM sbl_daily_metrics);

CREATE OR REPLACE VIEW v_sector_pressure_inputs AS
SELECT sector,
       AVG(utilization_pct)                                   AS avg_utilization,
       AVG(borrow_fee_bps)                                    AS avg_fee_bps,
       AVG(CASE WHEN hard_to_borrow_flag THEN 1.0 ELSE 0 END) AS htb_ratio
FROM v_latest_snapshot
GROUP BY sector;

CREATE OR REPLACE VIEW v_sector_pressure AS
WITH agg AS (
  SELECT sector,
         AVG(utilization_pct)                                   AS avg_utilization,
         AVG(borrow_fee_bps)                                    AS avg_fee_bps,
         AVG(CASE WHEN hard_to_borrow_flag THEN 1.0 ELSE 0 END) AS htb_ratio
  FROM v_latest_snapshot
  GROUP BY sector
),
norm AS (
  SELECT sector, avg_utilization, avg_fee_bps, htb_ratio,
         (avg_utilization - MIN(avg_utilization) OVER ())
           / NULLIF(MAX(avg_utilization) OVER () - MIN(avg_utilization) OVER (), 0) AS n_util,
         (avg_fee_bps - MIN(avg_fee_bps) OVER ())
           / NULLIF(MAX(avg_fee_bps) OVER () - MIN(avg_fee_bps) OVER (), 0)          AS n_fee,
         (htb_ratio - MIN(htb_ratio) OVER ())
           / NULLIF(MAX(htb_ratio) OVER () - MIN(htb_ratio) OVER (), 0)              AS n_htb
  FROM agg
)
SELECT sector, avg_utilization, avg_fee_bps, htb_ratio,
       -- weights below MUST match config.SECTOR_WEIGHTS
       100.0 * ( (1.0/3.0) * COALESCE(n_util, 0)
               + (1.0/3.0) * COALESCE(n_fee, 0)
               + (1.0/3.0) * COALESCE(n_htb, 0) ) AS sector_pressure_score
FROM norm
ORDER BY sector_pressure_score DESC;

CREATE OR REPLACE VIEW v_hard_to_borrow AS
SELECT date, symbol, sector, available_borrow_qty, borrow_fee_bps,
       utilization_pct, days_to_cover_proxy,
       daily_available_change_pct, daily_fee_change_bps, hard_to_borrow_reason
FROM v_latest_snapshot
WHERE hard_to_borrow_flag = TRUE
ORDER BY utilization_pct DESC;
