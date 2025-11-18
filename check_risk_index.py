import sqlite3
import json

DB_PATH = "data/autoguardian.db"

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

print("=== Average hybrid_score from scan_history ===")
rows = c.execute("SELECT ai_details FROM scan_history WHERE ai_details IS NOT NULL").fetchall()

scores = []
for (ai_json,) in rows:
    try:
        data = json.loads(ai_json)
        val = float(data.get("hybrid_score", 0))
        if val > 0:
            scores.append(val)
    except Exception:
        pass

if scores:
    avg_score = sum(scores) / len(scores)
    print(f"Found {len(scores)} entries with hybrid_score > 0")
    print(f"Average hybrid_score: {avg_score:.2f}")
else:
    print("No valid hybrid_score values found in database.")

print("\n=== Sample entries ===")
for (ai_json,) in rows[-5:]:
    print(ai_json[:200])
