import sqlite3
import os

# Path to your database
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "autoguardian.db")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# List all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()

for table in tables:
    print(f"Table: {table[0]}")
    cursor.execute(f"PRAGMA table_info({table[0]});")
    columns = cursor.fetchall()
    for col in columns:
        print(col)
    print("-" * 30)

conn.close()
