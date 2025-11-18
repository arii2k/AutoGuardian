# test_scan_gmail.py
from services.gmail_service import scan_and_label_gmail
from services.scanner import scan_emails
from datetime import datetime
import json
import os

# Set max number of emails to fetch
MAX_RESULTS = 5

# Fetch emails from Gmail
emails = scan_and_label_gmail(max_results=MAX_RESULTS)

# Path to your rules file
RULES_FILE = os.path.join(os.path.dirname(__file__), "test_rules.json")

# Scan emails with rules
results = scan_emails(emails, rules_file=RULES_FILE)

# Save results to JSON file for inspection
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "test_scan_output.json")
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f"Scan complete! Results saved to {OUTPUT_FILE}")
print(json.dumps(results, indent=2, ensure_ascii=False))
