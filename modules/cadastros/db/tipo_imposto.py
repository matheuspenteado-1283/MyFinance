from db.connection import get_connection


def init_tables():
    conn = get_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tb_tipo_imposto (
            id SERIAL PRIMARY KEY,
            user_email TEXT,
            tp_imposto TEXT NOT NULL,
            alq_imposto REAL,
            pagamento TEXT
        )
    ''')
    conn.commit()
    try:
        conn.execute('ALTER TABLE tb_tipo_imposto ADD COLUMN user_email TEXT')
        conn.commit()
    except Exception:
        pass
    conn.close()


def get_all_tipo_imposto(user_email):
    conn = get_connection()
    rows = conn.execute(
        'SELECT * FROM tb_tipo_imposto WHERE user_email=%s ORDER BY tp_imposto', (user_email,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_tipo_imposto(user_email, tp_imposto, alq_imposto, pagamento):
    conn = get_connection()
    conn.execute(
        'INSERT INTO tb_tipo_imposto (user_email, tp_imposto, alq_imposto, pagamento) VALUES (%s,%s,%s,%s)',
        (user_email, tp_imposto, alq_imposto, pagamento),
    )
    conn.commit()
    conn.close()


def update_tipo_imposto(user_email, ti_id, tp_imposto, alq_imposto, pagamento):
    conn = get_connection()
    conn.execute(
        'UPDATE tb_tipo_imposto SET tp_imposto=%s, alq_imposto=%s, pagamento=%s WHERE id=%s AND user_email=%s',
        (tp_imposto, alq_imposto, pagamento, ti_id, user_email),
    )
    conn.commit()
    conn.close()


def delete_tipo_imposto(user_email, ti_id):
    conn = get_connection()
    conn.execute('DELETE FROM tb_tipo_imposto WHERE id=%s AND user_email=%s', (ti_id, user_email))
    conn.commit()
    conn.close()


def clear_tipo_imposto(user_email):
    conn = get_connection()
    conn.execute('DELETE FROM tb_tipo_imposto WHERE user_email=%s', (user_email,))
    conn.commit()
    conn.close()
