# Bob CLI PoC: Zcash Shielded Memo OTP Authentication

This README shows how to run the Bob single-file CLI to verify control of a Zcash address using shielded transaction memos as an encrypted One-Time-Password (OTP) channel.

> Verification proves control of an address, not real-world identity.

## Components
- Alice: mobile wallet (zashi, zingo, ywallet) capable of reading/sending shielded memos
- Bob: `bob-cli.py` (this repo) for OTP generation, memo send/receive helpers, and HTTP API
- (Optional) zcash-devtool: local RPC for sending shielded transactions; the CLI has stubs if not available

## Security Defaults
- OTP: 128-bit base32 (Crockford) + HMAC(session|code, SERVER_HMAC_SECRET), TTL ≤ 10 minutes, single-use
- JWT: HS256, 15-minute lifetime; HttpOnly cookie in browser environments
- Rate limits: per-address attempts and simple lockouts; audit logging with hashed IP (optional)

## Setup
1. Prepare environment variables:
   ```bash
   export ADMIN_ADDRESS="u1YOUR_BOB_ADDRESS"
   export JWT_SECRET="change-this-secret"
   export SERVER_HMAC_SECRET="change-this-hmac-secret"
   # Optional RPC:
   export DEVTOOL_RPC_URL="http://127.0.0.1:9000"
   export MIN_SIGNIN_AMOUNT="0.000001"
   ```

2. (Optional) Start zcash-devtool RPC locally (adjust to your installation):
   ```bash
   # Example only — replace with actual devtool startup commands
   zcash-devtool start \
     --rpc-bind 127.0.0.1:9000 \
     --wallet bob-wallet \
     --allow-memo-send --allow-memo-scan
   ```
   - Bind RPC to `localhost` only.
   - Prepare Bob wallet with a small balance to cover memo transactions.

## Running Bob CLI

### Start HTTP API (for frontend integration)
```bash
python bob-cli.py serve
```
- Starts on `http://127.0.0.1:8000/`
- Endpoints:
  - `POST /verify-code` body `{ address, code, session }` → sets `session` cookie
  - `GET /me` → returns `{ address }`
  - `POST /logout` → clears cookie

### Manual Flow (claim → otp → reply)
1. Alice sends a claim memo to Bob (using a mobile wallet):
   ```json
   {"type":"claim","session":"","addr":"u1ALICE_ADDRESS"}
   ```
   - The memo should be UTF-8 JSON hex-encoded. Some wallets allow plain JSON.
2. Bob handles claim and sends OTP to Alice:
   ```bash
   python bob-cli.py claim u1ALICE_ADDRESS
   ```
   - Prints the generated `session` and `expiry`.
   - Bob sends OTP memo to Alice with minimal amount (default `0.000001 ZEC`).
3. Alice reads OTP from her wallet and replies (via Bob endpoint or memo):
   - If replying via HTTP (frontend uses this): `POST /verify-code` with `{ address, code, session }`.
   - If replying via memo: send `{ "type":"reply", "session":"<session>", "code":"<otp>" }` to Bob; then Bob verifies using `python bob-cli.py reply <session> <code>`.

### Demo Mode (simulated)
```bash
python bob-cli.py demo
```
- Simulates claim → otp → reply with stubbed RPC.
- Check `logs/audit.log` for `otp_sent` entries.

## Example Logs
- Logs are appended to `logs/audit.log` as JSON lines:
```json
{"ts":"2025-10-24T10:15:00Z","event":"otp_sent","session_id":"SESS123","addr":"u1ALICE","txid":"stub-txid-ABCD"}
{"ts":"2025-10-24T10:16:10Z","event":"verified","session_id":"SESS123","addr":"u1ALICE"}
```
- Include failure cases: `invalid_code`, `expired`, `locked` for auditing.

## Frontend Integration (zcashme React app)
- Configure API base for development:
  ```env
  VITE_AUTH_API_BASE=http://127.0.0.1:8000
  ```
- The frontend will `POST /verify-code` on “Verify Code” in Sign-In mode and then call `/me` to display “Signed in as <address>”.

## Notes & Limitations
- Sender address validation is intentionally not performed (Zcash shielded privacy). Proof relies on reading Bob’s memo to the claimed address.
- RPC calls are stubs unless you wire actual `zcash-devtool` endpoints. Replace `send_memo` and `scan_incoming` with your RPC specifics.
- OTP plaintext is never stored; only a salted hash. Retrieve code from Alice’s wallet memo.

## Troubleshooting
- If cookies aren’t set in the browser, ensure requests use `credentials: 'include'` and the API CORS allows your frontend origin.
- Some wallets display memo as hex. Use plain JSON mode if needed (the CLI accepts both hex and plain JSON for decoding).
- Rates and TTLs are conservative for security; adjust in environment if needed for testing.

## Next Steps
- Add full viewing key (FVK) integration to affirm Bob’s outgoing OTP memo on-chain.
- Implement stronger rate-limiting with IP-aware controls when deploying behind a web server.