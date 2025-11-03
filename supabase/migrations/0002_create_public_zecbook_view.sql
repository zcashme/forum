-- Migration: expose ZDA.Zecbook via public view (Postgres)

CREATE VIEW "public"."zecbook" AS
SELECT
  id,
  txid,
  ts,
  amount,
  memo_hex,
  memo_text,
  to_address,
  source,
  ingested_at,
  height
FROM "zda"."zecbook";