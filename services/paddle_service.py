# services/paddle_service.py
import os
import json
import uuid
from datetime import datetime, timezone, timedelta

# ---------------------------
# Paths & Setup
# ---------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

SUBSCRIPTIONS_FILE = os.path.join(DATA_DIR, "subscriptions.json")


# ---------------------------
# Subscription Object
# ---------------------------
class Subscription:
    def __init__(self, checkout_id, subscription_id=None, plan_id="mock-plan-monthly",
                 active=False, created_at=None, activated_at=None, expires_at=None):
        self.checkout_id = checkout_id
        self.subscription_id = subscription_id
        self.plan_id = plan_id
        self.active = active
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()
        self.activated_at = activated_at
        self.expires_at = expires_at

    @classmethod
    def from_dict(cls, data):
        return cls(
            checkout_id=data.get("checkout_id"),
            subscription_id=data.get("subscription_id"),
            plan_id=data.get("plan_id", "mock-plan-monthly"),
            active=data.get("active", False),
            created_at=data.get("created_at"),
            activated_at=data.get("activated_at"),
            expires_at=data.get("expires_at")
        )

    def to_dict(self):
        return {
            "checkout_id": self.checkout_id,
            "subscription_id": self.subscription_id,
            "plan_id": self.plan_id,
            "active": self.active,
            "created_at": self.created_at,
            "activated_at": self.activated_at,
            "expires_at": self.expires_at
        }


# ---------------------------
# JSON Helpers
# ---------------------------
def _load_json(path):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def _save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print("Failed to save JSON:", e)


# ---------------------------
# Subscription Core
# ---------------------------
def get_subscription_for(email):
    """
    Return Subscription object for email or None.
    """
    subs = _load_json(SUBSCRIPTIONS_FILE)
    rec = subs.get(email)
    if rec:
        return Subscription.from_dict(rec)
    return None


def ensure_subscription_active(email):
    """
    Ensure subscription exists and is active.
    Auto-create mock subscription if missing or expired.
    Returns a Subscription object.
    """
    subs = _load_json(SUBSCRIPTIONS_FILE)
    rec = subs.get(email)

    if not rec:
        print(f"⚙️ No subscription found for {email}, creating mock active subscription...")
        subscription = create_mock_subscription(email)
        activate_mock_subscription(email, subscription.checkout_id)
        return subscription

    subscription = Subscription.from_dict(rec)

    # Check expiry
    try:
        if subscription.expires_at:
            expires_dt = datetime.fromisoformat(subscription.expires_at)
            if expires_dt < datetime.now(timezone.utc):
                print(f"⚙️ Subscription for {email} expired — reactivating mock.")
                activate_mock_subscription(email, subscription.checkout_id)
                subscription.active = True
    except Exception:
        pass

    # Auto-activate if inactive
    if not subscription.active:
        print(f"⚙️ Subscription for {email} inactive — activating mock.")
        activate_mock_subscription(email, subscription.checkout_id)
        subscription.active = True

    return subscription


def create_mock_subscription(email, plan_id="mock-plan-monthly"):
    """
    Simulate starting a Paddle checkout. Create a subscription record with inactive state.
    Returns a Subscription object.
    """
    subs = _load_json(SUBSCRIPTIONS_FILE)
    checkout_id = str(uuid.uuid4())
    subscription = Subscription(checkout_id=checkout_id, plan_id=plan_id, active=False)
    subs[email] = subscription.to_dict()
    _save_json(SUBSCRIPTIONS_FILE, subs)
    return subscription


def activate_mock_subscription(email, checkout_id):
    """
    Simulate Paddle completing a checkout. Mark subscription active and set subscription_id.
    Returns the Subscription object or None on failure.
    """
    subs = _load_json(SUBSCRIPTIONS_FILE)
    rec = subs.get(email)
    if not rec:
        return None
    if rec.get("checkout_id") != checkout_id:
        return None

    subscription = Subscription.from_dict(rec)
    subscription.subscription_id = str(uuid.uuid4())
    subscription.active = True
    subscription.activated_at = datetime.now(timezone.utc).isoformat()
    subscription.expires_at = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    subs[email] = subscription.to_dict()
    _save_json(SUBSCRIPTIONS_FILE, subs)
    print(f"✅ Mock subscription activated for {email}")
    return subscription


def revoke_subscription(email):
    """
    Set subscription inactive (useful for testing cancellations).
    """
    subs = _load_json(SUBSCRIPTIONS_FILE)
    rec = subs.get(email)
    if not rec:
        return False
    subscription = Subscription.from_dict(rec)
    subscription.active = False
    subs[email] = subscription.to_dict()
    _save_json(SUBSCRIPTIONS_FILE, subs)
    print(f"❌ Subscription revoked for {email}")
    return True
