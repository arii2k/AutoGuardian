import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "autoguardian.db")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Create users table if it doesn't exist
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")

print("✅ users table created (if it didn't exist)")

conn.commit()
conn.close()
