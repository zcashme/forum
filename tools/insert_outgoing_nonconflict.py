#!/usr/bin/env python3
import json, os, sys, urllib.request, urllib.parse

def get_env(name):
    v = os.environ.get(name)
    if not v:
        print(f"Missing env: {name}", file=sys.stderr)
        sys.exit(1)
    return v

SUPABASE_URL = get_env("SUPABASE_URL").rstrip("/")
SUPABASE_KEY = get_env("SUPABASE_SERVICE_ROLE_KEY")
ADDR = get_env("VITE_SCAN_ADDR")

# Load existing keys (txid|memo_hex)
req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/zecbook?select=txid,memo_hex&limit=10000")
req.add_header("Authorization", f"Bearer {SUPABASE_KEY}")
req.add_header("apikey", SUPABASE_KEY)
req.add_header("Content-Profile", "public")
with urllib.request.urlopen(req) as resp:
    rows = json.loads(resp.read().decode("utf-8"))
existing = set()
for r in rows:
    txid = r.get("txid", "")
    memo_hex = r.get("memo_hex") or ""
    existing.add(f"{txid}|{memo_hex}")
print(f"Loaded existing keys: {len(existing)}")

# Fetch adapter outputs
with urllib.request.urlopen(f"http://127.0.0.1:9012/list-all?addr={urllib.parse.quote(ADDR)}&min=0") as resp:
    payload = json.loads(resp.read().decode("utf-8"))
outputs = payload.get("outputs", [])

# Prepare outgoing rows that do not conflict (on txid|memo_hex)
rows_to_insert = []
for m in outputs:
    if m.get("to_address") == ADDR:
        continue  # incoming, skip here
    k = f"{m.get('txid', '')}|{(m.get('memo_hex') or '')}"
    if k in existing:
        continue
    rows_to_insert.append({
        "txid": m.get("txid"),
        "ts": m.get("ts"),
        "amount": m.get("amount"),
        "memo_hex": m.get("memo_hex") or "",
        "memo_text": m.get("memo_text") or None,
        "to_address": m.get("to_address") or ADDR,
        "source": "devtool",
        "ingested_at": m.get("ts") or None,
        "height": m.get("height"),
    })
print(f"Prepared OUT rows to insert: {len(rows_to_insert)}")
if not rows_to_insert:
    sys.exit(0)

# Insert
data = json.dumps(rows_to_insert).encode("utf-8")
req2 = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/zecbook", data=data, method="POST")
req2.add_header("Content-Type", "application/json")
req2.add_header("Authorization", f"Bearer {SUPABASE_KEY}")
req2.add_header("apikey", SUPABASE_KEY)
req2.add_header("Content-Profile", "public")
req2.add_header("Prefer", "return=representation")
with urllib.request.urlopen(req2) as resp:
    print(resp.status)
    print(resp.read().decode("utf-8"))