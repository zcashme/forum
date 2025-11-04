import os
import json
import subprocess
import re
import urllib.request, urllib.parse
from datetime import datetime
from flask import Flask, request, jsonify

app = Flask(__name__)
SYNC_PROC = None
FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "http://localhost:5174")

@app.after_request
def add_cors_headers(resp):
    try:
        resp.headers['Access-Control-Allow-Origin'] = FRONTEND_ORIGIN
        resp.headers['Access-Control-Allow-Credentials'] = 'true'
        resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        resp.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
    except Exception:
        pass
    return resp

# Defaults based on your current setup; can be overridden via env vars
DEVTOOL_HOME = os.environ.get(
    "DEVTOOL_HOME",
    "/Users/haoxiang/Downloads/EDA-CLINICAL-Projects/Wallet/zcash-devtool",
)
WALLET_DIR = os.environ.get(
    "DEVTOOL_WALLET_DIR",
    "/Users/haoxiang/Downloads/EDA-CLINICAL-Projects/Wallet/main-wallet",
)
IDENTITY_FILE = os.environ.get(
    "DEVTOOL_IDENTITY_FILE",
    "/Users/haoxiang/Downloads/EDA-CLINICAL-Projects/Wallet/main-wallet/main-key.txt",
)
SERVER = os.environ.get("DEVTOOL_LIGHTWALLETD", "zecrocks")
ACCOUNT_ID = os.environ.get("DEVTOOL_ACCOUNT_ID", "")


def to_zats(amount):
    """Convert amount (ZEC) -> zatoshis (int). Accepts float/str/int."""
    if amount is None:
        raise ValueError("amount missing")
    try:
        # If Bob posts decimal ZEC like 0.000001
        amt = float(amount)
        zats = int(round(amt * 10**8))
        return zats
    except Exception:
        # If Bob posts already zats as string/int
        return int(amount)


def decode_memo(memo):
    """Decode hex memo (preferred) or pass-through string."""
    if memo is None:
        return ""
    memo_str = memo
    # Try hex decode
    try:
        b = bytes.fromhex(memo.strip())
        try:
            return b.decode("utf-8", errors="ignore")
        except Exception:
            return b.decode("latin1", errors="ignore")
    except Exception:
        # Not hex; assume plain text
        return memo_str


@app.route("/send", methods=["POST"])
def send():
    data = request.get_json(force=True, silent=True) or {}
    to = data.get("to")
    amount = data.get("amount")  # Bob typically posts decimal ZEC
    memo = data.get("memo")

    if not to:
        return jsonify({"ok": False, "error": "missing_to"}), 400
    if amount is None:
        return jsonify({"ok": False, "error": "missing_amount"}), 400

    zats = None
    try:
        zats = to_zats(amount)
    except Exception:
        return jsonify({"ok": False, "error": "bad_amount"}), 400

    memo_text = decode_memo(memo)

    # Build CLI command. We use cargo run to avoid relying on a release binary.
    cmd = [
        "cargo",
        "run",
        "--release",
        "--bin",
        "zcash-devtool",
        "--",
        "wallet",
        "-w",
        WALLET_DIR,
        "send",
        "-i",
        IDENTITY_FILE,
        "--address",
        to,
        "--value",
        str(zats),
        "--memo",
        memo_text,
        "-s",
        SERVER,
    ]
    if ACCOUNT_ID:
        cmd.append(ACCOUNT_ID)

    try:
        proc = subprocess.run(
            cmd,
            cwd=DEVTOOL_HOME,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "timeout"}), 504
    except Exception as e:
        return jsonify({"ok": False, "error": f"exec_error:{e}"}), 500

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""

    if proc.returncode != 0:
        return jsonify({
            "ok": False,
            "error": "cli_failed",
            "stderr": stderr[:1000],
            "stdout": stdout[:1000],
        }), 500

    # Attempt to extract txid from output if present
    txid = None
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        if "txid" in line.lower():
            # naive parse
            parts = line.replace("TXID", "txid").split()
            for p in parts:
                if len(p) >= 16 and p.isalnum():
                    txid = p
                    break
        if txid:
            break

    if not txid:
        txid = "cli-txid-unknown"

    return jsonify({"ok": True, "txid": txid, "stdout": stdout[:500]})


# --------- Scan Endpoint ---------

