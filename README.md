# ZcashMe PoC — Bob CLI + Frontend OTP Sign‑In

A proof‑of‑concept that demonstrates authenticating a Zcash user by sending a one‑time code (OTP) over shielded memos and issuing a short‑lived browser session. It includes:

- A single‑file Python CLI (`bob-cli.py`) that exposes a minimal HTTP API.
- A React + Vite frontend that drives the flow and shows a wallet‑ready ZIP‑321 URI.
- Optional integration points for a local "zcash‑devtool" RPC to send/scan shielded memos.

> This PoC proves control of a Zcash address, not real‑world identity.

---

## Contents

- Overview
- Requirements
- Quick Start (Backend + Frontend)
- End‑to‑End Flow with Alice’s mobile wallet
- zcash‑devtool (optional) startup and wiring
- Admin & Logs
- HTTP API Reference
- Troubleshooting

---

## Overview

- The frontend (Vite) triggers a **claim** to Bob and generates a ZIP‑321 link for the user’s wallet.
- Bob creates a session, generates an OTP, and (optionally via devtool RPC) sends an OTP memo to Alice’s address.
- Alice reads codewords (OTP) and submits them; Bob verifies and sets a short‑lived JWT cookie.
- The frontend calls `/me` to confirm the authenticated address, and toggles its UI (e.g., profile editing) accordingly.

---

## Requirements

- macOS or Linux
- Python 3.10+ (with `venv`)
- Node.js 18+ and npm
- A shielded‑memo capable mobile wallet (e.g., Zashi, YWallet, Zingo)
- Optional: local `zcash‑devtool` RPC for real memo send/scan

---

## Quick Start

### 1) Backend (Bob HTTP API)

Create a virtualenv, install Flask, export environment variables, then start Bob:

```bash
cd zcashme
python3 -m venv .venv
source .venv/bin/activate
python -m pip install Flask

# Secrets and runtime config (examples; change in real usage)
export ADMIN_ADDRESS="u1YOUR_BOB_ADDRESS"                 # Bob’s inbound address (for claim memos)
export JWT_SECRET="change-this-secret"                    # JWT signing key
export SERVER_HMAC_SECRET="change-this-hmac-secret"       # OTP MAC key
export MIN_SIGNIN_AMOUNT="0.0005"                         # Wallet ask; adjustable

# CORS: must match your Vite dev URL printed by `npm run dev`
export FRONTEND_ORIGIN="http://localhost:5175"

# Dev only: log OTP plaintext to audit log
export LOG_OTP_CODE=1

python bob-cli.py serve
# -> http://127.0.0.1:8000
```

### 2) Frontend (Vite)

```bash
npm install
npm run dev
# Note the port Vite selects (5173/5174/5175). If not 5175, set FRONTEND_ORIGIN accordingly and restart Bob.
```

Open the printed URL (e.g., `http://localhost:5175/`).

---

## End‑to‑End Flow (Alice Mobile Wallet)

1. In the frontend, go to the **Sign‑In** UI.
2. Enter your Zcash address (shielded preferred) and click **Open in Wallet**.
   - The app will generate a ZIP‑321 payment URI and open your wallet.
   - The memo says: “ZM! Sign‑in code request for <YOUR_ADDRESS>”.
   - A minimal amount is shown (default `MIN_SIGNIN_AMOUNT`).
3. In parallel, the frontend calls Bob’s `POST /claim` which creates a **session** and an **OTP**, then sends the OTP memo to your address (via RPC when available; stubbed otherwise).
4. Retrieve the OTP codewords from your wallet, return to the app, and click **Verify Code ➤**.
   - The app sends `POST /verify-code { address, code, session }`.
   - On success, Bob sets an HttpOnly `session` cookie; the app calls `GET /me` and shows your authenticated address.

> Note: Without a real RPC, memo sending is stubbed. For demos, enable `LOG_OTP_CODE=1` so the OTP appears in audit logs.

