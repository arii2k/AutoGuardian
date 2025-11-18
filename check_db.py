import sqlite3, json

DB_PATH = "data/autoguardian.db"

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

print("=== Last 5 scan_history entries ===")
for row in c.execute("SELECT score, ai_details FROM scan_history ORDER BY id DESC LIMIT 5"):
    score, ai_details = row
    try:
        ai_json = json.loads(ai_details) if ai_details else {}
    except Exception:
        ai_json = {}
    print(f"Score: {score} | AI: {ai_json}")

conn.close()
