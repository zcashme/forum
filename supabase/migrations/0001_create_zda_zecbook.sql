-- Migration: create ZDA.Zecbook table (Postgres)

CREATE TABLE zda.zecbook (
  id BIGSERIAL PRIMARY KEY,
  txid TEXT NOT NULL,
  ts timestamptz NOT NULL,
  amount numeric NOT NULL DEFAULT 0,
  memo_hex TEXT NOT NULL,
  memo_text TEXT,
  to_address TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT 'devtool',
  ingested_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  height integer,
  CONSTRAINT zecbook_txid_memo_hex_unique UNIQUE (txid, memo_hex)
);