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

CREATE OR REPLACE VIEW v_hard_to_borrow AS
SELECT date, symbol, sector, available_borrow_qty, borrow_fee_bps,
       utilization_pct, days_to_cover_proxy,
       daily_available_change_pct, daily_fee_change_bps, hard_to_borrow_reason
FROM v_latest_snapshot
WHERE hard_to_borrow_flag = TRUE
ORDER BY utilization_pct DESC;
