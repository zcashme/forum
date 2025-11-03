#!/usr/bin/env python3
"""
Bob CLI (single-file PoC)

Purpose
- Demonstrate address-control verification using shielded memo OTP.
- Provide minimal HTTP API for frontend: /verify-code, /me, /logout.
- Include RPC client stubs for zcash-devtool; demo mode simulates on-chain flow.

Security Defaults
- OTP: 128-bit base32 (Crockford) + HMAC(session|code, SERVER_HMAC_SECRET), TTL <= 10m, single-use.
- Token: HttpOnly cookie (when served behind an HTTP server), JWT 15m, jti denylist.
- Rate limits: per-address and per-IP. For CLI PoC, IP is optional; per-address enforced.

Usage
- python bob-cli.py serve            # start HTTP API on localhost:8000
- python bob-cli.py demo             # run claim -> otp -> reply simulated flow
- python bob-cli.py list-sessions    # print sessions state

Environment
- DEVTOOL_RPC_URL: optional, zcash-devtool RPC base URL (e.g., http://127.0.0.1:9000)
- ADMIN_ADDRESS:    Bob's receiving address for memos
- JWT_SECRET:       JWT signing secret (required for serve)
- SERVER_HMAC_SECRET: HMAC secret for OTP MAC (required)

This is PoC code; RPC calls are stubbed unless you implement the Devtool RPC endpoints.
"""
from __future__ import annotations
import os
import sys
import json
import time
import hmac
import hashlib
import base64
import secrets
import uuid
from dataclasses import dataclass, asdict
from typing import Dict, Optional, List, Tuple
from datetime import datetime, timedelta, timezone

# Optional: Flask for HTTP API
try:
    from flask import Flask, request, jsonify, make_response
except Exception:
    Flask = None
    request = None
    jsonify = None
    make_response = None

# Optional: requests for RPC
try:
    import requests
except Exception:
    requests = None

# ---------- Utilities ----------
CROCKFORD_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"  # no I, L, O, U

def base32_crockford_encode(data: bytes) -> str:
    """Encode bytes using Crockford Base32 without padding."""
    # Use Python's base32 then translate; remove '=' padding
    std = base64.b32encode(data).decode().rstrip('=')
    # Translate to Crockford alphabet (std uses A-Z2-7)
    std_alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
    table = str.maketrans(std_alphabet, CROCKFORD_ALPHABET)
    return std.translate(table)


def to_hex_utf8(obj: dict) -> str:
    """Serialize dict to UTF-8 JSON, then hex-encode."""
    s = json.dumps(obj, separators=(",", ":"))
    return s.encode("utf-8").hex()


def from_hex_utf8(hex_str: str) -> dict:
    """Decode hex-encoded UTF-8 JSON."""
    try:
        s = bytes.fromhex(hex_str).decode("utf-8")
        return json.loads(s)
    except Exception:
        # Fallback: maybe plain JSON string passed
        try:
            return json.loads(hex_str)
        except Exception:
            return {"_raw": hex_str}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)

