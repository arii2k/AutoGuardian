import sys
import os

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from services.gmail_service import scan_gmail

labels = scan_gmail()
print("Gmail Labels:", labels)
