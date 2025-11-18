import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "autoguardian.db")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Add user_id column if it doesn't exist
cursor.execute("PRAGMA table_info(scanned_emails);")
columns = [col[1] for col in cursor.fetchall()]

if "user_id" not in columns:
    cursor.execute("ALTER TABLE scanned_emails ADD COLUMN user_id INTEGER;")
    print("✅ user_id column added to scanned_emails")
else:
    print("ℹ️ user_id column already exists")

conn.commit()
conn.close()
