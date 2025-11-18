import sqlite3
from datetime import datetime
import json

DB_PATH = "data/autoguardian.db"  # adjust if your DB path is different

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# 1️⃣ Add missing columns safely
try:
    c.execute("ALTER TABLE collective_metrics ADD COLUMN matched_rules TEXT DEFAULT ''")
    print("✅ matched_rules column added")
except sqlite3.OperationalError:
    print("⚠️ matched_rules column already exists")

# 2️⃣ Optional: Add sender and subject columns if missing
for col in ["sender", "subject"]:
    try:
        c.execute(f"ALTER TABLE collective_metrics ADD COLUMN {col} TEXT DEFAULT ''")
        print(f"✅ {col} column added")
    except sqlite3.OperationalError:
        print(f"⚠️ {col} column already exists")

# 3️⃣ Re-populate collective_metrics from scan_history
c.execute("SELECT id, sender, subject, score, matched_rules, quarantine, timestamp FROM scan_history")
rows = c.fetchall()

for r in rows:
    email_id = r[0]
    sender = r[1] or ""
    subject = r[2] or ""
    score = r[3] or 0
    matched_rules = r[4] or ""
    quarantine = r[5] or 0
    timestamp = r[6] or datetime.now().isoformat()

    risk_level = 'High' if score >= 7 else 'Medium' if score >= 4 else 'Low'

    # Check if already exists to avoid duplicates
    c.execute("SELECT id FROM collective_metrics WHERE email_id=?", (email_id,))
    if not c.fetchone():
        c.execute("""
            INSERT INTO collective_metrics
            (user_id, email_id, sender, subject, score, risk_level, quarantine, timestamp, matched_rules)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (0, email_id, sender, subject, score, risk_level, quarantine, timestamp, matched_rules))

conn.commit()
conn.close()
print("✅ collective_metrics fixed and populated!")