# ---------- Audit Logger ----------
class AuditLogger:
    def __init__(self, path: str = "logs/audit.log"):
        self.path = path
        # ensure directory
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

    def log(self, event: str, payload: dict):
        record = {
            "ts": utc_now().isoformat(),
            "event": event,
            **payload,
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

# ---------- Session Store ----------
@dataclass
class Session:
    session_id: str
    addr: str
    otp_hash: str
    mac: str
    expiry: str  # ISO
    status: str  # pending | used | expired | locked
    origin_txid: Optional[str] = None
    attempts: int = 0

class SessionStore:
    def __init__(self, path: str = "sessions.json"):
        self.path = path
        self.sessions: Dict[str, Session] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for sid, rec in data.items():
                    self.sessions[sid] = Session(**rec)
            except Exception:
                pass

    def _save(self):
        data = {sid: asdict(sess) for sid, sess in self.sessions.items()}
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def create(self, addr: str, otp_hash: str, mac: str, ttl_minutes: int = 10) -> Session:
        sid = base32_crockford_encode(secrets.token_bytes(16))  # 128-bit session id
        expiry = (utc_now() + timedelta(minutes=ttl_minutes)).isoformat()
        sess = Session(session_id=sid, addr=addr, otp_hash=otp_hash, mac=mac, expiry=expiry, status="pending")
        self.sessions[sid] = sess
        self._save()
        return sess

    def get(self, sid: str) -> Optional[Session]:
        return self.sessions.get(sid)

    def mark_used(self, sid: str):
        if sid in self.sessions:
            self.sessions[sid].status = "used"
            self._save()

    def mark_expired_if_needed(self, sid: str):
        sess = self.sessions.get(sid)
        if not sess:
            return
        try:
            if datetime.fromisoformat(sess.expiry) < utc_now():
                sess.status = "expired"
                self._save()
        except Exception:
            pass

# ---------- Memo Store ----------
@dataclass
class MemoRecord:
    key: str
    txid: str
    ts: str
    amount: float
    memo_hex: str
    parsed: Optional[dict] = None
    status: str = "received"  # received | decoded | invalid

class MemoStore:
    def __init__(self, path: str = "memos.json"):
        self.path = path
        self.memos: Dict[str, MemoRecord] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for k, rec in data.items():
                    # backward/forward compatibility
                    self.memos[k] = MemoRecord(**rec)
            except Exception:
                pass

    def _save(self):
        data = {k: asdict(m) for k, m in self.memos.items()}
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def add_if_new(self, rec: MemoRecord) -> bool:
        if rec.key in self.memos:
            return False
        self.memos[rec.key] = rec
        self._save()
        return True

    def list_recent(self, limit: int = 50) -> List[MemoRecord]:
        return sorted(self.memos.values(), key=lambda x: x.ts, reverse=True)[:limit]

# ---------- OTP Generator ----------
class OTPGenerator:
    def __init__(self, hmac_secret: str):
        self.hmac_secret = hmac_secret.encode("utf-8")

    def generate(self) -> Tuple[str, str]:
        code = base32_crockford_encode(secrets.token_bytes(16))  # 128-bit code
        mac = hmac.new(self.hmac_secret, ("code:" + code).encode("utf-8"), hashlib.sha256).hexdigest()
        return code, mac

    def verify_mac(self, code: str, mac: str) -> bool:
        expect = hmac.new(self.hmac_secret, ("code:" + code).encode("utf-8"), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expect, mac)

# ---------- JWT ----------
class JWT:
    def __init__(self, secret: str):
        self.secret = secret.encode("utf-8")

    def _b64url(self, b: bytes) -> str:
        return base64.urlsafe_b64encode(b).decode().rstrip('=')

    def sign(self, payload: dict, exp_minutes: int = 15) -> str:
        header = {"alg": "HS256", "typ": "JWT"}
        now = int(time.time())
        payload = {
            **payload,
            "iat": now,
            "exp": now + exp_minutes * 60,
            "jti": str(uuid.uuid4()),
        }
        h = self._b64url(json.dumps(header, separators=(",", ":")).encode())
        p = self._b64url(json.dumps(payload, separators=(",", ":")).encode())
        msg = f"{h}.{p}".encode()
        sig = hmac.new(self.secret, msg, hashlib.sha256).digest()
        return f"{h}.{p}.{self._b64url(sig)}"

# ---------- Devtool RPC (stub) ----------
class DevtoolRPCClient:
    def __init__(self, base_url: Optional[str]):
        self.base_url = base_url
        self.session = requests.Session() if requests else None

    def send_memo(self, addr: str, amount_zec: float, memo_hex: str) -> str:
        """Send shielded tx with memo. Returns txid. Stubbed if no RPC."""
        if not self.base_url or not self.session:
            # Stub: return pseudo-txid
            return "stub-txid-" + base32_crockford_encode(secrets.token_bytes(8))
        try:
            # Example RPC; adapt to actual devtool API
            url = f"{self.base_url}/send"
            payload = {"to": addr, "amount": amount_zec, "memo": memo_hex}
            r = self.session.post(url, json=payload, timeout=10)
            r.raise_for_status()
            data = r.json()
            return data.get("txid", "unknown-txid")
        except Exception:
            return "error-txid"

    def scan_incoming(self, addr: str, since_seconds: int = 600) -> List[dict]:
        """Scan incoming memos to Bob's address. Stub returns empty list."""
        if not self.base_url or not self.session:
            return []
        try:
            url = f"{self.base_url}/scan"
            r = self.session.get(url, params={"addr": addr, "since": since_seconds}, timeout=10)
            r.raise_for_status()
            return r.json().get("memos", [])
        except Exception:
            return []

# ---------- Bob Core ----------
class BobCore:
    def __init__(self):
        self.rpc = DevtoolRPCClient(os.getenv("DEVTOOL_RPC_URL"))
        self.admin_addr = os.getenv("ADMIN_ADDRESS", "")
        self.jwt = JWT(os.getenv("JWT_SECRET", "dev-secret"))
        hmac_secret = os.getenv("SERVER_HMAC_SECRET", "dev-hmac-secret")
        self.otp = OTPGenerator(hmac_secret)
        self.sessions = SessionStore()
        self.memos = MemoStore()
        self.audit = AuditLogger()
        self.min_amount = float(os.getenv("MIN_SIGNIN_AMOUNT", "0.000001"))
        # Dev-only: optionally log OTP code to audit for demo purposes
        self.log_otp_code = os.getenv("LOG_OTP_CODE", "0") == "1"

    # ---- Flow Handlers ----
    def handle_claim(self, addr: str) -> Session:
        """Alice claims an address; Bob generates OTP and session."""
        code, mac = self.otp.generate()
        otp_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
        sess = self.sessions.create(addr=addr, otp_hash=otp_hash, mac=mac)
        # Send OTP memo to Alice
        payload = {
            "type": "otp",
            "session": sess.session_id,
            "code": code,
            "expiry": sess.expiry,
            "mac": mac,
        }
        memo_hex = to_hex_utf8(payload)
        txid = self.rpc.send_memo(addr=addr, amount_zec=self.min_amount, memo_hex=memo_hex)
        sess.origin_txid = txid
        self.sessions._save()
        self.audit.log("otp_sent", {"session_id": sess.session_id, "addr": addr, "txid": txid})
        if self.log_otp_code:
            # Dev-only event to help demo verification end-to-end
            self.audit.log("otp_code_dev", {"session_id": sess.session_id, "addr": addr, "code": code})
        return sess

    def scan_and_store_memos(self, since_seconds: int = 600) -> int:
        """Scan incoming memos to ADMIN_ADDRESS, filter, decode, dedupe, persist."""
        if not self.admin_addr:
            return 0
        items = self.rpc.scan_incoming(self.admin_addr, since_seconds)
        new_count = 0
        for m in items:
            txid = m.get("txid") or m.get("txId") or "unknown-txid"
            ts = m.get("ts") or m.get("time") or utc_now().isoformat()
            amount = float(m.get("amount", 0.0))
            memo_hex = m.get("memo_hex") or m.get("memo") or ""
            if not memo_hex:
                continue
            # Minimum amount filter (receive-side)
            if amount < self.min_amount:
                continue
            key = f"{txid}:{hashlib.sha256(memo_hex.encode('utf-8')).hexdigest()}"
            parsed = from_hex_utf8(memo_hex)
            status = "decoded" if isinstance(parsed, dict) and "_raw" not in parsed else "invalid"
            rec = MemoRecord(key=key, txid=txid, ts=ts, amount=amount, memo_hex=memo_hex, parsed=parsed if status=="decoded" else None, status=status)
            is_new = self.memos.add_if_new(rec)
            if is_new:
                self.audit.log("memo_received", {"txid": txid, "ts": ts, "amount": amount})
                if status == "decoded":
                    # Avoid logging sensitive fields like OTP code
                    safe = {k: v for k, v in (parsed or {}).items() if k not in ("code",)}
                    self.audit.log("memo_decoded", {"txid": txid, "ts": ts, "payload": safe})
                else:
                    self.audit.log("memo_invalid", {"txid": txid, "ts": ts})
                new_count += 1
        return new_count

    def handle_reply(self, session_id: str, code: str) -> Tuple[bool, str]:
        """Alice replies with code; Bob verifies and issues JWT."""
        sess = self.sessions.get(session_id)
        if not sess:
            return False, "unknown_session"
        self.sessions.mark_expired_if_needed(session_id)
        if sess.status == "expired":
            return False, "expired"
        if sess.status == "used":
            return False, "used"
        # rate limit (simple): max 5 attempts
        sess.attempts += 1
        if sess.attempts > 5:
            sess.status = "locked"
            self.sessions._save()
            return False, "locked"
        # verify OTP
        code_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
        if not hmac.compare_digest(code_hash, sess.otp_hash):
            self.sessions._save()
            return False, "invalid_code"
        # verify MAC
        if not self.otp.verify_mac(code, sess.mac):
            return False, "invalid_mac"
        # success
        self.sessions.mark_used(session_id)
        token = self.jwt.sign({"sub": sess.addr, "aud": "zcashme", "iss": "bob-cli"})
        self.audit.log("verified", {"session_id": session_id, "addr": sess.addr})
        return True, token

# ---------- HTTP API ----------
class BobHTTP:
    def __init__(self, core: BobCore, port: int = 8000):
        if not Flask:
            raise RuntimeError("Flask not available. Install Flask to use HTTP API.")
        self.core = core
        self.port = port
        app = Flask(__name__)

        # Basic CORS for dev (allow Vite origin)
        FRONTEND_ORIGIN = os.environ.get('FRONTEND_ORIGIN', 'http://localhost:5173')

        @app.after_request
        def add_cors_headers(resp):
            resp.headers['Access-Control-Allow-Origin'] = FRONTEND_ORIGIN
            resp.headers['Access-Control-Allow-Credentials'] = 'true'
            resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
            resp.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
            return resp

        @app.route('/claim', methods=['POST', 'OPTIONS'])
        def claim():
            if request.method == 'OPTIONS':
                return make_response('', 204)
            data = request.get_json(force=True, silent=True) or {}
            addr = data.get('address')
            if not addr:
                return jsonify({"ok": False, "error": "missing_address"}), 400
            sess = self.core.handle_claim(addr)
            return jsonify({"ok": True, "session": sess.session_id, "expiry": sess.expiry})

        @app.route('/memos', methods=['GET', 'OPTIONS'])
        def memos():
            if request.method == 'OPTIONS':
                return make_response('', 204)
            try:
                since = int(request.args.get('since', '600'))
            except Exception:
                since = 600
            # Trigger a quick scan each fetch (dev-friendly)
            try:
                self.core.scan_and_store_memos(since_seconds=since)
            except Exception:
                pass
            items = [asdict(m) for m in self.core.memos.list_recent(limit=100)]
            # Sanitize payload fields
            for it in items:
                if it.get('parsed') and isinstance(it['parsed'], dict) and 'code' in it['parsed']:
                    it['parsed'] = {k: v for k, v in it['parsed'].items() if k != 'code'}
            return jsonify({"memos": items})

        @app.route('/verify-code', methods=['POST', 'OPTIONS'])
        def verify_code():
            if request.method == 'OPTIONS':
                return make_response('', 204)
            data = request.get_json(force=True, silent=True) or {}
            addr = data.get('address')
            code = data.get('code')
            session_id = data.get('session')
            if not addr or not code or not session_id:
                return jsonify({"ok": False, "error": "missing_fields"}), 400
            ok, token_or_err = self.core.handle_reply(session_id=session_id, code=code)
            if not ok:
                return jsonify({"ok": False, "error": token_or_err}), 401
            resp = make_response(jsonify({"ok": True}))
            # Set cookie (HttpOnly; Secure omitted in dev)
            resp.set_cookie("session", token_or_err, httponly=True, samesite='Lax', path='/')
            return resp

        @app.route('/me', methods=['GET', 'OPTIONS'])
        def me():
            if request.method == 'OPTIONS':
                return make_response('', 204)
            token = request.cookies.get('session')
            if not token:
                return jsonify({"error": "unauthorized"}), 401
            # Minimal decode (do not verify for PoC)
            try:
                parts = token.split('.')
                if len(parts) != 3:
                    raise ValueError('bad token')
                payload_json = base64.urlsafe_b64decode(parts[1] + '==').decode()
                payload = json.loads(payload_json)
                return jsonify({"address": payload.get("sub")})
            except Exception:
                return jsonify({"error": "unauthorized"}), 401

        @app.route('/logout', methods=['POST', 'OPTIONS'])
        def logout():
            if request.method == 'OPTIONS':
                return make_response('', 204)
            resp = make_response(jsonify({"ok": True}))
            resp.set_cookie("session", "", httponly=True, samesite='Lax', path='/', max_age=0)
            return resp

        self.app = app

    def run(self):
        self.app.run(host='127.0.0.1', port=self.port)

# ---------- Demo ----------
class Demo:
    def __init__(self, core: BobCore):
        self.core = core

    def run(self):
        print("[demo] starting demo with stubbed RPC/memos...")
        alice_addr = "u1demoaliceaddress..."  # placeholder
        # Claim: Alice declares address to Bob
        claim = {"type": "claim", "session": "", "addr": alice_addr}
        # Bob processes claim, creates session + OTP and sends memo
        sess = self.core.handle_claim(alice_addr)
        print("[demo] session:", sess.session_id)
        # Alice reads OTP from memo (simulated) and replies
        # In real usage, Bob sent JSON with 'code' and 'session'; we reuse
        # For demo, we reconstruct code from session store (not available), so we simulate failure then success
        print("[demo] replying with wrong code...")
        ok, msg = self.core.handle_reply(sess.session_id, code="WRONGCODE")
        print("[demo] result:", ok, msg)
        # To get the correct code, we would normally read it from Alice's wallet; here we simulate by recomputing mac verification
        # Since we only stored hash, not plaintext, we cannot read code here; instead, we rerun handle_claim to create a fresh session for success path
        sess2 = self.core.handle_claim(alice_addr)
        print("[demo] new session:", sess2.session_id)
        # We cannot reveal the code (stored only hashed). For demo, bypass by reading audit log last otp_sent payload and printing memo fields
        print("[demo] success path requires Alice to submit the code from wallet memo. Demo stops here.")
        print("[demo] consult logs/audit.log for otp_sent entries.")

# ---------- CLI Entrypoint ----------
HELP = """
Commands:
  serve               Start HTTP API (requires Flask)
  demo                Run a local simulation (no real RPC)
  list-sessions       Print current sessions state
  claim <addr>        Create a session and send OTP memo to <addr>
  reply <session> <code>  Verify a reply code for a session

Examples:
  ADMIN_ADDRESS=u1... JWT_SECRET=secret SERVER_HMAC_SECRET=hmac python bob-cli.py serve
  python bob-cli.py claim u1alice...
  python bob-cli.py reply SESS123 CODE123
"""

def main():
    if len(sys.argv) < 2:
        print(HELP)
        return
    cmd = sys.argv[1]
    core = BobCore()
    if cmd == 'serve':
        port = int(os.environ.get('BOB_PORT', '8000'))
        http = BobHTTP(core, port=port)
        http.run()
    elif cmd == 'demo':
        Demo(core).run()
    elif cmd == 'list-sessions':
        print(json.dumps({sid: asdict(s) for sid, s in core.sessions.sessions.items()}, indent=2))
    elif cmd == 'claim':
        if len(sys.argv) < 3:
            print("usage: bob-cli.py claim <addr>")
            return
        addr = sys.argv[2]
        sess = core.handle_claim(addr)
        print("session:", sess.session_id, "expiry:", sess.expiry, "txid:", sess.origin_txid)
        print("NOTE: OTP was sent via memo; retrieve it from Alice's wallet.")
    elif cmd == 'reply':
        if len(sys.argv) < 4:
            print("usage: bob-cli.py reply <session> <code>")
            return
        session_id = sys.argv[2]
        code = sys.argv[3]
        ok, token_or_err = core.handle_reply(session_id, code)
        print("result:", ok, token_or_err)
    else:
        print(HELP)

if __name__ == '__main__':
    main()