# migrate_db.py
import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "autoguardian.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

def migrate_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # scan_history table
    c.execute('''
        CREATE TABLE IF NOT EXISTS scan_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email_id TEXT,
            date TEXT,
            sender TEXT,
            subject TEXT,
            score INTEGER,
            matched_rules TEXT,
            memory_alert TEXT,
            community_alert TEXT,
            quarantine INTEGER DEFAULT 0,
            timestamp TEXT,
            user_id INTEGER
        )
    ''')

    # collective_metrics table
    c.execute('''
        CREATE TABLE IF NOT EXISTS collective_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            email_id TEXT,
            score INTEGER,
            risk_level TEXT,
            quarantine INTEGER DEFAULT 0,
            timestamp TEXT
        )
    ''')

    # Add missing column if older table exists
    try:
        c.execute("ALTER TABLE collective_metrics ADD COLUMN quarantine INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass  # column already exists

    conn.commit()
    conn.close()
    print("✅ Database migration complete.")

if __name__ == "__main__":
    migrate_db()
