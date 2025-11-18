from services.scanner import scan_emails
import json

# Test emails (safe examples)
test_emails = [
    {
        "id": "TEST_RULES",
        "Date": "2025-10-19T13:00:00",
        "From": "google@test.com",
        "Subject": "Your Google Account was recovered successfully"
    },
    {
        "id": "TEST_COMMUNITY",
        "Date": "2025-10-19T12:45:00",
        "From": "community@test.com",
        "Subject": "Community Alert Email"
    }
]

# Run scanner using your rules.json and community_memory.json
results = scan_emails(test_emails, rules_file="rules.json", community_file="community_memory.json")

# Print results
print(json.dumps(results, indent=2))
