from __future__ import annotations
import secrets
import datetime
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
    c.execute('''
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id SERIAL PRIMARY KEY,
            email TEXT NOT NULL,
            token TEXT UNIQUE NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL,
            used BOOLEAN NOT NULL DEFAULT FALSE
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


def create_reset_token(email: str) -> str | None:
    """Creates a 1-hour reset token. Returns token or None if email not found."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT id FROM users WHERE email = %s', (email.lower().strip(),))
    if not c.fetchone():
        conn.close()
        return None
    token = secrets.token_urlsafe(32)
    expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
    c.execute(
        'INSERT INTO password_reset_tokens (email, token, expires_at) VALUES (%s, %s, %s)',
        (email.lower().strip(), token, expires_at)
    )
    conn.commit()
    conn.close()
    return token


def verify_reset_token(token: str) -> str | None:
    """Returns the email if the token is valid and unexpired, else None."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        'SELECT email, expires_at, used FROM password_reset_tokens WHERE token = %s',
        (token,)
    )
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    if row['used']:
        return None
    if datetime.datetime.now(datetime.timezone.utc) > row['expires_at']:
        return None
    return row['email']


def consume_reset_token(token: str, new_password: str) -> bool:
    """Marks token as used and updates the user's password. Returns True on success."""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute(
            'SELECT email FROM password_reset_tokens WHERE token = %s AND used = FALSE AND expires_at > NOW()',
            (token,)
        )
        row = c.fetchone()
        if not row:
            return False
        email = row['email']
        new_hash = generate_password_hash(new_password, method='pbkdf2:sha256')
        c.execute('UPDATE users SET password_hash = %s WHERE email = %s', (new_hash, email))
        c.execute('UPDATE password_reset_tokens SET used = TRUE WHERE token = %s', (token,))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def change_user_email(current_email: str, password: str, new_email: str) -> dict:
    current = current_email.lower().strip()
    new = new_email.lower().strip()

    if current == new:
        return {'error': 'O novo e-mail é igual ao atual'}

    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('SELECT password_hash FROM users WHERE email = %s', (current,))
        row = c.fetchone()
        if not row or not check_password_hash(row['password_hash'], password):
            return {'error': 'Senha incorreta'}

        c.execute('SELECT id FROM users WHERE email = %s', (new,))
        if c.fetchone():
            return {'error': 'Este e-mail já está em uso'}

        TABLES = [
            'despesas_mensais',
            'despesas_anuais',
            'receitas_mensais',
            'lcto_impostos',
            'lcto_emprestimos',
            'lcto_investimentos',
            'trader_positions',
            'relatorios_configurados',
        ]
        for table in TABLES:
            c.execute(
                f'UPDATE {table} SET user_email = %s WHERE LOWER(user_email) = %s',
                (new, current)
            )

        c.execute(
            'UPDATE password_reset_tokens SET email = %s WHERE LOWER(email) = %s',
            (new, current)
        )
        c.execute('UPDATE users SET email = %s WHERE email = %s', (new, current))

        conn.commit()
        return {'ok': True}
    except Exception as exc:
        conn.rollback()
        return {'error': f'Erro interno: {exc}'}
    finally:
        conn.close()


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
