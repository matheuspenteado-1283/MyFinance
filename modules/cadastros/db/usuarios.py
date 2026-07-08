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
    conn.execute('ALTER TABLE cad_usuarios ADD COLUMN IF NOT EXISTS user_email TEXT')
    conn.execute('ALTER TABLE cad_usuarios ADD COLUMN IF NOT EXISTS label_usr1 TEXT')
    conn.execute('ALTER TABLE cad_usuarios ADD COLUMN IF NOT EXISTS label_usr2 TEXT')
    conn.commit()
    _collapse_and_backfill_pagador_labels(conn)
    conn.close()


def _collapse_and_backfill_pagador_labels(conn):
    dup_emails = conn.execute('''
        SELECT user_email FROM cad_usuarios
        WHERE user_email IS NOT NULL AND user_email <> ''
        GROUP BY user_email HAVING COUNT(*) > 1
    ''').fetchall()
    for r in dup_emails:
        ids = conn.execute(
            'SELECT id FROM cad_usuarios WHERE user_email=%s ORDER BY id ASC',
            (r['user_email'],)
        ).fetchall()
        drop_ids = [x['id'] for x in ids[1:]]
        if drop_ids:
            conn.execute('DELETE FROM cad_usuarios WHERE id = ANY(%s)', (drop_ids,))
    conn.commit()

    pending = conn.execute('''
        SELECT id, user_email FROM cad_usuarios
        WHERE label_usr1 IS NULL AND user_email IS NOT NULL AND user_email <> ''
    ''').fetchall()
    for r in pending:
        chaves = conn.execute(
            'SELECT chave_usr1, chave_usr2 FROM cad_usuarios WHERE user_email=%s ORDER BY id ASC',
            (r['user_email'],)
        ).fetchall()
        label1 = next((c['chave_usr1'] for c in chaves if c.get('chave_usr1')), 'USR1')
        label2 = next((c['chave_usr2'] for c in chaves if c.get('chave_usr2')), 'USR2')
        conn.execute(
            'UPDATE cad_usuarios SET label_usr1=%s, label_usr2=%s WHERE id=%s',
            (label1, label2, r['id'])
        )
    conn.commit()


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


def get_pagador_labels(user_email):
    conn = get_connection()
    row = conn.execute(
        'SELECT label_usr1, label_usr2 FROM cad_usuarios WHERE user_email=%s ORDER BY id ASC LIMIT 1',
        (user_email,)
    ).fetchone()
    conn.close()
    if not row:
        return {'label_usr1': 'USR1', 'label_usr2': 'USR2'}
    return {
        'label_usr1': row.get('label_usr1') or 'USR1',
        'label_usr2': row.get('label_usr2') or 'USR2',
    }


def save_pagador_labels(user_email, label_usr1, label_usr2):
    conn = get_connection()
    row = conn.execute(
        'SELECT id FROM cad_usuarios WHERE user_email=%s ORDER BY id ASC LIMIT 1',
        (user_email,)
    ).fetchone()
    if row:
        conn.execute(
            'UPDATE cad_usuarios SET label_usr1=%s, label_usr2=%s WHERE id=%s',
            (label_usr1, label_usr2, row['id']),
        )
    else:
        conn.execute(
            "INSERT INTO cad_usuarios (user_email, nome, label_usr1, label_usr2) VALUES (%s, '', %s, %s)",
            (user_email, label_usr1, label_usr2),
        )
    conn.commit()
    conn.close()
