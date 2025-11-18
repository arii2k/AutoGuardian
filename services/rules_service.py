import requests
import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
RULES_FILE = os.path.join(DATA_DIR, "rules.json")

OPENPHISH_URL = "https://openphish.com/feed.txt"
URLHAUS_URL = "https://urlhaus.abuse.ch/downloads/csv_online/"

def fetch_openphish():
    try:
        r = requests.get(OPENPHISH_URL)
        urls = r.text.strip().split("\n")
        return [{"pattern": url, "score": 5, "sources": ["openphish"], "description": "OpenPhish URL"} for url in urls]
    except Exception as e:
        print("Failed to fetch OpenPhish:", e)
        return []

def fetch_urlhaus():
    try:
        r = requests.get(URLHAUS_URL)
        lines = r.text.strip().split("\n")[1:]  # skip header
        urls = [line.split(",")[1] for line in lines if line]
        return [{"pattern": url, "score": 5, "sources": ["urlhaus"], "description": "URLhaus URL"} for url in urls]
    except Exception as e:
        print("Failed to fetch URLhaus:", e)
        return []

def update_rules():
    rules = []
    rules += fetch_openphish()
    rules += fetch_urlhaus()
    # Merge with local rules
    if os.path.exists(RULES_FILE):
        try:
            with open(RULES_FILE, "r", encoding="utf-8") as f:
                rules += json.load(f)
        except:
            pass
    with open(RULES_FILE, "w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2)
    return rules

if __name__ == "__main__":
    rules = update_rules()
    print(f"Rules updated: {len(rules)}")
