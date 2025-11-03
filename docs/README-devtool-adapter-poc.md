# Zecbook PoC — Devtool Adapter → Supabase → Frontend

This write‑up documents a minimal, repeatable loop to send a small memoed Zcash transfer from the local devtool wallet to a target UA, ingest it via the HTTP adapter, persist it in Supabase, and display it in the frontend.

## Overview
- Trigger a memoed send from the devtool wallet to your board/admin UA.
- Use the adapter to scan the wallet and persist matching records into Supabase `public.zecbook` (PoC uses `memos_only`).
- The frontend fetches `zecbook` rows and shows memo text, amount, timestamp, and `txid`.

## Components
- `zcash-devtool` wallet + CLI (`cargo run --release --bin zcash-devtool`).
- `devtool_adapter.py`: HTTP bridge exposing `/send`, `/scan`, `/list-all`, `/import-ufvk`, `/sync`.
- Supabase (REST): table `zecbook` in schema `public` (PoC) or `zda`.
- React + Vite frontend under `src/`, reads from Supabase and can trigger adapter `/scan`.

## Environment
Set these env vars (paths match the adapter defaults; adjust if needed):
- `DEVTOOL_HOME=/Users/haoxiang/Downloads/EDA-CLINICAL-Projects/Wallet/zcash-devtool`
- `DEVTOOL_WALLET_DIR=/Users/haoxiang/Downloads/EDA-CLINICAL-Projects/Wallet/main-wallet`
- `DEVTOOL_IDENTITY_FILE=/Users/haoxiang/Downloads/EDA-CLINICAL-Projects/Wallet/main-wallet/main-key.txt`
- `DEVTOOL_LIGHTWALLETD=zecrocks`
- `DEVTOOL_ACCOUNT_ID=93799f13-6d86-4cb0-b42d-0e51b3332f06` (source wallet)
- `SUPABASE_URL=...` (your project URL)
- `SUPABASE_SERVICE_ROLE_KEY=...` (service role for server‑side writes)
- `SUPABASE_SCHEMA=public` (PoC) or `zda`
- `DEVTOOL_ADAPTER_HOST=127.0.0.1`
- `DEVTOOL_ADAPTER_PORT=9014` (or `9012/9013` if desired)
- `DEVTOOL_PERSIST_MODE=memos_only` (PoC default)

Start the adapter:
- `source .venv/bin/activate && env $(cat .env | grep -v '^#' | xargs) SUPABASE_SCHEMA=public DEVTOOL_ADAPTER_PORT=9014 python3 devtool_adapter.py`
- Base URL: `http://127.0.0.1:9014/`

## Wallet Context
- Source account UUID: `93799f13-6d86-4cb0-b42d-0e51b3332f06`
- Source UA (example): `u1gz4l...` (full in prior summary)
- Balance example: `0.02189900 ZEC`

Helper commands:
- List accounts: 
  - `cargo run --release --bin zcash-devtool -- wallet -w /Users/haoxiang/Downloads/EDA-CLINICAL-Projects/Wallet/main-wallet list-accounts`
- List addresses for account:
  - `cargo run --release --bin zcash-devtool -- wallet -w /Users/haoxiang/Downloads/EDA-CLINICAL-Projects/Wallet/main-wallet list-addresses 93799f13-6d86-4cb0-b42d-0e51b3332f06`
- Check balance:
  - `cargo run --release --bin zcash-devtool -- wallet -w /Users/haoxiang/Downloads/EDA-CLINICAL-Projects/Wallet/main-wallet balance 93799f13-6d86-4cb0-b42d-0e51b3332f06`
- Sync & enhance:
  - `cargo run --release --bin zcash-devtool -- wallet -w /Users/haoxiang/Downloads/EDA-CLINICAL-Projects/Wallet/main-wallet sync -s zecrocks`
  - `cargo run --release --bin zcash-devtool -- wallet -w /Users/haoxiang/Downloads/EDA-CLINICAL-Projects/Wallet/main-wallet enhance`

## Send Zcash with Memo
Target UA (example):
- `u1qzt502u9fwh67s7an0e202c35mm0h534jaa648t4p2r6mhf30guxjjqwlkmvthahnz5myz2ev7neff5pmveh54xszv9njcmu5g2eent82ucpd3lwyzkmyrn6rytwsqefk475hl5tl4tu8yehc0z8w9fcf4zg6r03sq7lldx0uxph7c0lclnlc4qjwhu2v52dkvuntxr8tmpug3jntvm`