---

## zcash‑devtool (Optional)

To enable real shielded memo operations from Bob:

```bash
# Example only — replace with your actual devtool binary and flags
zcash-devtool start \
  --rpc-bind 127.0.0.1:9000 \
  --wallet bob-wallet \
  --allow-memo-send --allow-memo-scan

# Point Bob to the RPC
export DEVTOOL_RPC_URL="http://127.0.0.1:9000"
```

- Bob’s `DevtoolRPCClient` uses:
  - `POST /send` — `{ to, amount, memo }` → returns `{ txid }` (example semantics)
  - `GET /scan` — `?addr=<ADMIN_ADDRESS>&since=<seconds>` → returns `{ memos: [...] }`
- If `DEVTOOL_RPC_URL` is not set, memo send/scan are stubbed.

---

## Admin & Logs

- Sessions are persisted in `sessions.json` (project root).
- Audit logs are appended to `logs/audit.log` (JSONL).

Common checks:

```bash
# View recent audit lines
tail -n 50 logs/audit.log
# Filter key events
grep -E 'otp_sent|otp_code_dev|verified' logs/audit.log

# List current sessions
python bob-cli.py list-sessions
cat sessions.json
```

Sample events (dev mode):

```json
{"ts":"2025-10-24T10:12:31Z","event":"otp_sent","session_id":"H9KJY...","addr":"u1alice...","txid":"stub-txid-..."}
{"ts":"2025-10-24T10:13:10Z","event":"otp_code_dev","session_id":"H9KJY...","addr":"u1alice...","code":"HVNW6A1F1MM9ABTP1VS0J5HD5W"}
{"ts":"2025-10-24T10:13:11Z","event":"verified","session_id":"H9KJY...","addr":"u1alice..."}
```

> Security: In production, do not set `LOG_OTP_CODE=1`. OTP plaintext must never be logged.

---

## HTTP API Reference

- `POST /claim`
  - Body: `{ "address": "u1alice..." }`
  - Response: `{ "ok": true, "session": "<id>", "expiry": "<ISO>" }`

- `POST /verify-code`
  - Body: `{ "address": "u1alice...", "code": "<OTP>", "session": "<id>" }`
  - Response: `{ "ok": true }` and sets `session` cookie (HttpOnly)

- `GET /me`
  - Response: `{ "address": "u1alice..." }` when authenticated; `401` otherwise

- `POST /logout`
  - Clears the `session` cookie

Curl examples:

```bash
# Claim
curl -s -X POST http://127.0.0.1:8000/claim \
  -H 'Content-Type: application/json' \
  -d '{"address":"u1demoaliceaddress..."}'

# Verify (replace placeholders)
curl -i -s -X POST http://127.0.0.1:8000/verify-code \
  -H 'Content-Type: application/json' \
  -d '{"address":"u1demoaliceaddress...","code":"<OTP>","session":"<SESSION>"}'

# Me (with cookie)
curl -s http://127.0.0.1:8000/me --cookie "session=<JWT>"
```

---

## Troubleshooting

- Pip says “externally‑managed‑environment”: use `venv` as shown above.
- CORS errors: set `FRONTEND_ORIGIN` to your Vite URL (e.g., `http://localhost:5175`) and restart Bob.
- Vite port already in use: it will pick another port; update `FRONTEND_ORIGIN` to match.
- Supabase: the frontend uses a dev‑safe stub (`src/supabase.js`) so sign‑in works without a Supabase project.

---

## Project Structure

```
zcashme/
├── bob-cli.py             # Bob PoC HTTP API (single file)
├── logs/audit.log         # JSONL audit log (created on first run)
├── sessions.json          # Session store
├── src/                   # React app (Sign‑In, directory, etc.)
└── docs/README-bob-poc.md # Additional notes
```

Pull requests welcome. For significant changes, open an issue first.
