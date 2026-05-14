from db.connection import get_connection


def init_tables():
    conn = get_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS cad_usuarios (
            id SERIAL PRIMARY KEY,
            user_email TEXT,
            chave_usr1 TEXT,
            chave_usr2 TEXT,
            nome TEXT NOT NULL,
            fator_pagamento INTEGER DEFAULT 1
        )
    ''')
    conn.commit()
    try:
        conn.execute('ALTER TABLE cad_usuarios ADD COLUMN user_email TEXT')
        conn.commit()
    except Exception:
        pass
    conn.close()


def get_all_usuarios(user_email):
    conn = get_connection()
    rows = conn.execute(
        'SELECT * FROM cad_usuarios WHERE user_email=%s ORDER BY id DESC', (user_email,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_usuario(user_email, chave_usr1, chave_usr2, nome, fator_pagamento):
    conn = get_connection()
    conn.execute(
        'INSERT INTO cad_usuarios (user_email, chave_usr1, chave_usr2, nome, fator_pagamento) VALUES (%s,%s,%s,%s,%s)',
        (user_email, chave_usr1, chave_usr2, nome, fator_pagamento),
    )
    conn.commit()
    conn.close()


def update_usuario(user_email, u_id, chave_usr1, chave_usr2, nome, fator_pagamento):
    conn = get_connection()
    conn.execute(
        'UPDATE cad_usuarios SET chave_usr1=%s, chave_usr2=%s, nome=%s, fator_pagamento=%s WHERE id=%s AND user_email=%s',
        (chave_usr1, chave_usr2, nome, fator_pagamento, u_id, user_email),
    )
    conn.commit()
    conn.close()


def delete_usuario(user_email, u_id):
    conn = get_connection()
    conn.execute('DELETE FROM cad_usuarios WHERE id=%s AND user_email=%s', (u_id, user_email))
    conn.commit()
    conn.close()


def clear_usuarios(user_email):
    conn = get_connection()
    conn.execute('DELETE FROM cad_usuarios WHERE user_email=%s', (user_email,))
    conn.commit()
    conn.close()