def _to_iso(ts_raw: str) -> str:
    try:
        # e.g., "2025-10-05 18:45:31.0 +00:00:00"
        ts = ts_raw.split("+")[0].strip()  # naive cut timezone
        return datetime.fromisoformat(ts.replace(" ", "T")).isoformat()
    except Exception:
        return datetime.utcnow().isoformat()


def _hex_or_hexify(s: str) -> str:
    s = (s or "").strip()
    if re.fullmatch(r"[0-9a-fA-F]+", s):
        return s.lower()
    # treat as UTF-8 and hexify
    try:
        return s.encode("utf-8").hex()
    except Exception:
        return s


def _parse_list_tx_stdout(stdout: str, target_addr: str):
    items = []
    txid = None
    ts = None
    amount = None
    to_addr = None
    memo_hex = None

    for raw in stdout.splitlines():
        line = raw.strip()
        if not line:
            # finalize current output if we have memo
            if txid and memo_hex and to_addr and to_addr == target_addr:
                items.append({
                    "txid": txid,
                    "ts": ts or datetime.utcnow().isoformat(),
                    "amount": amount if amount is not None else 0.0,
                    "memo_hex": memo_hex,
                })
            # reset memo fields between outputs
            to_addr = None
            memo_hex = None
            amount = None
            continue

        if re.fullmatch(r"[0-9a-f]{64}", line):
            txid = line
            ts = None
            to_addr = None
            memo_hex = None
            amount = None
            continue

        if line.startswith("Mined:"):
            m = re.search(r"\(([^)]+)\)", line)
            if m:
                ts = _to_iso(m.group(1))
            continue

        if line.startswith("Value:"):
            m = re.search(r"([0-9.]+)\s+ZEC", line)
            if m:
                try:
                    amount = float(m.group(1))
                except Exception:
                    amount = 0.0
            continue

        if line.startswith("To:"):
            to_addr = line.split("To:", 1)[1].strip()
            continue

        # Different builds may show "Memo:" or "Memo (Orchard):"
        if line.lower().startswith("memo"):
            parts = line.split(":", 1)
            if len(parts) == 2:
                memo_hex = _hex_or_hexify(parts[1])
            continue

    # flush last record
    if txid and memo_hex and to_addr and to_addr == target_addr:
        items.append({
            "txid": txid,
            "ts": ts or datetime.utcnow().isoformat(),
            "amount": amount if amount is not None else 0.0,
            "memo_hex": memo_hex,
        })

    return items


# Supabase configuration (service-side write)
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
SUPABASE_SCHEMA = os.environ.get("SUPABASE_SCHEMA", "zda")
SUPABASE_TABLE = os.environ.get("SUPABASE_TABLE", "zecbook")
PERSIST_MODE_DEFAULT = os.environ.get("DEVTOOL_PERSIST_MODE", "memos_only").lower()


def _dedup_by_keys(rows, conflict_keys: str):
    try:
        keys = [k.strip() for k in (conflict_keys or "").split(",") if k.strip()]
        seen = set()
        result = []
        for r in rows or []:
            key = tuple((r.get(k) or "") for k in keys)
            if key in seen:
                continue
            seen.add(key)
            result.append(r)
        return result
    except Exception:
        return rows


def _upsert_memos_supabase(rows, conflict_keys="txid,to_address,memo_hex", schema=SUPABASE_SCHEMA, table=SUPABASE_TABLE):
    if not SUPABASE_URL or not SUPABASE_KEY or not table:
        return {"ok": False, "skipped": True, "reason": "missing_supabase_config"}
    try:
        endpoint = f"{SUPABASE_URL.rstrip('/')}/rest/v1/{table}"
        params = {"on_conflict": conflict_keys}
        url = endpoint + "?" + urllib.parse.urlencode(params)
        data = json.dumps(rows).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {SUPABASE_KEY}")
        req.add_header("apikey", SUPABASE_KEY)
        # Target non-public schema if provided
        if schema:
            req.add_header("Content-Profile", schema)
        # Merge duplicates on conflict
        req.add_header("Prefer", "resolution=merge-duplicates")
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.getcode()
            body = resp.read()[:500]
        return {"ok": 200 <= status < 300, "status": status, "body": body.decode("utf-8", errors="ignore")}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.route("/scan", methods=["GET"])
