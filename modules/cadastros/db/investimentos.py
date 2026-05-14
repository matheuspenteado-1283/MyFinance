from db.connection import get_connection


def init_tables():
    conn = get_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS cad_investimentos (
            id SERIAL PRIMARY KEY,
            descricao TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()


def get_all_investimentos():
    conn = get_connection()
    rows = conn.execute('SELECT * FROM cad_investimentos ORDER BY id DESC').fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_investimento(descricao):
    conn = get_connection()
    conn.execute('INSERT INTO cad_investimentos (descricao) VALUES (%s)', (descricao,))
    conn.commit()
    conn.close()


def update_investimento(i_id, descricao):
    conn = get_connection()
    conn.execute('UPDATE cad_investimentos SET descricao=%s WHERE id=%s', (descricao, i_id))
    conn.commit()
    conn.close()


def delete_investimento(i_id):
    conn = get_connection()
    conn.execute('DELETE FROM cad_investimentos WHERE id=%s', (i_id,))
    conn.commit()
    conn.close()


def clear_investimentos():
    conn = get_connection()
    conn.execute('DELETE FROM cad_investimentos')
    conn.commit()
    conn.close()
