from db.connection import get_connection


def init_tables():
    conn = get_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS cad_usuarios (
            id SERIAL PRIMARY KEY,
            chave_usr1 TEXT,
            chave_usr2 TEXT,
            nome TEXT NOT NULL,
            fator_pagamento INTEGER DEFAULT 1
        )
    ''')
    conn.commit()
    conn.close()


def get_all_usuarios():
    conn = get_connection()
    rows = conn.execute('SELECT * FROM cad_usuarios ORDER BY id DESC').fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_usuario(chave_usr1, chave_usr2, nome, fator_pagamento):
    conn = get_connection()
    conn.execute(
        'INSERT INTO cad_usuarios (chave_usr1, chave_usr2, nome, fator_pagamento) VALUES (%s,%s,%s,%s)',
        (chave_usr1, chave_usr2, nome, fator_pagamento),
    )
    conn.commit()
    conn.close()


def update_usuario(u_id, chave_usr1, chave_usr2, nome, fator_pagamento):
    conn = get_connection()
    conn.execute(
        'UPDATE cad_usuarios SET chave_usr1=%s, chave_usr2=%s, nome=%s, fator_pagamento=%s WHERE id=%s',
        (chave_usr1, chave_usr2, nome, fator_pagamento, u_id),
    )
    conn.commit()
    conn.close()


def delete_usuario(u_id):
    conn = get_connection()
    conn.execute('DELETE FROM cad_usuarios WHERE id=%s', (u_id,))
    conn.commit()
    conn.close()


def clear_usuarios():
    conn = get_connection()
    conn.execute('DELETE FROM cad_usuarios')
    conn.commit()
    conn.close()