def scan():
    addr = request.args.get("addr", "").strip()
    if not addr:
        return jsonify({"ok": False, "error": "missing_addr"}), 400

    # Optional: since seconds; server-side filter
    try:
        since_sec = int(request.args.get("since", "600"))
    except Exception:
        since_sec = 600

    # Optional: minimum amount threshold in ZEC (query `min` or env `DEVTOOL_MIN_ZEC`)
    try:
        min_zec = float(request.args.get("min", os.environ.get("DEVTOOL_MIN_ZEC", "0.0005")))
    except Exception:
        min_zec = 0.0005
    if min_zec < 0:
        min_zec = 0.0

    # New: persistence mode override via query param
    persist_mode = request.args.get("persist_mode", PERSIST_MODE_DEFAULT).lower()

    # Build CLI command to list transactions; prefer enhanced data
    cmd = [
        "cargo",
        "run",
        "--release",
        "--bin",
        "zcash-devtool",
        "--",
        "wallet",
        "-w",
        WALLET_DIR,
        "list-tx",
    ]
    if ACCOUNT_ID:
        cmd.append(ACCOUNT_ID)

    try:
        proc = subprocess.run(
            cmd,
            cwd=DEVTOOL_HOME,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "timeout"}), 504
    except Exception as e:
        return jsonify({"ok": False, "error": f"exec_error:{e}"}), 500

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""

    if proc.returncode != 0:
        return jsonify({
            "ok": False,
            "error": "cli_failed",
            "stderr": stderr[:1000],
            "stdout": stdout[:1000],
        }), 500

    # Try JSON first if CLI supports it
    memos = []
    try:
        data = json.loads(stdout)
        # Expect a list of tx objects; try to normalize
        for tx in (data if isinstance(data, list) else data.get("transactions", [])):
            txid = tx.get("txid") or tx.get("id")
            ts = tx.get("time") or tx.get("ts")
            outputs = tx.get("outputs") or []
            for out in outputs:
                to_addr = out.get("address") or out.get("to")
                memo = out.get("memo_hex") or out.get("memo")
                amount = out.get("amount") or out.get("value")
                if to_addr == addr and memo:
                    memos.append({
                        "txid": txid or "unknown-txid",
                        "ts": ts or datetime.utcnow().isoformat(),
                        "amount": float(amount) if amount is not None else 0.0,
                        "memo_hex": _hex_or_hexify(str(memo)),
                    })
    except Exception:
        # Fallback: parse human-readable stdout
        memos = _parse_list_tx_stdout(stdout, target_addr=addr)

    # Build outputs_for_addr (for persist_mode=all and server-side filters)
    outputs_for_addr = []
    try:
        data2 = json.loads(stdout)
        for tx in (data2 if isinstance(data2, list) else data2.get("transactions", [])):
            txid = tx.get("txid") or tx.get("id")
            ts = tx.get("time") or tx.get("ts")
            height = tx.get("height")
            for out in (tx.get("outputs") or []):
                to_addr = out.get("address") or out.get("to")
                memo = out.get("memo_hex") or out.get("memo")
                amount = out.get("amount") or out.get("value")
                incoming = out.get("incoming")
                if to_addr == addr:
                    outputs_for_addr.append({
                        "txid": txid or "unknown-txid",
                        "ts": ts or datetime.utcnow().isoformat(),
                        "height": height,
                        "amount": float(amount) if amount is not None else 0.0,
                        "memo_hex": _hex_or_hexify(str(memo)) if memo is not None else None,
                        "to_address": to_addr,
                        "incoming": bool(incoming),
                    })
    except Exception:
        try:
            outputs_full = _parse_list_tx_stdout_full(stdout)
            outputs_for_addr = [m for m in outputs_full if m.get("to_address") == addr]
        except Exception:
            outputs_for_addr = []

    # Server-side time filter (if ts present and ISO)
    if since_sec and memos:
        try:
            cutoff = datetime.utcnow().timestamp() - since_sec
            def _keep(m):
                try:
                    ts = datetime.fromisoformat(m.get("ts", datetime.utcnow().isoformat())).timestamp()
                    return ts >= cutoff
                except Exception:
                    return True
            memos = [m for m in memos if _keep(m)]
        except Exception:
            pass
    if since_sec and outputs_for_addr:
        try:
            cutoff = datetime.utcnow().timestamp() - since_sec
            def _keep2(m):
                try:
                    ts = datetime.fromisoformat(m.get("ts", datetime.utcnow().isoformat())).timestamp()
                    return ts >= cutoff
                except Exception:
                    return True
            outputs_for_addr = [m for m in outputs_for_addr if _keep2(m)]
        except Exception:
            pass

    # Minimum amount filter (server-side)
    if memos:
        try:
            memos = [m for m in memos if float(m.get("amount", 0.0)) >= min_zec]
        except Exception:
            pass
    if outputs_for_addr:
        try:
            outputs_for_addr = [m for m in outputs_for_addr if float(m.get("amount", 0.0)) >= min_zec]
        except Exception:
            pass

    # Decode memo hex -> UTF-8 text for convenience
    if memos:
        try:
            for m in memos:
                m["memo_text"] = decode_memo(m.get("memo_hex"))
        except Exception:
            pass

    # Persist to Supabase (best-effort)
    try:
        rows = []
        if persist_mode == "all":
            rows = [{
                "txid": m.get("txid"),
                "ts": m.get("ts"),
                "amount": m.get("amount"),
                "memo_hex": m.get("memo_hex") or "",
                "memo_text": decode_memo(m.get("memo_hex")) if m.get("memo_hex") else None,
                "to_address": addr,
                "source": "devtool",
                "ingested_at": datetime.utcnow().isoformat(),
                "height": m.get("height"),
            } for m in outputs_for_addr]
        else:
            rows = [{
                "txid": m.get("txid"),
                "ts": m.get("ts"),
                "amount": m.get("amount"),
                "memo_hex": m.get("memo_hex"),
                "memo_text": m.get("memo_text"),
                "to_address": addr,
                "source": "devtool",
                "ingested_at": datetime.utcnow().isoformat(),
            } for m in memos if m.get("memo_hex")]
        conflict_keys = "txid,to_address,memo_hex" if persist_mode == "all" else "txid,memo_hex"
        rows = _dedup_by_keys(rows, conflict_keys)
        supa_res = _upsert_memos_supabase(rows, conflict_keys=conflict_keys)
        persisted = bool(supa_res.get("ok"))
    except Exception:
        supa_res = {"ok": False, "error": "upsert_failed"}

    return jsonify({"ok": True, "memos": memos, "persisted": bool(supa_res.get("ok")), "persist_mode": persist_mode})


