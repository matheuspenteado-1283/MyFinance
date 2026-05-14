from db.connection import get_connection


def init_tables():
    conn = get_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS cad_contas (
            id SERIAL PRIMARY KEY,
            user_email TEXT,
            descricao TEXT NOT NULL,
            agencia TEXT,
            conta TEXT,
            dados_acesso TEXT,
            senha TEXT,
            comentarios TEXT
        )
    ''')
    conn.commit()
    try:
        conn.execute('ALTER TABLE cad_contas ADD COLUMN user_email TEXT')
        conn.commit()
    except Exception:
        pass
    conn.close()


def get_all_contas(user_email):
    conn = get_connection()
    rows = conn.execute(
        'SELECT * FROM cad_contas WHERE user_email=%s ORDER BY id DESC', (user_email,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_conta(user_email, descricao, agencia, conta, dados_acesso, senha, comentarios):
    conn = get_connection()
    conn.execute(
        'INSERT INTO cad_contas (user_email, descricao, agencia, conta, dados_acesso, senha, comentarios) VALUES (%s,%s,%s,%s,%s,%s,%s)',
        (user_email, descricao, agencia, conta, dados_acesso, senha, comentarios),
    )
    conn.commit()
    conn.close()


def update_conta(user_email, c_id, descricao, agencia, conta, dados_acesso, senha, comentarios):
    conn = get_connection()
    conn.execute(
        'UPDATE cad_contas SET descricao=%s, agencia=%s, conta=%s, dados_acesso=%s, senha=%s, comentarios=%s WHERE id=%s AND user_email=%s',
        (descricao, agencia, conta, dados_acesso, senha, comentarios, c_id, user_email),
    )
    conn.commit()
    conn.close()


def delete_conta(user_email, c_id):
    conn = get_connection()
    conn.execute('DELETE FROM cad_contas WHERE id=%s AND user_email=%s', (c_id, user_email))
    conn.commit()
    conn.close()


def clear_contas(user_email):
    conn = get_connection()
    conn.execute('DELETE FROM cad_contas WHERE user_email=%s', (user_email,))
    conn.commit()
    conn.close()


def get_senha_conta(user_email, c_id):
    conn = get_connection()
    row = conn.execute(
        'SELECT senha FROM cad_contas WHERE id=%s AND user_email=%s', (c_id, user_email)
    ).fetchone()
    conn.close()
    return row['senha'] if row else ''
