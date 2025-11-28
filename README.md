# **Zcash Forum — Refactored Version**

A cleanly refactored version of the Zcash memo-based forum, split into a proper **backend** (Flask + SQLite) and **frontend** (HTML/CSS/JS modules).
The UI is a modern, modular, component-based design.

---

# **📁 Project Structure**

```
GITHUB/
│
├── backend/
│   ├── app.py                # Flask app (API + HTML routes)
│   ├── config.py             # Paths + constants
│   ├── db.py                 # SQLite init + helpers
│   ├── scanner.py            # Imports memos from UFVK (optional)
│   ├── forum_messages.db     # SQLite DB (autocreated / populated by scanner)
│   │
│   ├── utils/
│   │   ├── wallet_reader.py  # Runs read_view_key.py + zcash-devtool
│   │   ├── zcash_parser.py   # Parses transaction text
│   │   └── __init__.py
│   │
│   ├── forum_wallets/        # Auto-created by scanner
│   └── forum_exports/        # Auto-created by scanner
│
├── frontend/
│   ├── index.html            # UI shell
│   └── assets/
│       ├── css/forum.css     # Full custom styles
│       └── js/
│           ├── main.js
│           ├── constants.js
│           ├── utils/
│           │   ├── dom.js
│           │   └── format.js
│           ├── hooks/
│           │   ├── useComposer.js
│           │   └── useFeed.js
│           └── components/
│               └── messageCard.js
│
└── README.md
```

---

# **🚀 Running the Project Locally**

## **1. Install Python dependencies**

This project only requires Flask + standard library:

```bash
pip install flask flask-cors
```

---

## **2. Start the backend server**

From the **project root**, run:

```bash
python -m backend.app
```

This automatically:

* Initializes the `forum_messages.db` database
* Serves `index.html` from the `frontend/` folder
* Serves assets from `frontend/assets/`
* Provides all API routes under `/api/...`

Then open:

```
http://127.0.0.1:5003/
```

---

# ** (Optional) Importing Posts via Scanner**

The Community Feed is empty until data is imported.

To populate the SQLite DB, run:

```bash
python -m backend.scanner
```

### **However…**

The scanner depends on a large external binary:
✔ **zcash-devtool**

Because of its size, it is **NOT included** in this repo.

Without it:

* `backend.scanner` will fail with
  `zcash-devtool path not found`
* `forum_messages.db` remains empty
* UI loads perfectly, but the **feed shows 0 posts**

### If someone wants real posts:

They must:

1. Download `zcash-devtool`
2. Place it inside:

```
backend/zcash-devtool/
```

3. Set environment variables:

```bash
export FORUM_UFVK=...
export FORUM_BIRTHDAY=...
```

4. Run:

```bash
python -m backend.scanner
```

If you do not need live data (just UI review), ignore this section.

---

### Key frontend files for reviewing:

| File                                           | Purpose                                      |
| ---------------------------------------------- | -------------------------------------------- |
| `frontend/index.html`                          | Page structure + component sections          |
| `frontend/assets/css/forum.css`                | Full styling for the entire UI               |
| `frontend/assets/js/main.js`                   | Entry point, binds composer + feed           |
| `frontend/assets/js/hooks/useComposer.js`      | Zcash URI + QR generation                    |
| `frontend/assets/js/hooks/useFeed.js`          | Fetches posts, handles search + live updates |
| `frontend/assets/js/components/messageCard.js` | Renders individual posts                     |

---