Option A — CLI (amount in zats):
- `cargo run --release --bin zcash-devtool -- wallet -w /Users/haoxiang/Downloads/EDA-CLINICAL-Projects/Wallet/main-wallet send -i /Users/haoxiang/Downloads/EDA-CLINICAL-Projects/Wallet/main-wallet/main-key.txt --address <RECEIVER_UA> --value 100 --memo "PoC: hello from devtool" -s zecrocks 93799f13-6d86-4cb0-b42d-0e51b3332f06`
  - `100` zats = `0.000001` ZEC (good for PoC).

Option B — HTTP Adapter (amount in ZEC):
- `curl -s -X POST http://127.0.0.1:9014/send -H "Content-Type: application/json" -d '{"to":"<RECEIVER_UA>","amount":0.000001,"memo":"PoC: hello from devtool"}'`
- Hex memo variant: 
  - `curl -s -X POST http://127.0.0.1:9014/send -H "Content-Type: application/json" -d '{"to":"<RECEIVER_UA>","amount":0.000001,"memo":"506f433a2068656c6c6f2066726f6d20646576746f6f6c"}'`
- Adapter response: `{"ok": true, "txid": "...", "stdout": "..."}`

Memo decoding:
- Adapter tries hex first; if not valid hex, treats memo as UTF‑8 text.
- Amount is converted from ZEC to zats internally.

## Persist to Supabase
Persist recent memos to Supabase (recommended for PoC):
- `curl -s "http://127.0.0.1:9014/scan?addr=<RECEIVER_UA>&since=600&min=0&persist_mode=memos_only"`
  - `persist_mode=memos_only`: only records with memo are inserted, matches current unique keys.
  - Returns `{ ok, memos, persisted, persist_mode }`.

Bulk list & persist (optional):
- `curl -s "http://127.0.0.1:9014/list-all?persist=1&persist_mode=memos_only&min=0"`

Supabase REST check:
- `curl -s -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" "$SUPABASE_URL/rest/v1/zecbook?select=txid,ts,amount,memo_text,to_address&order=ts.desc"`

Modes:
- `memos_only`: uses conflict keys `txid,memo_hex`.
- `all`: requires DB constraint `UNIQUE(txid, to_address, memo_hex)` (add before use).

## Frontend
Configure env for local dev:
- `VITE_DEVTOOL_API_BASE=http://127.0.0.1:9014`
- `VITE_SCAN_ADDR=<RECEIVER_UA>`

Run the app:
- `npm install`
- `npm run dev`
- The component `src/LatestMessages.jsx` can trigger `/scan` and then reads `zecbook` to show latest memos.

## Logs & Diagnostics
- Adapter `POST /send` responds with `txid` and partial stdout for traceability.
- `logs/audit.log`: Bob CLI audit (if used), useful for demo OTP flows.
- `sessions.json`: Bob CLI session state (not required for the devtool persistence path).
- Wallet CLI:
  - `cargo run --release --bin zcash-devtool -- wallet -w ... list-tx 93799f13-6d86-4cb0-b42d-0e51b3332f06`

## Timings
- Chain confirmation: typically 1–3 minutes.
- Adapter scan + Supabase upsert: seconds to tens of seconds.
- Frontend display: near‑real‑time after rows appear.

## Troubleshooting
- Adapter `/send` returns `bad_amount`: ensure `amount` is numeric (ZEC) or use CLI with zats.
- Supabase insert fails: check `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`; confirm schema/table (`public.zecbook`).
- No rows visible: run `/scan` or `/list-all?persist=1` with `min=0` and correct `addr`.
- Switching to `persist_mode=all`: add `UNIQUE(txid, to_address, memo_hex)` to your `public.zecbook` first.

## Example End‑to‑End (PoC)
1) Send (adapter):
   - `curl -s -X POST http://127.0.0.1:9014/send -H "Content-Type: application/json" -d '{"to":"<RECEIVER_UA>","amount":0.000001,"memo":"PoC test via adapter"}'`
2) Scan & persist:
   - `curl -s "http://127.0.0.1:9014/scan?addr=<RECEIVER_UA>&since=600&min=0&persist_mode=memos_only"`
3) Verify Supabase:
   - `curl -s -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" "$SUPABASE_URL/rest/v1/zecbook?select=txid,ts,amount,memo_text,to_address&order=ts.desc"`
4) Frontend shows the message (memo text, amount, time, `txid`).

## Notes
- For demos, prefer very small amounts (e.g., `0.000001 ZEC`).
- `decode_memo` allows either hex or text; text is easiest for PoC.
- Avoid sensitive content in memos for production.