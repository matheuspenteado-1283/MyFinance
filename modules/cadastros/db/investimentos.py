from db.connection import get_connection


def init_tables():
    conn = get_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS cad_investimentos (
            id SERIAL PRIMARY KEY,
            user_email TEXT,
            descricao TEXT NOT NULL
        )
    ''')
    conn.commit()
    try:
        conn.execute('ALTER TABLE cad_investimentos ADD COLUMN user_email TEXT')
        conn.commit()
    except Exception:
        pass
    conn.close()


def get_all_investimentos(user_email):
    conn = get_connection()
    rows = conn.execute(
        'SELECT * FROM cad_investimentos WHERE user_email=%s ORDER BY id DESC', (user_email,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_investimento(user_email, descricao):
    conn = get_connection()
    conn.execute(
        'INSERT INTO cad_investimentos (user_email, descricao) VALUES (%s,%s)', (user_email, descricao)
    )
    conn.commit()
    conn.close()


def update_investimento(user_email, i_id, descricao):
    conn = get_connection()
    conn.execute(
        'UPDATE cad_investimentos SET descricao=%s WHERE id=%s AND user_email=%s', (descricao, i_id, user_email)
    )
    conn.commit()
    conn.close()


def delete_investimento(user_email, i_id):
    conn = get_connection()
    conn.execute('DELETE FROM cad_investimentos WHERE id=%s AND user_email=%s', (i_id, user_email))
    conn.commit()
    conn.close()


def clear_investimentos(user_email):
    conn = get_connection()
    conn.execute('DELETE FROM cad_investimentos WHERE user_email=%s', (user_email,))
    conn.commit()
    conn.close()
