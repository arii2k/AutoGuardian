# test_scan_db.py
from services.gmail_service import scan_and_label_gmail
from services.models import ScannedEmail, db
from datetime import datetime

def save_to_db(scanned_results):
    for r in scanned_results:
        email = r['email']
        record = ScannedEmail(
            timestamp=datetime.now(),
            sender=email.get('From'),
            subject=email.get('Subject'),
            score=r.get('score', 0),
            matched_rules=r.get('matched_rules', []),
            memory_alert=r.get('memory_alert'),
            community_alert=r.get('community_alert'),
            quarantine=r.get('quarantine', False)
        )
        db.add(record)
    db.commit()
    print(f"✅ Saved {len(scanned_results)} emails to DB.")

if __name__ == "__main__":
    print("🔹 Scanning Gmail and saving to DB...")
    results = scan_and_label_gmail(max_results=5)  # scan last 5 emails
    save_to_db(results)
    print("🔹 Done.")
