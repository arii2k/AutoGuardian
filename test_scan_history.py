import json
from datetime import datetime

file_path = "scan_history.json"

try:
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
except json.JSONDecodeError:
    data = []

new_entry = {
    "timestamp": datetime.now().isoformat(),
    "email": {
        "Date": "Now",
        "From": "test@example.com",
        "Subject": "Test Email",
        "id": "TEST123"
    },
    "score": 3,
    "matched_rules": [],
    "memory_alert": None,
    "community_alert": None,
    "quarantine": False
}

data.append(new_entry)

with open(file_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)

print("Scan history updated successfully!")
