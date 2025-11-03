-- Migration: widen unique constraint to include to_address
-- NOTE: Keep memo_hex as NOT NULL to satisfy existing schema; adapter will
-- persist non‑memo outputs with empty string ("") memo_hex in persist_mode=all.

-- Drop previous unique constraint (if present)
ALTER TABLE zda.zecbook
  DROP CONSTRAINT IF EXISTS zecbook_txid_memo_hex_unique;

-- New unique constraint to match adapter upsert on_conflict
ALTER TABLE zda.zecbook
  ADD CONSTRAINT zecbook_txid_to_addr_memo_unique UNIQUE (txid, to_address, memo_hex);