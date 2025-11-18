import sqlite3
import os

# Path to your database
DB_PATH = os.path.join("data", "autoguardian.db")  # adjust if your path is different

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Get all table schemas
cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()

for name, sql in tables:
    print(f"Table: {name}\n{sql}\n{'-'*50}")

conn.close()
