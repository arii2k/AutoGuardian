import json
from datetime import datetime
from services.scanner import scan_emails

# Sample email (use one from your scan_history to be realistic)
sample_email = {
    "Date": "Thu, 16 Oct 2025 18:19:45 GMT",
    "Subject": "Your Google Account was recovered successfully",
    "From": "Google <no-reply@accounts.google.com>",
    "id": "199ee3fdd9c0a7f2"
}

# run scanner on that single email using our test rules file
results = scan_emails([sample_email], rules_file="test_rules.json")

# pretty-print results
print(json.dumps(results, indent=2, ensure_ascii=False))
