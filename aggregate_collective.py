import sqlite3
from collections import Counter
from datetime import datetime

DB_PATH = 'autoguardian.db'

# ---------------------------
# Connect to DB
# ---------------------------
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# ---------------------------
# Ensure collective_metrics table has correct schema
# ---------------------------
cursor.execute("""
CREATE TABLE IF NOT EXISTS collective_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    email_id TEXT,
    sender TEXT,
    subject TEXT,
    score INTEGER,
    risk_level TEXT,
    quarantine INTEGER,
    timestamp TEXT,
    matched_rules TEXT DEFAULT ''
)
""")
conn.commit()

# ---------------------------
# Fetch all scan history
# ---------------------------
cursor.execute("SELECT sender, subject, matched_rules, score, timestamp FROM scan_history")
rows = cursor.fetchall()

# ---------------------------
# Aggregation counters
# ---------------------------
top_senders = Counter()
top_rules = Counter()
high_risk_trend = {}

# ---------------------------
# Process rows
# ---------------------------
for sender, subject, matched_rules, score, timestamp in rows:
    # Count risky senders (score >=7)
    if score >= 7 and sender:
        top_senders[sender] += 1

    # Count matched rules
    if matched_rules:
        rules_list = matched_rules.split(',')  # comma-separated
        for rule in rules_list:
            top_rules[rule.strip()] += 1

    # High-risk trend per day
    if score >= 7:
        date_str = timestamp.split('T')[0]  # YYYY-MM-DD
        high_risk_trend[date_str] = high_risk_trend.get(date_str, 0) + 1

# ---------------------------
# Print analytics
# ---------------------------
print("\nTop risky senders:")
for sender, count in top_senders.most_common(10):
    print(sender, count)

print("\nTop matched rules:")
for rule, count in top_rules.most_common(10):
    print(rule, count)

print("\nHigh-risk trend over time:")
for date, count in sorted(high_risk_trend.items()):
    print(date, count)

# ---------------------------
# Store aggregated data in collective_metrics
# ---------------------------
for sender, subject, matched_rules, score, timestamp in rows:
    # Risk classification
    if score >= 7:
        risk_level = 'High'
    elif score >= 4:
        risk_level = 'Medium'
    else:
        risk_level = 'Low'

    cursor.execute("""
        INSERT INTO collective_metrics
        (user_id, email_id, sender, subject, score, risk_level, quarantine, timestamp, matched_rules)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        0,                  # user_id = 0 (cross-user)
        None,               # email_id unknown
        sender,
        subject,
        score,
        risk_level,
        1 if risk_level=='High' else 0,  # quarantine high-risk
        datetime.now().isoformat(),
        matched_rules or ''
    ))

conn.commit()
conn.close()
print("\n✅ Cross-user aggregation complete and saved to collective_metrics.")
