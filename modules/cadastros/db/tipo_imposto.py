from db.connection import get_connection


def init_tables():
    conn = get_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tb_tipo_imposto (
            id SERIAL PRIMARY KEY,
            tp_imposto TEXT NOT NULL,
            alq_imposto REAL,
            pagamento TEXT
        )
    ''')
    conn.commit()
    conn.close()


def get_all_tipo_imposto():
    conn = get_connection()
    rows = conn.execute('SELECT * FROM tb_tipo_imposto ORDER BY tp_imposto').fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_tipo_imposto(tp_imposto, alq_imposto, pagamento):
    conn = get_connection()
    conn.execute(
        'INSERT INTO tb_tipo_imposto (tp_imposto, alq_imposto, pagamento) VALUES (%s, %s, %s)',
        (tp_imposto, alq_imposto, pagamento),
    )
    conn.commit()
    conn.close()


def update_tipo_imposto(ti_id, tp_imposto, alq_imposto, pagamento):
    conn = get_connection()
    conn.execute(
        'UPDATE tb_tipo_imposto SET tp_imposto=%s, alq_imposto=%s, pagamento=%s WHERE id=%s',
        (tp_imposto, alq_imposto, pagamento, ti_id),
    )
    conn.commit()
    conn.close()


def delete_tipo_imposto(ti_id):
    conn = get_connection()
    conn.execute('DELETE FROM tb_tipo_imposto WHERE id=%s', (ti_id,))
    conn.commit()
    conn.close()


def clear_tipo_imposto():
    conn = get_connection()
    conn.execute('DELETE FROM tb_tipo_imposto')
    conn.commit()
    conn.close()
