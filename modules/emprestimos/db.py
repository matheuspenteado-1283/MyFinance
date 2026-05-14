from db.connection import get_connection


def init_tables():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS lcto_emprestimos (
            id SERIAL PRIMARY KEY,
            user_email TEXT,
            tipo TEXT NOT NULL,
            beneficiario TEXT,
            valor_operacao REAL NOT NULL,
            moeda_emp TEXT DEFAULT 'BRL',
            data_emprestimo TEXT,
            data_operacao TEXT,
            obs TEXT,
            status TEXT DEFAULT 'Ativo',
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    # migração de coluna
    try:
        c.execute('SELECT moeda_emp FROM lcto_emprestimos LIMIT 1')
    except Exception:
        c.execute("ALTER TABLE lcto_emprestimos ADD COLUMN moeda_emp TEXT DEFAULT 'BRL'")
        conn.commit()
    conn.close()


def get_all_lcto_emprestimos(user_email: str):
    conn = get_connection()
    rows = conn.execute(
        'SELECT * FROM lcto_emprestimos WHERE user_email=%s ORDER BY data_operacao DESC, id DESC',
        (user_email,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_lcto_emprestimo(user_email, tipo, beneficiario, valor_operacao, moeda_emp,
                        data_emprestimo, data_operacao, obs, status):
    conn = get_connection()
    conn.execute('''
        INSERT INTO lcto_emprestimos
        (user_email, tipo, beneficiario, valor_operacao, moeda_emp, data_emprestimo, data_operacao, obs, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    ''', (user_email, tipo, beneficiario, valor_operacao, moeda_emp,
          data_emprestimo, data_operacao, obs, status))
    conn.commit()
    conn.close()


def update_lcto_emprestimo(le_id, tipo, beneficiario, valor_operacao, moeda_emp,
                           data_emprestimo, data_operacao, obs, status):
    conn = get_connection()
    conn.execute('''
        UPDATE lcto_emprestimos SET
        tipo=%s, beneficiario=%s, valor_operacao=%s, moeda_emp=%s, data_emprestimo=%s, data_operacao=%s, obs=%s, status=%s
        WHERE id=%s
    ''', (tipo, beneficiario, valor_operacao, moeda_emp, data_emprestimo, data_operacao, obs, status, le_id))
    conn.commit()
    conn.close()


def delete_lcto_emprestimo(le_id):
    conn = get_connection()
    conn.execute('DELETE FROM lcto_emprestimos WHERE id=%s', (le_id,))
    conn.commit()
    conn.close()


def get_saldo_emprestimos(user_email: str):
    conn = get_connection()
    row = conn.execute('''
        SELECT
            SUM(CASE WHEN tipo = 'Empréstimo' THEN valor_operacao ELSE 0 END) as total_emprestado,
            SUM(CASE WHEN tipo IN ('Pagamento', 'Abatimento') THEN valor_operacao ELSE 0 END) as total_pago
        FROM lcto_emprestimos
        WHERE user_email = %s
    ''', (user_email,)).fetchone()
    conn.close()
    total_emprestado = row['total_emprestado'] or 0
    total_pago = row['total_pago'] or 0
    return {'total_emprestado': total_emprestado, 'total_pago': total_pago, 'saldo': total_emprestado - total_pago}
