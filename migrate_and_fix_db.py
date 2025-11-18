#!/usr/bin/env python3
import sqlite3
import os
from datetime import datetime
import json

# ---------------------------
# Paths
# ---------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "autoguardian.db")

os.makedirs(DATA_DIR, exist_ok=True)

# ---------------------------
# Connect to DB
# ---------------------------
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# ---------------------------
# 1️⃣ Add missing user_id to scanned_emails
# ---------------------------
cursor.execute("PRAGMA table_info(scanned_emails);")
columns = [col[1] for col in cursor.fetchall()]
if "user_id" not in columns:
    cursor.execute("ALTER TABLE scanned_emails ADD COLUMN user_id INTEGER DEFAULT 0")
    print("✅ Added user_id to scanned_emails")
else:
    print("ℹ user_id already exists in scanned_emails")

# ---------------------------
# 2️⃣ Ensure matched_rules exists in all tables
# ---------------------------
tables_to_check = ["scan_history", "collective_metrics", "scanned_emails"]
for table in tables_to_check:
    cursor.execute(f"PRAGMA table_info({table});")
    existing_cols = [col[1] for col in cursor.fetchall()]
    if "matched_rules" not in existing_cols:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN matched_rules TEXT DEFAULT ''")
        print(f"✅ Added matched_rules to {table}")
    else:
        print(f"ℹ matched_rules already exists in {table}")

# ---------------------------
# 3️⃣ Ensure risk_level exists in scan_history
# ---------------------------
cursor.execute("PRAGMA table_info(scan_history);")
existing_cols = [col[1] for col in cursor.fetchall()]
if "risk_level" not in existing_cols:
    cursor.execute("ALTER TABLE scan_history ADD COLUMN risk_level TEXT DEFAULT 'Safe'")
    print("✅ Added risk_level to scan_history")
else:
    print("ℹ risk_level already exists in scan_history")

# ---------------------------
# 4️⃣ Populate collective_metrics from scan_history
# ---------------------------
cursor.execute("""
    SELECT id, user_id, sender, subject, score, quarantine, timestamp, matched_rules
    FROM scan_history
""")
rows = cursor.fetchall()
inserted = 0

for r in rows:
    email_id = r[0]
    user_id = r[1] or 0
    sender = r[2] or ""
    subject = r[3] or ""
    score = r[4] or 0
    quarantine = r[5] or 0
    timestamp = r[6] or datetime.now().isoformat()
    matched_rules = r[7] or ""

    # Determine risk level
    risk_level = "High" if score >= 7 else "Medium" if score >= 4 else "Low"

    # Avoid duplicates
    cursor.execute("SELECT id FROM collective_metrics WHERE email_id=?", (email_id,))
    if not cursor.fetchone():
        cursor.execute("""
            INSERT INTO collective_metrics
            (user_id, email_id, sender, subject, score, risk_level, quarantine, timestamp, matched_rules)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, email_id, sender, subject, score, risk_level, quarantine, timestamp, matched_rules))
        inserted += 1

conn.commit()
print(f"✅ Populated collective_metrics from scan_history ({inserted} new rows)")

# ---------------------------
# Done
# ---------------------------
conn.close()
print("🎉 Database migration and fix complete!")
