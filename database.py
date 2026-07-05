import sqlite3

DB_PATH = "prospectiq.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS prospects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            title TEXT,
            scraped_text TEXT,
            analysis_json TEXT,
            score_json TEXT,
            draft_json TEXT,
            approval_status TEXT DEFAULT 'pending',
            approved_email_subject TEXT,
            approved_email_body TEXT,
            approved_linkedin_dm TEXT,
            status TEXT DEFAULT 'scraped',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS strategy (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_description TEXT,
            strategy_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    for col in [
        "analysis_json TEXT", "draft_json TEXT", "score_json TEXT",
        "approval_status TEXT DEFAULT 'pending'",
        "approved_email_subject TEXT",
        "approved_email_body TEXT",
        "approved_linkedin_dm TEXT"
    ]:
        try:
            conn.execute(f"ALTER TABLE prospects ADD COLUMN {col}")
        except:
            pass
    conn.commit()
    conn.close()

def get_strategy():
    conn = get_db()
    row = conn.execute("SELECT * FROM strategy ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    return row