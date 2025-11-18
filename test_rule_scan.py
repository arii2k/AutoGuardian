# test_rule_scan.py
from services.scanner import scan_emails

# 1️⃣ Test email that should match a rule in rules.json
emails = [{
    "From": "Google <no-reply@accounts.google.com>",
    "Subject": "Your Google Account has been compromised!",
    "Date": "Sun, 19 Oct 2025 23:40:00 +0000",
    "id": "test001"
}]

# 2️⃣ Run the scanner
results = scan_emails(emails)

# 3️⃣ Print results clearly
for r in results:
    email = r["email"]
    print("\n--- Scan Result ---")
    print("Subject:", email.get("Subject"))
    print("From:", email.get("From"))
    print("Date:", email.get("Date"))
    print("Matched Rules:", r.get("matched_rules", []))
    print("Score:", r.get("score"))
    print("Memory Alert:", r.get("memory_alert"))
    print("Community Alert:", r.get("community_alert"))
    print("Quarantine:", r.get("quarantine"))
    print("---------------------------")
