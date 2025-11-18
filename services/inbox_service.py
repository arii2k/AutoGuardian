# services/inbox_service.py — store per-user inbox configuration
import os
import sqlite3
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "autoguardian.db")


def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_tables():
    conn = _get_conn()
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS user_inboxes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            provider TEXT NOT NULL,         -- 'imap' or 'gmail'
            imap_host TEXT,
            imap_username TEXT,
            imap_password TEXT,             -- TODO: encrypt before production
            imap_port INTEGER,
            use_ssl INTEGER DEFAULT 1,
            status TEXT,
            last_scan TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    # one inbox per user (for now)
    c.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_user_inboxes_user ON user_inboxes(user_id)"
    )
    conn.commit()
    conn.close()


def get_inbox_for_user(user_id: int):
    ensure_tables()
    conn = _get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM user_inboxes WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def upsert_imap_inbox(user_id: int, host: str, username: str, password: str, port: int, use_ssl: bool):
    """
    Create or update a single IMAP inbox for this user.
    NOTE: password is stored in plaintext for now — do NOT use in prod like this.
    """
    ensure_tables()
    conn = _get_conn()
    c = conn.cursor()
    # delete any existing inbox for this user
    c.execute("DELETE FROM user_inboxes WHERE user_id=?", (user_id,))
    c.execute(
        """
        INSERT INTO user_inboxes (
            user_id, provider, imap_host, imap_username,
            imap_password, imap_port, use_ssl, status, last_scan
        ) VALUES (?, 'imap', ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            host.strip(),
            username.strip(),
            password,
            int(port),
            1 if use_ssl else 0,
            "connected",
            None,
        ),
    )
    conn.commit()
    conn.close()


def update_inbox_last_scan(user_id: int, status: str = "ok"):
    ensure_tables()
    conn = _get_conn()
    c = conn.cursor()
    c.execute(
        """
        UPDATE user_inboxes
        SET last_scan=?, status=?
        WHERE user_id=?
        """,
        (datetime.utcnow().isoformat(), status, user_id),
    )
    conn.commit()
    conn.close()


def disconnect_inbox(user_id: int):
    ensure_tables()
    conn = _get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM user_inboxes WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()
