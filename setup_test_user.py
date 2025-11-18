# setup_test_user.py (fixed for Subscription object)
import os
import sqlite3
from services.paddle_service import activate_mock_subscription, create_mock_subscription
from services.gmail_service import start_user_auto_scan
from services.device_utils import get_device, optimize_torch_for_device

# ---------------------------
# Paths
# ---------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "autoguardian.db")
os.makedirs(DATA_DIR, exist_ok=True)

# ---------------------------
# Device Setup (for ML scoring)
# ---------------------------
DEVICE = get_device()
optimize_torch_for_device(DEVICE)
print(f"🧠 Device set to: {DEVICE}")

# ---------------------------
# Ensure test user exists in DB
# ---------------------------
def ensure_test_user(email="test@example.com", username="TestUser"):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
    )
    conn.commit()

    # Check if user exists
    c.execute("SELECT id FROM users WHERE email=?", (email,))
    row = c.fetchone()
    if row:
        user_id = row[0]
        print(f"✅ User {email} already exists with ID {user_id}")
    else:
        # Insert user with dummy password hash
        c.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (username, email, "dummyhash"),
        )
        conn.commit()
        user_id = c.lastrowid
        print(f"✅ Created test user {email} with ID {user_id}")

    conn.close()
    return user_id

# ---------------------------
# Ensure subscription is active
# ---------------------------
def ensure_subscription(email):
    sub = create_mock_subscription(email)
    # Access attributes via dot notation
    activate_mock_subscription(email, sub.checkout_id)

# ---------------------------
# Start background Gmail scanner
# ---------------------------
def start_scanner_for_user(user_id, email):
    scheduler = start_user_auto_scan(user_id, email, poll_interval=60)
    return scheduler

# ---------------------------
# Run setup
# ---------------------------
if __name__ == "__main__":
    user_email = "test@example.com"
    user_id = ensure_test_user(user_email)
    ensure_subscription(user_email)
    start_scanner_for_user(user_id, user_email)
    print(f"🟢 Setup complete. Background scanner started for {user_email}.")
