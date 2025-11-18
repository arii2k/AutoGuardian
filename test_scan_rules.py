import json
from services.scanner import scan_emails

emails = [
    {
        "Date": "Fri, 17 Oct 2025 08:04:53 -0600",
        "From": "Banka Raiffeisen <news@sf.email.raiffeisen-kosovo.com>",
        "Subject": "Raiffeisen Bank Kosovo Mobile: Shkarko versionin më të fundit!",
        "id": "TEST_MEMORY"
    },
    {
        "Date": "Fri, 17 Oct 2025 18:27:08 +0200",
        "From": "\"zaposli.me\" <noreply@zaposli.me>",
        "Subject": "Novi poslovi na Zaposli.ME - 2025-10-17",
        "id": "TEST_COMMUNITY"
    },
    {
        "Date": "Thu, 16 Oct 2025 18:19:45 GMT",
        "From": "Google <no-reply@accounts.google.com>",
        "Subject": "Your Google Account was recovered successfully",
        "id": "TEST_HIGH"
    }
]

# Run the scan
results = scan_emails(emails, rules_file="test_rules.json")

# Save results to scan_history.json for dashboard
with open("scan_history.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)

print("Test scan complete! Results saved to scan_history.json")
print(json.dumps(results, indent=2, ensure_ascii=False))
