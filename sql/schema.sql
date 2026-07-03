-- PRD v2 section 12 -- PostgreSQL schema
CREATE TABLE sbl_daily_metrics (
  date                        DATE        NOT NULL,
  symbol                      VARCHAR(16) NOT NULL,
  sector                      VARCHAR(32) NOT NULL,
  available_borrow_qty        BIGINT,
  total_lendable_qty          BIGINT,
  borrowed_qty                BIGINT,
  utilization_pct             DOUBLE PRECISION,
  borrow_fee_bps              DOUBLE PRECISION,
  lending_rate_pct            DOUBLE PRECISION,
  lending_rate_bps            DOUBLE PRECISION,
  intermediary_spread_bps     DOUBLE PRECISION,
  days_to_cover_proxy         DOUBLE PRECISION,
  collateral_requirement_pct  DOUBLE PRECISION,
  close_price                 DOUBLE PRECISION,
  avg_daily_value             DOUBLE PRECISION,
  available_borrow_value      DOUBLE PRECISION,
  borrowed_value              DOUBLE PRECISION,
  daily_available_change_pct  DOUBLE PRECISION,
  daily_fee_change_bps        DOUBLE PRECISION,
  hard_to_borrow_flag         BOOLEAN,
  hard_to_borrow_reason       TEXT,
  data_quality_note           TEXT,
  PRIMARY KEY (date, symbol)
);
CREATE INDEX idx_sbl_date   ON sbl_daily_metrics (date);
CREATE INDEX idx_sbl_sector ON sbl_daily_metrics (sector);
