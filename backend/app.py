import os
import logging
from datetime import datetime

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

from .db import get_db, init_db, row_to_message
from .config import FRONTEND_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__, static_folder=None)
CORS(app, resources={r"/api/*": {"origins": "*"}})

init_db()

@app.route("/")
def index():
    # index.html is in frontend/
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<int:msg_id>")
@app.route("/<int:msg_id>/<int:page>")
def post_slug(msg_id, page=0):
    # SPA route – always serve the same index.html
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/post/comment")
def post_comment():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/assets/<path:path>")
def assets(path):
    # serve /assets/... from frontend/assets/...
    assets_dir = os.path.join(FRONTEND_DIR, "assets")
    return send_from_directory(assets_dir, path)

# --------------------------------------------------------------------------
# API – messages
# --------------------------------------------------------------------------
@app.route("/api/messages", methods=["GET"])
def list_messages():
    """
    Optional query params:
      - since_id: only return messages with id > since_id
      - limit: max number of messages (default 50)
    """
    since_id = request.args.get("since_id", type=int)
    limit = request.args.get("limit", 50, type=int)
    limit = max(1, min(limit, 200))  # clamp 1..200

    conn = get_db()
    cur = conn.cursor()

    if since_id is not None:
        cur.execute(
            "SELECT id, txid, output_index, amount_zats, parent_id, "
            "created_at, text, likes "
            "FROM messages WHERE id > ? ORDER BY id ASC LIMIT ?",
            (since_id, limit),
        )
    else:
        cur.execute(
            "SELECT id, txid, output_index, amount_zats, parent_id, "
            "created_at, text, likes "
            "FROM messages ORDER BY id DESC LIMIT ?",
            (limit,),
        )

    rows = cur.fetchall()
    conn.close()

    messages = [row_to_message(r) for r in rows]
    return jsonify({"status": "ok", "messages": messages})


@app.route("/api/messages/<int:msg_id>", methods=["GET"])
def get_message(msg_id: int):
    """
    Get a single post (and optionally its comments) for slug views.

    Query:
      include_comments=1 : also return comments where parent_id = msg_id

    Response:
      {
        status: "ok",
        message: { ...root post... },
        comments: [ ...optional comments... ],
        comment_count: <int>
      }
    """
    include_comments = request.args.get("include_comments", "0") == "1"

    conn = get_db()
    cur = conn.cursor()

    # root post
    cur.execute(
        "SELECT id, txid, output_index, amount_zats, parent_id, "
        "created_at, text, likes "
        "FROM messages WHERE id = ?",
        (msg_id,),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({"status": "error", "error": "not_found"}), 404

    message = row_to_message(row)

    # comment count
    cur.execute("SELECT COUNT(*) AS c FROM messages WHERE parent_id = ?", (msg_id,))
    cc_row = cur.fetchone()
    comment_count = cc_row["c"] if cc_row else 0

    comments = []
    if include_comments:
        cur.execute(
            "SELECT id, txid, output_index, amount_zats, parent_id, "
            "created_at, text, likes "
            "FROM messages WHERE parent_id = ? ORDER BY id ASC",
            (msg_id,),
        )
        comments = [row_to_message(r) for r in cur.fetchall()]

    conn.close()

    return jsonify(
        {
            "status": "ok",
            "message": message,
            "comments": comments,
            "comment_count": comment_count,
        }
    )


# --------------------------------------------------------------------------
# API – likes
# --------------------------------------------------------------------------
@app.route("/api/messages/<int:msg_id>/like", methods=["POST"])
def like_message(msg_id):
    """
    Toggle like for (msg_id, user_id).
    Body: { "user_id": "some-stable-id" }
    Returns: { status: "ok", liked: true/false, likes: <count> }
    """
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    if not user_id:
        return jsonify({"status": "error", "error": "missing_user_id"}), 400

    conn = get_db()
    cur = conn.cursor()

    # does this user already like it?
    cur.execute(
        "SELECT 1 FROM message_likes WHERE message_id = ? AND user_id = ?",
        (msg_id, user_id),
    )
    row = cur.fetchone()

    if row:
        # already liked: UNLIKE
        cur.execute(
            "DELETE FROM message_likes WHERE message_id = ? AND user_id = ?",
            (msg_id, user_id),
        )
        cur.execute(
            "UPDATE messages SET likes = COALESCE(likes, 0) - 1 "
            "WHERE id = ? AND likes > 0",
            (msg_id,),
        )
        liked = False
    else:
        # not yet liked: LIKE
        cur.execute(
            """
            INSERT OR IGNORE INTO message_likes (message_id, user_id, created_at)
            VALUES (?, ?, ?)
            """,
            (msg_id, user_id, datetime.utcnow().isoformat(timespec="seconds") + "Z"),
        )
        cur.execute(
            "UPDATE messages SET likes = COALESCE(likes, 0) + 1 "
            "WHERE id = ?",
            (msg_id,),
        )
        liked = True

    # read fresh total
    cur.execute(
        "SELECT COALESCE(likes, 0) AS likes FROM messages WHERE id = ?",
        (msg_id,),
    )
    likes_row = cur.fetchone()
    conn.commit()
    conn.close()

    if not likes_row:
        return jsonify({"status": "error", "error": "not_found"}), 404

    return jsonify(
        {
            "status": "ok",
            "liked": liked,
            "likes": likes_row["likes"],
        }
    )


# --------------------------------------------------------------------------
# Misc
# --------------------------------------------------------------------------
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    # Only HTTP from Nginx / Cloudflare
    app.run(host="127.0.0.1", port=8080, debug=True)
