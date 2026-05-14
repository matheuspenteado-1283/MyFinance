from db.connection import get_connection


def init_tables():
    conn = get_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS cad_receitas (
            id SERIAL PRIMARY KEY,
            descricao TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()


def get_all_receitas():
    conn = get_connection()
    rows = conn.execute('SELECT * FROM cad_receitas ORDER BY id DESC').fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_receita(descricao):
    conn = get_connection()
    conn.execute('INSERT INTO cad_receitas (descricao) VALUES (%s)', (descricao,))
    conn.commit()
    conn.close()


def update_receita(r_id, descricao):
    conn = get_connection()
    conn.execute('UPDATE cad_receitas SET descricao=%s WHERE id=%s', (descricao, r_id))
    conn.commit()
    conn.close()


def delete_receita(r_id):
    conn = get_connection()
    conn.execute('DELETE FROM cad_receitas WHERE id=%s', (r_id,))
    conn.commit()
    conn.close()


def clear_receitas():
    conn = get_connection()
    conn.execute('DELETE FROM cad_receitas')
    conn.commit()
    conn.close()
