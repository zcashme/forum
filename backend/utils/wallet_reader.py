import os
import sys
import subprocess
import logging

from ..config import (
    FORUM_UFVK,
    FORUM_BIRTHDAY,
    FORUM_NAME,
    EXPORTS_DIR,
    WALLETS_DIR,
    forum_wallet_slug,
)

log = logging.getLogger(__name__)

def run_read_view_key() -> str:
    slug = forum_wallet_slug()
    wallet_dir = os.path.join(WALLETS_DIR, slug)
    output_prefix = os.path.join(EXPORTS_DIR, f"{slug}_txs")
    txt_path = output_prefix + ".txt"

    if os.path.exists(txt_path):
        os.remove(txt_path)

    cmd = [
        sys.executable,
        os.path.join(os.path.dirname(__file__), "..", "read_view_key.py"),
        "--key", FORUM_UFVK,
        "--birthday", str(FORUM_BIRTHDAY),
        "--wallet-dir", wallet_dir,
        "--name", FORUM_NAME,
        "--output-prefix", output_prefix,
    ]

    log.info("Running read_view_key.py for forum wallet")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        log.error("read_view_key.py failed: %s", result.stderr)
        raise RuntimeError("read_view_key failed")

    if not os.path.exists(txt_path):
        raise RuntimeError("Output file not created")

    with open(txt_path, "r", encoding="utf-8") as f:
        return f.read()
