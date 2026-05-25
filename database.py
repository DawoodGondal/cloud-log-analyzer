import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    return psycopg2.connect(os.getenv('DATABASE_URL'))

def init_db():
    """Create tables if they don't exist."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute('''
        CREATE TABLE IF NOT EXISTS analysis_results (
            id SERIAL PRIMARY KEY,
            filename TEXT NOT NULL,
            analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            error_404 INT DEFAULT 0,
            error_500 INT DEFAULT 0,
            error_403 INT DEFAULT 0,
            error_400 INT DEFAULT 0,
            error_502 INT DEFAULT 0,
            error_503 INT DEFAULT 0,
            total_requests INT DEFAULT 0
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS audit_log (
            id SERIAL PRIMARY KEY,
            event TEXT NOT NULL,
            username TEXT,
            detail TEXT,
            happened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    cur.close()
    conn.close()
    print("Database initialized.")

def save_result(filename, errors, traffic):
    """Persist one analysis run to the database."""
    conn = get_connection()
    cur = conn.cursor()

    total = sum(traffic.values()) if traffic else 0

    cur.execute('''
        INSERT INTO analysis_results
            (filename, error_404, error_500, error_403, error_400, error_502, error_503, total_requests)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    ''', (
        filename,
        errors.get('404', 0),
        errors.get('500', 0),
        errors.get('403', 0),
        errors.get('400', 0),
        errors.get('502', 0),
        errors.get('503', 0),
        total
    ))

    result_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return result_id

def log_event(event, username=None, detail=None):
    """Write an audit trail entry."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        'INSERT INTO audit_log (event, username, detail) VALUES (%s, %s, %s)',
        (event, username, detail)
    )
    conn.commit()
    cur.close()
    conn.close()

def get_history():
    """Fetch all past analysis runs."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('''
        SELECT filename, analyzed_at, error_404, error_500, error_403, total_requests
        FROM analysis_results
        ORDER BY analyzed_at DESC
        LIMIT 20
    ''')
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows