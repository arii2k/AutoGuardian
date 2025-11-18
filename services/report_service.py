# services/report_service.py
import json
import os
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
SCAN_FILE = os.path.join(DATA_DIR, "scan_history.json")
REPORT_FILE = os.path.join(DATA_DIR, "weekly_report.txt")

def generate_report():
    if not os.path.exists(SCAN_FILE):
        print("No scan history found.")
        return

    with open(SCAN_FILE, "r", encoding="utf-8") as f:
        items = json.load(f)

    high = [i for i in items if i.get("score",0) >= 5 or i.get("quarantine")]
    lines = []

    # Use timezone-aware datetime
    lines.append(f"Report generated: {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"Total scans: {len(items)}")
    lines.append(f"High/quarantined: {len(high)}")
    lines.append("")

    for r in high:
        email = r.get("email", {})
        lines.append(f"- {email.get('Date','N/A')} | {email.get('From','N/A')} | {email.get('Subject','N/A')} | "
                     f"score={r.get('score',0)} | quarantine={r.get('quarantine',False)} | "
                     f"memory_alert={r.get('memory_alert')} | community_alert={r.get('community_alert')}")

    try:
        with open(REPORT_FILE, "w", encoding="utf-8") as out:
            out.write("\n".join(lines))
        print(f"Report saved to {REPORT_FILE}")
    except Exception as e:
        print("Failed to save report:", e)

if __name__ == "__main__":
    generate_report()