# --- Extended parsing: all outputs with height & direction ---

def _parse_list_tx_stdout_full(stdout: str):
    outputs = []
    current = None
    current_txid = None
    current_ts = None
    current_height = None

    def _flush():
        nonlocal current
        if current and current.get("txid"):
            # normalize defaults
            item = {
                "txid": current.get("txid"),
                "ts": current.get("ts") or datetime.utcnow().isoformat(),
                "height": current.get("height"),
                "amount": current.get("amount") if current.get("amount") is not None else 0.0,
                "to_address": current.get("to_address"),
                "incoming": bool(current.get("incoming")),
                "memo_hex": current.get("memo_hex"),
            }
            outputs.append(item)
        current = None

    for raw in stdout.splitlines():
        line = raw.strip()
        if not line:
            _flush()
            continue

        # new transaction header
        if re.fullmatch(r"[0-9a-f]{64}", line):
            _flush()
            current_txid = line
            current_ts = None
            current_height = None
            continue

        if line.startswith("Mined:"):
            try:
                m_ht = re.search(r"Mined:\s*(\d+)", line)
                if m_ht:
                    current_height = int(m_ht.group(1))
            except Exception:
                pass
            m = re.search(r"\(([^)]+)\)", line)
            if m:
                current_ts = _to_iso(m.group(1))
            continue

        if line.startswith("Output"):
            _flush()
            current = {
                "txid": current_txid,
                "ts": current_ts,
                "height": current_height,
                "amount": None,
                "to_address": None,
                "incoming": None,
                "memo_hex": None,
            }
            continue

        if line.startswith("Value:"):
            m = re.search(r"([0-9.]+)\s+ZEC", line)
            if m and current is not None:
                try:
                    current["amount"] = float(m.group(1))
                except Exception:
                    current["amount"] = 0.0
            continue

        if "Received by account:" in line:
            if current is not None:
                current["incoming"] = True
            continue

        if line.startswith("To:"):
            if current is not None:
                current["to_address"] = line.split("To:", 1)[1].strip()
            continue

        # Different builds may show "Memo:" or "Memo (Orchard):"
        if line.lower().startswith("memo"):
            parts = line.split(":", 1)
            if len(parts) == 2 and current is not None:
                current["memo_hex"] = _hex_or_hexify(parts[1])
            continue

    # flush last record
    _flush()

    return outputs


