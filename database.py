import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    return psycopg2.connect(os.getenv('DATABASE_URL'))

def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

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

def register_user(username, password_hash):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            'INSERT INTO users (username, password_hash) VALUES (%s, %s) RETURNING id',
            (username, password_hash)
        )
        user_id = cur.fetchone()[0]
        conn.commit()
        return user_id
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        return None
    finally:
        cur.close()
        conn.close()

def get_user(username):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('SELECT id, username, password_hash FROM users WHERE username = %s', (username,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row

def save_result(filename, errors, traffic):
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