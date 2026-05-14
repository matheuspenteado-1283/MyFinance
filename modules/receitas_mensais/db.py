from db.connection import get_connection


def init_tables():
    conn = get_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS receitas_mensais (
            id SERIAL PRIMARY KEY,
            user_email TEXT,
            data TEXT,
            tipo_receita TEXT,
            valor_original REAL,
            moeda_original TEXT,
            cotacao REAL DEFAULT 1,
            valor_eur REAL,
            valor_brl REAL,
            conta_bancaria TEXT,
            mes_referencia TEXT,
            despesa_mensal_id INTEGER,
            comentarios TEXT,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()


def get_receitas_mensais(user_email, mes=None):
    conn = get_connection()
    if mes:
        rows = conn.execute(
            'SELECT * FROM receitas_mensais WHERE user_email=%s AND mes_referencia=%s ORDER BY data, id',
            (user_email, mes),
        ).fetchall()
    else:
        rows = conn.execute(
            'SELECT * FROM receitas_mensais WHERE user_email=%s ORDER BY mes_referencia DESC, data, id',
            (user_email,),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_receita_mensal(user_email, row):
    conn = get_connection()
    conn.execute('''
        INSERT INTO receitas_mensais
        (user_email, data, tipo_receita, valor_original, moeda_original, cotacao, valor_eur, valor_brl,
         conta_bancaria, mes_referencia, despesa_mensal_id, comentarios)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    ''', (
        user_email,
        row.get('data'), row.get('tipo_receita'), row.get('valor_original'),
        row.get('moeda_original'), row.get('cotacao', 1), row.get('valor_eur'),
        row.get('valor_brl'), row.get('conta_bancaria'), row.get('mes_referencia'),
        row.get('despesa_mensal_id'), row.get('comentarios'),
    ))
    conn.commit()
    conn.close()


def update_receita_mensal(user_email, r_id, row):
    conn = get_connection()
    conn.execute('''
        UPDATE receitas_mensais SET
        data=%s, tipo_receita=%s, valor_original=%s, moeda_original=%s, cotacao=%s, valor_eur=%s, valor_brl=%s,
        conta_bancaria=%s, mes_referencia=%s, comentarios=%s
        WHERE id=%s AND user_email=%s
    ''', (
        row.get('data'), row.get('tipo_receita'), row.get('valor_original'),
        row.get('moeda_original'), row.get('cotacao', 1), row.get('valor_eur'),
        row.get('valor_brl'), row.get('conta_bancaria'), row.get('mes_referencia'),
        row.get('comentarios'), r_id, user_email,
    ))
    conn.commit()
    conn.close()


def delete_receita_mensal(user_email, r_id):
    conn = get_connection()
    conn.execute('DELETE FROM receitas_mensais WHERE id=%s AND user_email=%s', (r_id, user_email))
    conn.commit()
    conn.close()


def sync_receitas_from_despesas_mensais(user_email, mes):
    conn = get_connection()
    conn.execute(
        'DELETE FROM receitas_mensais WHERE user_email=%s AND mes_referencia=%s AND despesa_mensal_id IS NOT NULL',
        (user_email, mes),
    )
    rows = conn.execute(
        'SELECT * FROM despesas_mensais WHERE user_email=%s AND mes_referencia=%s AND receita=1',
        (user_email, mes),
    ).fetchall()
    for r in rows:
        conn.execute('''
            INSERT INTO receitas_mensais
            (user_email, data, tipo_receita, valor_original, moeda_original, cotacao, valor_eur, valor_brl,
             conta_bancaria, mes_referencia, despesa_mensal_id, comentarios)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ''', (
            user_email, r['data'], r['categoria_final'], r['valor_original'],
            r['moeda'], r['cambio_eur'], r['valor_eur'],
            r['valor_original'], r['conta_bancaria'], r['mes_referencia'],
            r['id'], r['comentarios'],
        ))
    conn.commit()
    conn.close()
    return len(rows)


def get_totais_receitas(user_email, mes):
    conn = get_connection()
    row = conn.execute('''
        SELECT SUM(valor_eur) as total_eur, SUM(valor_brl) as total_brl
        FROM receitas_mensais WHERE user_email=%s AND mes_referencia=%s
    ''', (user_email, mes)).fetchone()
    conn.close()
    return {'total_eur': row['total_eur'] or 0, 'total_brl': row['total_brl'] or 0}
