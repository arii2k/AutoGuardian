import requests
import json

url = "http://127.0.0.1:5000/api/dashboard-data"

try:
    resp = requests.get(url)
    data = resp.json()
    print(json.dumps(data, indent=2))
except Exception as e:
    print("❌ Error connecting to API:", e)
