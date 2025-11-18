# train_model.py
import os
import json
from services.local_nlp import train_local_model

# ---------------------------
# Paths
# ---------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
SCAN_HISTORY_FILE = os.path.join(DATA_DIR, "scan_history.json")

# ---------------------------
# Load scan history safely
# ---------------------------
if os.path.exists(SCAN_HISTORY_FILE):
    with open(SCAN_HISTORY_FILE, "r", encoding="utf-8") as f:
        scan_history = json.load(f)
else:
    scan_history = []

# ---------------------------
# Prepare training data
# ---------------------------
emails = []
labels = []

for item in scan_history:
    email_obj = item.get("email", {})
    subject = email_obj.get("Subject", "")
    sender = email_obj.get("From", "")
    content = f"{subject} {sender}"
    emails.append(content)

    risk_level = item.get("risk_level", "Safe")
    # High = phishing, others = safe
    labels.append(1 if risk_level == "High" else 0)

# ---------------------------
# Check for at least 2 classes
# ---------------------------
if len(set(labels)) < 2:
    print("⚠️ Not enough classes in scan_history.json. Adding synthetic phishing samples for training...")
    synthetic_phishing = [
        "Urgent: Your account has been compromised",
        "Click here to reset your password immediately",
        "Verify your billing information now",
        "Action required: Suspicious login detected",
        "You won a prize! Click to claim"
    ]
    emails += synthetic_phishing
    labels += [1] * len(synthetic_phishing)

# ---------------------------
# Train the local NLP model
# ---------------------------
if emails:
    train_local_model(emails, labels)
else:
    print("⚠️ No emails found to train on. Please make sure scan_history.json has data.")
