from services.auto_scan import start_auto_scan_scheduler
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "autoguardian.db")

start_auto_scan_scheduler(user_email="me@example.com", user_id=1, db_path=DB_PATH)
