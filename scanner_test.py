# scanner_test.py
import time
import logging
from services.auto_scan import start_auto_scan_scheduler
from services.gmail_service import scan_and_label_gmail

# ---------------------------
# Logger Setup
# ---------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ScannerTest")

# ---------------------------
# Wrapper to catch errors
# ---------------------------
def safe_scan():
    try:
        results = scan_and_label_gmail(max_results=5)  # reduce number for testing
        logger.info(f"Scanned {len(results)} emails.")
    except Exception as e:
        logger.error(f"Scan failed: {e}", exc_info=True)

# ---------------------------
# Start auto scan scheduler
# ---------------------------
if __name__ == "__main__":
    logger.info("Starting standalone scanner (no Flask).")
    
    # Start the scheduler in its own thread
    start_auto_scan_scheduler(interval_seconds=60, user_email="me@example.com", user_id=1)
    
    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Standalone scanner stopped by user.")
