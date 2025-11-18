# backend/test_scan1.py
import os
import sys
from services.gmail_service import scan_and_label_gmail, export_to_csv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def main():
    print("🔹 Starting test scan of Gmail with Hybrid AI/NLP phishing detection...\n")

    # Scan 10 most recent emails (adjust max_results if needed)
    scanned_emails = scan_and_label_gmail(max_results=10, user_email="me@example.com", user_id=1)

    print(f"\n✅ Scan complete. {len(scanned_emails)} emails processed.\n")

    # Print a summary table
    for i, email in enumerate(scanned_emails, start=1):
        print(f"{i}. Subject: {email['email'].get('Subject')}")
        print(f"   From: {email['email'].get('From')}")
        print(f"   Score: {email.get('score')}")
        print(f"   Risk Level: {email.get('risk_level')}")
        print(f"   Quarantine: {email.get('quarantine')}")
        print(f"   Community Alert: {email.get('community_alert')}")
        print(f"   Explanations: {email.get('explanations')}\n")

    # Export to CSV for dashboard/testing
    export_to_csv(file_path=os.path.join("data", "test_scan_history.csv"))
    print("✅ CSV export done: data/test_scan_history.csv")
    print("✅ JSON backup already saved: data/scan_history.json")

if __name__ == "__main__":
    main()