@app.route("/import-ufvk", methods=["POST"])
def import_ufvk():
    data = request.get_json(force=True, silent=True) or {}
    ufvk = data.get("ufvk", "").strip()
    name = (data.get("name") or "admin").strip()
    # Allow birthday height override; default 0
    try:
        birthday = int(data.get("birthday", 0))
    except Exception:
        birthday = 0
    if not ufvk:
        return jsonify({"ok": False, "error": "missing_ufvk"}), 400

    cmd = [
        "cargo", "run", "--release", "--bin", "zcash-devtool", "--",
        "wallet", "-w", WALLET_DIR,
        "import-ufvk",
        "--name", name,
        "-s", SERVER,
        ufvk, str(birthday),
    ]

    try:
        proc = subprocess.run(
            cmd,
            cwd=DEVTOOL_HOME,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "timeout"}), 504
    except Exception as e:
        return jsonify({"ok": False, "error": f"exec_error:{e}"}), 500

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""

    return jsonify({
        "ok": proc.returncode == 0,
        "stdout": stdout[:2000],
        "stderr": stderr[:2000],
    }), (200 if proc.returncode == 0 else 500)


@app.route("/sync", methods=["GET"])
def sync():
    global SYNC_PROC
    if SYNC_PROC and SYNC_PROC.poll() is None:
        return jsonify({"ok": True, "status": "running"}), 200

    cmd = [
        "cargo", "run", "--release", "--bin", "zcash-devtool", "--",
        "wallet", "-w", WALLET_DIR,
        "sync",
        "-s", SERVER,
    ]

    try:
        SYNC_PROC = subprocess.Popen(
            cmd,
            cwd=DEVTOOL_HOME,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return jsonify({"ok": True, "status": "started"}), 202
    except Exception as e:
        return jsonify({"ok": False, "error": f"exec_error:{e}"}), 500


@app.route("/sync-status", methods=["GET"])
def sync_status():
    global SYNC_PROC
    if not SYNC_PROC:
        return jsonify({"ok": True, "status": "idle"})
    code = SYNC_PROC.poll()
    if code is None:
        return jsonify({"ok": True, "status": "running"})
    else:
        ok = (code == 0)
        SYNC_PROC = None
        return jsonify({"ok": ok, "status": "completed", "exit_code": code}), (200 if ok else 500)


@app.route("/list-all", methods=["GET"])
def list_all():
    # Filters
    try:
        since_sec = int(request.args.get("since", "0"))
    except Exception:
        since_sec = 0
    try:
        min_zec = float(request.args.get("min", "0"))
    except Exception:
        min_zec = 0.0
    try:
        height_min = int(request.args.get("height_min", "0"))
    except Exception:
        height_min = 0
    persist = request.args.get("persist", "0").lower() in ("1", "true", "yes")
    # New: addr for filling to_address when missing
    addr = request.args.get("addr")
    # New: restrict persistence (and response) to target addr only
    addr_only = request.args.get("addr_only", "0").lower() in ("1", "true", "yes")
    
    # New: persistence mode override via query param
    persist_mode = request.args.get("persist_mode", PERSIST_MODE_DEFAULT).lower()

    # List all transactions from the wallet
    cmd = [
        "cargo", "run", "--release", "--bin", "zcash-devtool", "--",
        "wallet", "-w", WALLET_DIR,
        "list-tx",
    ]
    if ACCOUNT_ID:
        cmd.append(ACCOUNT_ID)

    try:
        proc = subprocess.run(
            cmd,
            cwd=DEVTOOL_HOME,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "timeout"}), 504
    except Exception as e:
        return jsonify({"ok": False, "error": f"exec_error:{e}"}), 500

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""

    if proc.returncode != 0:
        lower = (stderr + stdout).lower()
        if "database is locked" in lower:
            return jsonify({"ok": False, "error": "db_locked"}), 503
        return jsonify({
            "ok": False,
            "error": "cli_failed",
            "stderr": stderr[:1000],
            "stdout": stdout[:1000],
        }), 500

    # Try JSON first; otherwise parse stdout fully
    outputs = []
    try:
        data = json.loads(stdout)
        for tx in (data if isinstance(data, list) else data.get("transactions", [])):
            txid = tx.get("txid") or tx.get("id")
            ts = tx.get("time") or tx.get("ts")
            height = tx.get("height")
            for out in (tx.get("outputs") or []):
                to_addr = out.get("address") or out.get("to")
                memo = out.get("memo_hex") or out.get("memo")
                amount = out.get("amount") or out.get("value")
                incoming = out.get("incoming")
                outputs.append({
                    "txid": txid or "unknown-txid",
                    "ts": ts or datetime.utcnow().isoformat(),
                    "height": height,
                    "amount": float(amount) if amount is not None else 0.0,
                    "memo_hex": _hex_or_hexify(str(memo)) if memo is not None else None,
                    "to_address": to_addr,
                    "incoming": bool(incoming),
                })
    except Exception:
        outputs = _parse_list_tx_stdout_full(stdout)

    # Optional: restrict outputs to target addr only
    try:
        if addr_only and addr:
            outputs = [m for m in outputs if m.get("to_address") == addr]
    except Exception:
        pass

    # Server-side filters
    if since_sec and outputs:
        try:
            cutoff = datetime.utcnow().timestamp() - since_sec
            def _keep(m):
                try:
                    ts = datetime.fromisoformat(m.get("ts", datetime.utcnow().isoformat())).timestamp()
                    return ts >= cutoff
                except Exception:
                    return True
            outputs = [m for m in outputs if _keep(m)]
        except Exception:
            pass
    if min_zec and outputs:
        try:
            outputs = [m for m in outputs if float(m.get("amount") or 0.0) >= min_zec]
        except Exception:
            pass
    if height_min and outputs:
        try:
            outputs = [m for m in outputs if int(m.get("height") or 0) >= height_min]
        except Exception:
            pass

    # Decode memo for convenience
    try:
        for m in outputs:
            if m.get("memo_hex"):
                m["memo_text"] = decode_memo(m.get("memo_hex"))
    except Exception:
        pass

    # Persist to Supabase if requested
    persisted = False
    if persist and outputs:
        try:
            if persist_mode == "all":
                rows = [{
                    "txid": m.get("txid"),
                    "ts": m.get("ts"),
                    "amount": m.get("amount"),
                    "memo_hex": m.get("memo_hex") or "",
                    "memo_text": m.get("memo_text") if m.get("memo_hex") else None,
                    "to_address": m.get("to_address") or addr,
                    "source": "devtool",
                    "ingested_at": datetime.utcnow().isoformat(),
                    "height": m.get("height"),
                } for m in outputs if (not addr_only) or (m.get("to_address") == addr)]
            else:
                rows = [{
                    "txid": m.get("txid"),
                    "ts": m.get("ts"),
                    "amount": m.get("amount"),
                    "memo_hex": m.get("memo_hex"),
                    "memo_text": m.get("memo_text"),
                    "to_address": (m.get("to_address") or addr),
                    "source": "devtool",
                    "ingested_at": datetime.utcnow().isoformat(),
                    "height": m.get("height"),
                } for m in outputs if m.get("memo_hex") and ((not addr_only) or (m.get("to_address") == addr))]
            conflict_keys = "txid,to_address,memo_hex" if persist_mode == "all" else "txid,memo_hex"
            rows = _dedup_by_keys(rows, conflict_keys)
            supa_res = _upsert_memos_supabase(rows, conflict_keys=conflict_keys)
            persisted = bool(supa_res.get("ok"))
        except Exception:
            persisted = False

    return jsonify({"ok": True, "outputs": outputs, "persisted": persisted, "persist_mode": persist_mode})


@app.route("/", methods=["GET"]) 
def root():
    return jsonify({
        "ok": True,
        "adapter": "zcash-devtool-cli",
        "wallet_dir": WALLET_DIR,
        "identity_file": IDENTITY_FILE,
        "server": SERVER,
    })


if __name__ == "__main__":
    port = int(os.environ.get("DEVTOOL_ADAPTER_PORT", "9000"))
    host = os.environ.get("DEVTOOL_ADAPTER_HOST", "127.0.0.1")
    app.run(host=host, port=port)