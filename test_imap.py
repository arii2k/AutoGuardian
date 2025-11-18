from services.imap_service import scan_and_tag_imap

if __name__ == "__main__":
    results = scan_and_tag_imap(
        host="imap.yourprovider.com",
        username="you@example.com",
        password="YOUR_IMAP_APP_PASSWORD",
        user_email="you@example.com",
        user_id=1,
        days=2,
        max_results=20,
    )
    print(f"Scanned {len(results)} emails")
    for r in results:
        print(r["email"]["Subject"], "=>", r["risk_level"])
