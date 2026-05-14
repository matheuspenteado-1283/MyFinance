from db.connection import get_connection


def init_tables():
    conn = get_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS cad_despesas (
            id SERIAL PRIMARY KEY,
            despesa TEXT NOT NULL,
            tipo_despesa TEXT,
            fator_divisao INTEGER,
            prioridade TEXT
        )
    ''')
    conn.commit()
    conn.close()


def get_all_despesas():
    conn = get_connection()
    rows = conn.execute('SELECT * FROM cad_despesas ORDER BY id DESC').fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_despesa(despesa, tipo_despesa, fator_divisao, prioridade):
    conn = get_connection()
    conn.execute(
        'INSERT INTO cad_despesas (despesa, tipo_despesa, fator_divisao, prioridade) VALUES (%s, %s, %s, %s)',
        (despesa, tipo_despesa, fator_divisao, prioridade),
    )
    conn.commit()
    conn.close()


def update_despesa(d_id, despesa, tipo_despesa, fator_divisao, prioridade):
    conn = get_connection()
    conn.execute(
        'UPDATE cad_despesas SET despesa=%s, tipo_despesa=%s, fator_divisao=%s, prioridade=%s WHERE id=%s',
        (despesa, tipo_despesa, fator_divisao, prioridade, d_id),
    )
    conn.commit()
    conn.close()


def delete_despesa(d_id):
    conn = get_connection()
    conn.execute('DELETE FROM cad_despesas WHERE id=%s', (d_id,))
    conn.commit()
    conn.close()


def overwrite_despesas(despesas_list):
    conn = get_connection()
    conn.execute('DELETE FROM cad_despesas')
    for d in despesas_list:
        conn.execute(
            'INSERT INTO cad_despesas (despesa, tipo_despesa, fator_divisao, prioridade) VALUES (%s, %s, %s, %s)',
            (d.get('despesa'), d.get('tipo_despesa'), d.get('fator_divisao'), d.get('prioridade')),
        )
    conn.commit()
    conn.close()


def clear_despesas():
    conn = get_connection()
    conn.execute('DELETE FROM cad_despesas')
    conn.commit()
    conn.close()
