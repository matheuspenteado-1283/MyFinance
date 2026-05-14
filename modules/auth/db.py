from db.connection import get_connection
from werkzeug.security import generate_password_hash, check_password_hash


def init_tables():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()


def register_user(email: str, password: str) -> bool:
    conn = get_connection()
    c = conn.cursor()
    email_lower = email.lower().strip()
    try:
        c.execute('DELETE FROM despesas_mensais WHERE user_email = %s', (email_lower,))
        c.execute('DELETE FROM despesas_anuais WHERE user_email = %s', (email_lower,))
        c.execute('DELETE FROM receitas_mensais WHERE user_email = %s', (email_lower,))
        c.execute('DELETE FROM lcto_impostos WHERE user_email = %s', (email_lower,))
        c.execute('INSERT INTO users (email, password_hash) VALUES (%s, %s)',
                  (email_lower, generate_password_hash(password, method='pbkdf2:sha256')))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def verify_user(email: str, password: str) -> bool:
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT password_hash FROM users WHERE email = %s', (email.lower().strip(),))
    row = c.fetchone()
    conn.close()
    if row and check_password_hash(row['password_hash'], password):
        return True
    return False


def get_user_by_email(email: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT id, email FROM users WHERE email = %s', (email.lower().strip(),))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def limpar_dados_usuario(email: str):
    conn = get_connection()
    c = conn.cursor()
    email_lower = email.lower().strip()
    c.execute('DELETE FROM despesas_mensais WHERE LOWER(user_email) = %s', (email_lower,))
    c.execute('DELETE FROM despesas_anuais WHERE LOWER(user_email) = %s', (email_lower,))
    c.execute('DELETE FROM receitas_mensais WHERE LOWER(user_email) = %s', (email_lower,))
    c.execute('DELETE FROM lcto_impostos WHERE LOWER(user_email) = %s', (email_lower,))
    c.execute('DELETE FROM lcto_emprestimos WHERE LOWER(user_email) = %s', (email_lower,))
    c.execute('DELETE FROM categorias_aprendidas')
    conn.commit()
    conn.close()
