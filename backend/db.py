import sqlite3
from .config import DB_PATH

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            text TEXT NOT NULL,
            txid TEXT UNIQUE,
            output_index INTEGER,
            amount_zats INTEGER,
            parent_id INTEGER,
            likes INTEGER
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS message_likes (
            message_id  INTEGER NOT NULL,
            user_id     TEXT    NOT NULL,
            created_at  TEXT    NOT NULL,
            PRIMARY KEY (message_id, user_id)
        )
    """)

    conn.commit()
    conn.close()

def row_to_message(r: sqlite3.Row) -> dict:
    return {
        "id": r["id"],
        "txid": r["txid"],
        "output_index": r["output_index"],
        "amount_zats": r["amount_zats"],
        "parent_id": r["parent_id"],
        "created_at": r["created_at"],
        "text": r["text"],
        "likes": r["likes"] if "likes" in r.keys() and r["likes"] is not None else 0,
    }
