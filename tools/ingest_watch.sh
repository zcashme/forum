#!/usr/bin/env bash
set -euo pipefail

# Load env (frontend and adapter settings)
if [ -f .env ]; then
  # shellcheck disable=SC2046
  export $(grep -v '^#' .env | xargs)
fi

BASE="${VITE_DEVTOOL_API_BASE:-http://127.0.0.1:9000}"
ADDR="${VITE_SCAN_ADDR:-}"
MODE="${DEVTOOL_PERSIST_MODE:-memos_only}"
INTERVAL="${INGEST_INTERVAL_SEC:-30}"

if [ -z "${ADDR}" ]; then
  echo "[ingest_watch] VITE_SCAN_ADDR is required (target UA/address)" >&2
  exit 1
fi

echo "[ingest_watch] base=${BASE} addr=${ADDR} mode=${MODE} interval=${INTERVAL}s"

while true; do
  TS=$(date -Iseconds)
  # Persist recent transactions into Supabase via adapter.
  curl -s "${BASE}/list-all?persist=1&min=0&since=600&persist_mode=${MODE}&addr=${ADDR}" >/dev/null || true
  echo "[${TS}] persisted latest transactions"
  sleep "${INTERVAL}"
done