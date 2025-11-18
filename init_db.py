# ---------------------------
# Database helpers
# ---------------------------
def init_db():
    """Initialize database and ensure all tables & columns exist."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # scan_history table
    c.execute('''
        CREATE TABLE IF NOT EXISTS scan_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email_id TEXT,
            date TEXT,
            sender TEXT,
            subject TEXT,
            score INTEGER,
            matched_rules TEXT,
            memory_alert TEXT,
            community_alert TEXT,
            quarantine INTEGER DEFAULT 0,
            timestamp TEXT,
            user_id INTEGER
        )
    ''')

    # collective_metrics table
    c.execute('''
        CREATE TABLE IF NOT EXISTS collective_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            email_id TEXT,
            score INTEGER,
            risk_level TEXT,
            quarantine INTEGER DEFAULT 0,
            timestamp TEXT
        )
    ''')

    # Define expected columns per table
    expected_columns = {
        "scan_history": {
            "quarantine": "INTEGER DEFAULT 0"
        },
        "collective_metrics": {
            "quarantine": "INTEGER DEFAULT 0"
        }
    }

    # Automatically add missing columns if needed
    for table, cols in expected_columns.items():
        c.execute(f"PRAGMA table_info({table});")
        existing_cols = [col[1] for col in c.fetchall()]
        for col_name, col_type in cols.items():
            if col_name not in existing_cols:
                c.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")

    conn.commit()
    conn.close()
