from db.connection import get_connection


def init_tables():
    conn = get_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS cad_despesas (
            id SERIAL PRIMARY KEY,
            user_email TEXT,
            despesa TEXT NOT NULL,
            tipo_despesa TEXT,
            fator_divisao INTEGER,
            prioridade TEXT
        )
    ''')
    conn.commit()
    try:
        conn.execute('ALTER TABLE cad_despesas ADD COLUMN user_email TEXT')
        conn.commit()
    except Exception:
        pass
    conn.close()


def get_all_despesas(user_email):
    conn = get_connection()
    rows = conn.execute(
        'SELECT * FROM cad_despesas WHERE user_email=%s ORDER BY id DESC', (user_email,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_despesa(user_email, despesa, tipo_despesa, fator_divisao, prioridade):
    conn = get_connection()
    conn.execute(
        'INSERT INTO cad_despesas (user_email, despesa, tipo_despesa, fator_divisao, prioridade) VALUES (%s,%s,%s,%s,%s)',
        (user_email, despesa, tipo_despesa, fator_divisao, prioridade),
    )
    conn.commit()
    conn.close()


def update_despesa(user_email, d_id, despesa, tipo_despesa, fator_divisao, prioridade):
    conn = get_connection()
    conn.execute(
        'UPDATE cad_despesas SET despesa=%s, tipo_despesa=%s, fator_divisao=%s, prioridade=%s WHERE id=%s AND user_email=%s',
        (despesa, tipo_despesa, fator_divisao, prioridade, d_id, user_email),
    )
    conn.commit()
    conn.close()


def delete_despesa(user_email, d_id):
    conn = get_connection()
    conn.execute('DELETE FROM cad_despesas WHERE id=%s AND user_email=%s', (d_id, user_email))
    conn.commit()
    conn.close()


def overwrite_despesas(user_email, despesas_list):
    conn = get_connection()
    conn.execute('DELETE FROM cad_despesas WHERE user_email=%s', (user_email,))
    for d in despesas_list:
        conn.execute(
            'INSERT INTO cad_despesas (user_email, despesa, tipo_despesa, fator_divisao, prioridade) VALUES (%s,%s,%s,%s,%s)',
            (user_email, d.get('despesa'), d.get('tipo_despesa'), d.get('fator_divisao'), d.get('prioridade')),
        )
    conn.commit()
    conn.close()


def clear_despesas(user_email):
    conn = get_connection()
    conn.execute('DELETE FROM cad_despesas WHERE user_email=%s', (user_email,))
    conn.commit()
    conn.close()
