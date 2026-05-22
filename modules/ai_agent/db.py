import json
from datetime import datetime, timedelta
from db.connection import get_connection


def init_tables():
    conn = get_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS ai_analyses (
            id SERIAL PRIMARY KEY,
            user_email TEXT NOT NULL,
            analysis_type TEXT NOT NULL,
            period TEXT,
            result_json TEXT,
            generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP
        )
    ''')
    conn.execute('''
        CREATE INDEX IF NOT EXISTS idx_ai_analyses_lookup
        ON ai_analyses (user_email, analysis_type, period, expires_at)
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS ai_chat_history (
            id SERIAL PRIMARY KEY,
            user_email TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()


def get_cached_analysis(user_email: str, analysis_type: str, period: str = None):
    conn = get_connection()
    now = datetime.utcnow()
    if period:
        row = conn.execute(
            '''SELECT result_json FROM ai_analyses
               WHERE user_email=%s AND analysis_type=%s AND period=%s AND expires_at > %s
               ORDER BY generated_at DESC LIMIT 1''',
            (user_email, analysis_type, period, now),
        ).fetchone()
    else:
        row = conn.execute(
            '''SELECT result_json FROM ai_analyses
               WHERE user_email=%s AND analysis_type=%s AND expires_at > %s
               ORDER BY generated_at DESC LIMIT 1''',
            (user_email, analysis_type, now),
        ).fetchone()
    conn.close()
    if row:
        return json.loads(row['result_json'])
    return None


def save_analysis(user_email: str, analysis_type: str, result: dict,
                  period: str = None, ttl_hours: int = 6):
    conn = get_connection()
    now = datetime.utcnow()
    expires = now + timedelta(hours=ttl_hours)
    conn.execute(
        '''INSERT INTO ai_analyses
           (user_email, analysis_type, period, result_json, generated_at, expires_at)
           VALUES (%s, %s, %s, %s, %s, %s)''',
        (user_email, analysis_type, period,
         json.dumps(result, ensure_ascii=False), now, expires),
    )
    conn.commit()
    conn.close()


def clear_user_cache(user_email: str):
    conn = get_connection()
    conn.execute('DELETE FROM ai_analyses WHERE user_email=%s', (user_email,))
    conn.commit()
    conn.close()


def get_chat_history(user_email: str, limit: int = 20):
    conn = get_connection()
    rows = conn.execute(
        '''SELECT role, content FROM ai_chat_history
           WHERE user_email=%s ORDER BY created_at DESC LIMIT %s''',
        (user_email, limit),
    ).fetchall()
    conn.close()
    return [{'role': r['role'], 'content': r['content']} for r in reversed(rows)]


def save_chat_message(user_email: str, role: str, content: str):
    conn = get_connection()
    conn.execute(
        'INSERT INTO ai_chat_history (user_email, role, content) VALUES (%s, %s, %s)',
        (user_email, role, content),
    )
    conn.commit()
    conn.close()


def clear_chat_history(user_email: str):
    conn = get_connection()
    conn.execute('DELETE FROM ai_chat_history WHERE user_email=%s', (user_email,))
    conn.commit()
    conn.close()
