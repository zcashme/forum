#!/usr/bin/env bash
set -euo pipefail
source .env
ADDR="${VITE_SCAN_ADDR}"
EXIST_FILE="$(mktemp)"
# Load existing unique keys (txid|memo_hex)
curl -s "${SUPABASE_URL}/rest/v1/zecbook?select=txid,memo_hex&limit=10000" \
  -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" -H "Content-Profile: public" \
  | jq -rc 'map((.txid + "|" + (.memo_hex // ""))) | unique' > "${EXIST_FILE}"
echo "Loaded existing keys: $(jq -r length "${EXIST_FILE}")"
OUT_FILE="$(mktemp)"
curl -s "http://127.0.0.1:9012/list-all?addr=${ADDR}&min=0" > list_all.json
jq -c --arg ADDR "${ADDR}" --argjson EXIST "$(cat "${EXIST_FILE}")" '
[ .outputs[]
  | select(.to_address != $ADDR)
  | . as $m
  | {
      txid: $m.txid,
      ts: $m.ts,
      amount: $m.amount,
      memo_hex: ($m.memo_hex // ""),
      memo_text: ($m.memo_text // null),
      to_address: ($m.to_address // $ADDR),
      source: "devtool",
      ingested_at: (now | todateiso8601),
      height: $m.height
    }
  | select(($EXIST | index((.txid + "|" + .memo_hex))) == null)
]
' list_all.json > "${OUT_FILE}"
echo "Prepared OUT rows to insert: $(jq -r length "${OUT_FILE}")"
if [ "$(jq -r length "${OUT_FILE}")" = "0" ]; then echo "No new OUT rows to insert."; rm "${EXIST_FILE}" "${OUT_FILE}" list_all.json; exit 0; fi
curl -i -s -X POST "${SUPABASE_URL}/rest/v1/zecbook" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H "Content-Profile: public" \
  -H "Prefer: return=representation" \
  --data-binary @"${OUT_FILE}" | sed -n "1,120p"
rm "${EXIST_FILE}" "${OUT_FILE}" list_all.json