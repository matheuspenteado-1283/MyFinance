from db.connection import get_connection


def init_tables():
    conn = get_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS cad_contas (
            id SERIAL PRIMARY KEY,
            descricao TEXT NOT NULL,
            agencia TEXT,
            conta TEXT,
            dados_acesso TEXT,
            senha TEXT,
            comentarios TEXT
        )
    ''')
    conn.commit()
    conn.close()


def get_all_contas():
    conn = get_connection()
    rows = conn.execute('SELECT * FROM cad_contas ORDER BY id DESC').fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_conta(descricao, agencia, conta, dados_acesso, senha, comentarios):
    conn = get_connection()
    conn.execute(
        'INSERT INTO cad_contas (descricao, agencia, conta, dados_acesso, senha, comentarios) VALUES (%s,%s,%s,%s,%s,%s)',
        (descricao, agencia, conta, dados_acesso, senha, comentarios),
    )
    conn.commit()
    conn.close()


def update_conta(c_id, descricao, agencia, conta, dados_acesso, senha, comentarios):
    conn = get_connection()
    conn.execute(
        'UPDATE cad_contas SET descricao=%s, agencia=%s, conta=%s, dados_acesso=%s, senha=%s, comentarios=%s WHERE id=%s',
        (descricao, agencia, conta, dados_acesso, senha, comentarios, c_id),
    )
    conn.commit()
    conn.close()


def delete_conta(c_id):
    conn = get_connection()
    conn.execute('DELETE FROM cad_contas WHERE id=%s', (c_id,))
    conn.commit()
    conn.close()


def clear_contas():
    conn = get_connection()
    conn.execute('DELETE FROM cad_contas')
    conn.commit()
    conn.close()


def get_senha_conta(c_id):
    conn = get_connection()
    row = conn.execute('SELECT senha FROM cad_contas WHERE id=%s', (c_id,)).fetchone()
    conn.close()
    return row['senha'] if row else ''
