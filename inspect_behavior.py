import sqlite3
import os

DB_PATH = os.path.join("data", "autoguardian.db")
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

print("✅ Connected to:", DB_PATH)

print("\n=== Tables in DB ===")
for row in c.execute("SELECT name FROM sqlite_master WHERE type='table';"):
    print(" -", row[0])

# Check contents of existing behavior tables
print("\n=== behavior_log (first 5) ===")
try:
    for row in c.execute("SELECT * FROM behavior_log LIMIT 5;"):
        print(row)
except Exception as e:
    print("⚠️ behavior_log missing or empty:", e)

print("\n=== behavior_user_stats (first 5) ===")
try:
    for row in c.execute("SELECT * FROM behavior_user_stats LIMIT 5;"):
        print(row)
except Exception as e:
    print("⚠️ behavior_user_stats missing or empty:", e)

conn.close()
