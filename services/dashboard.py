from flask import Flask, jsonify
import sqlite3, json

app = Flask(__name__)

@app.route("/api/dashboard-data")
def dashboard_data():
    conn = sqlite3.connect("data/autoguardian.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Fetch last 10 scans
    cur.execute("""
        SELECT subject, sender, risk_level, score, ai_details, date
        FROM scan_history
        ORDER BY id DESC
        LIMIT 10
    """)
    rows = cur.fetchall()
    
    data = []
    for row in rows:
        try:
            ai_json = json.loads(row["ai_details"]) if row["ai_details"] else {}
        except:
            ai_json = {}
        data.append({
            "subject": row["subject"],
            "sender": row["sender"],
            "risk_level": row["risk_level"],
            "score": row["score"],
            "ai_reasons": ai_json.get("ensemble_reasons", []),
            "date": row["date"]
        })

    return jsonify({
        "recent_scans": data,
        "behavior": {
            "behavior_risk": 0.0,
            "risky_clicks_30d": 0,
            "risky_clicks_7d": 0,
            "total_clicks_30d": 0
        },
        "collective_stats": {
            "records": data
        }
    })
