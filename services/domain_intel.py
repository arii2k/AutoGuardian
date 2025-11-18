import requests
import datetime

def domain_reputation(domain):
    try:
        r = requests.get(f"https://ipapi.co/{domain}/json/", timeout=5)
        data = r.json()
        creation = data.get("creation_date")
        if creation:
            age_days = (datetime.datetime.utcnow() - datetime.datetime.fromisoformat(creation)).days
            if age_days < 30:
                return True, f"Domain age suspicious ({age_days} days old)"
    except:
        pass
    return False, ""
