import logging
from datetime import datetime
import re

from .db import get_db, init_db
from .utils.wallet_reader import run_read_view_key
from .utils.zcash_parser import parse_list_tx_text
from .config import REPLY_PREFIX

log = logging.getLogger(__name__)

def process_transactions():
    init_db()

    text = run_read_view_key()
    txs = parse_list_tx_text(text)
    if not txs:
        log.info("No transactions parsed")
        return

    conn = get_db()
    cur = conn.cursor()
    new_count = 0

    for tx in txs:
        txid = tx["txid"]
        mined_time = tx.get("mined_time") or datetime.utcnow().isoformat(timespec="seconds") + "Z"

        for out in tx.get("outputs", []):
            memo = out.get("memo")
            idx = out.get("index", 0)
            if not memo:
                continue

            memo_str = memo.strip()
            if not memo_str:
                continue

            parent_id = None
            clean_text = memo_str

            m = re.match(rf"{REPLY_PREFIX}(\d+):(.*)$", memo_str, re.DOTALL)
            if m:
                parent_id = int(m.group(1))
                clean_text = m.group(2).lstrip()

            body = clean_text[:504]
            amount_zats = out.get("amount_zats")

            try:
                cur.execute(
                    """
                    INSERT INTO messages (txid, output_index, created_at, text, amount_zats, parent_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(txid, output_index) DO UPDATE SET
                        amount_zats = excluded.amount_zats,
                        parent_id   = COALESCE(messages.parent_id, excluded.parent_id),
                        text        = COALESCE(messages.text, excluded.text),
                        created_at  = COALESCE(messages.created_at, excluded.created_at)
                    """,
                    (txid, idx, mined_time, body, amount_zats, parent_id),
                )
                if cur.rowcount > 0:
                    new_count += 1
                    log.info(
                        "Upserted post from tx %s output %s (amount_zats=%r, parent_id=%r)",
                        txid, idx, amount_zats, parent_id,
                    )
            except Exception:
                log.exception("Failed to upsert message for tx %s", txid)

    conn.commit()
    conn.close()
    log.info("Scan complete. New posts: %s", new_count)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    process_transactions()
