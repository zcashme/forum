import os
import hashlib

# backend/app.py -> backend dir
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

# project root is one level above backend/
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)

# frontend directory (where assets/ lives)
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")

DB_PATH = os.path.join(BACKEND_DIR, "forum_messages.db")
EXPORTS_DIR = os.path.join(BACKEND_DIR, "forum_exports")
WALLETS_DIR = os.path.join(BACKEND_DIR, "forum_wallets")

os.makedirs(EXPORTS_DIR, exist_ok=True)
os.makedirs(WALLETS_DIR, exist_ok=True)

FORUM_UFVK = os.environ.get("FORUM_UFVK", "uview1aljhpegnrg36ydkmvcqfqtertmcj32qkze0ymx8g67yacahutttshxnz9huttvze6zv0l5xnmu7skjs228adyqje3f2qk8yyhpx8v5pk87wqxarkkmmcwqd7kv0dgufe5nj26ks2d8lhl328qm8jqzz2c3uu76yu6vrftluky68t965csas8daa6dpafvlrjmj7s3qc5hfwcudjl55m3wcdwdg0rdspa5zk3zpp2zk84ze7sw28asnj5d62c8kfnfuftq305dv9mtkr4hjrx8mfh6cgxz8f9xmr6v8n7qed5s3v6dy3zuw5hlgf9nl5ew9h4sfcae3auzjs3tflmee6xqyeqvusjzxnjwd8jguqhdyy6a5syvy8fr7qtx04ktfuka55s0s3crkd3ukygh5wys50pjlhrdskxf9772p0njh0pfl7ddvl8zs5cpser52q0d3mcvprkeal6zgzs66ds8e988u6pf09uz3unnhxzc6qz7qm2d080")
FORUM_BIRTHDAY = int(os.environ.get("FORUM_BIRTHDAY", "3000000"))
FORUM_NAME = "forum.zcash.me"

REPLY_PREFIX = "ZFORUM:reply:"

def forum_wallet_slug() -> str:
    return "forum_" + hashlib.sha256(FORUM_UFVK.encode("utf-8")).hexdigest()[:16]


