from db.connection import get_connection


def init_tables():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS despesas_mensais (
            id SERIAL PRIMARY KEY,
            user_email TEXT,
            data TEXT,
            descricao TEXT,
            valor_original REAL,
            moeda TEXT,
            cambio_eur REAL,
            valor_eur REAL,
            usr1 TEXT,
            usr2 TEXT,
            diferenca_original REAL,
            status_pago TEXT DEFAULT 'Pendente',
            categoria_final TEXT,
            receita INTEGER DEFAULT 0,
            comentarios TEXT,
            conta_bancaria TEXT,
            mes_referencia TEXT,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS despesas_anuais (
            id SERIAL PRIMARY KEY,
            user_email TEXT,
            ano INTEGER,
            categoria_final TEXT,
            total_usr1 REAL DEFAULT 0,
            total_usr2 REAL DEFAULT 0,
            total_geral REAL DEFAULT 0,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()


def get_despesas_mensais(user_email, mes=None):
    conn = get_connection()
    if mes:
        rows = conn.execute(
            'SELECT * FROM despesas_mensais WHERE user_email=%s AND mes_referencia=%s ORDER BY data, id',
            (user_email, mes),
        ).fetchall()
    else:
        rows = conn.execute(
            'SELECT * FROM despesas_mensais WHERE user_email=%s ORDER BY mes_referencia DESC, data, id',
            (user_email,),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_despesas_mensais_batch(user_email, rows_list):
    if not rows_list:
        return {'saved': 0, 'skipped_duplicates': 0}
    mes = rows_list[0].get('mes_referencia', '')
    conn = get_connection()
    saved = 0
    skipped_duplicates = 0
    batch_keys = set()

    for r in rows_list:
        duplicate_key = _despesa_duplicate_key(user_email, r)
        if duplicate_key:
            if duplicate_key in batch_keys or _despesa_mensal_exists(conn, duplicate_key):
                skipped_duplicates += 1
                continue
            batch_keys.add(duplicate_key)

        conn.execute('''
            INSERT INTO despesas_mensais
            (user_email, data, descricao, valor_original, moeda, cambio_eur, valor_eur,
             usr1, usr2, diferenca_original, status_pago, categoria_final, receita,
             comentarios, conta_bancaria, mes_referencia)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ''', (
            user_email,
            r.get('data'), r.get('descricao'), r.get('valor_original'),
            r.get('moeda'), r.get('cambio_eur'), r.get('valor_eur'),
            r.get('usr1', 0), r.get('usr2', 0), r.get('diferenca_original'),
            r.get('status_pago', 'Pendente'), r.get('categoria_final'),
            1 if r.get('receita') else 0,
            r.get('comentarios'), r.get('conta_bancaria'), mes,
        ))
        saved += 1
    conn.commit()
    conn.close()
    return {'saved': saved, 'skipped_duplicates': skipped_duplicates}


def _despesa_duplicate_key(user_email, row):
    data = (row.get('data') or '').strip()
    descricao = (row.get('descricao') or '').strip().lower()
    moeda = (row.get('moeda') or '').strip().upper()
    conta_bancaria = (row.get('conta_bancaria') or '').strip()

    try:
        valor_original = round(float(row.get('valor_original')), 2)
    except (TypeError, ValueError):
        return None

    if not all([user_email, data, descricao, moeda, conta_bancaria]):
        return None

    return (user_email, conta_bancaria, data, descricao, valor_original, moeda)


def _despesa_mensal_exists(conn, duplicate_key):
    user_email, conta_bancaria, data, descricao, valor_original, moeda = duplicate_key
    row = conn.execute('''
        SELECT 1
        FROM despesas_mensais
        WHERE user_email = %s
          AND TRIM(COALESCE(conta_bancaria, '')) = %s
          AND data = %s
          AND LOWER(TRIM(COALESCE(descricao, ''))) = %s
          AND ABS(COALESCE(valor_original, 0) - %s) < 0.005
          AND UPPER(TRIM(COALESCE(moeda, ''))) = %s
        LIMIT 1
    ''', (user_email, conta_bancaria, data, descricao, valor_original, moeda)).fetchone()
    return row is not None


def add_despesa_mensal(user_email, row):
    conn = get_connection()
    conn.execute('''
        INSERT INTO despesas_mensais
        (user_email, data, descricao, valor_original, moeda, cambio_eur, valor_eur,
         usr1, usr2, diferenca_original, status_pago, categoria_final, receita,
         comentarios, conta_bancaria, mes_referencia)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    ''', (
        user_email,
        row.get('data'), row.get('descricao'), row.get('valor_original'),
        row.get('moeda'), row.get('cambio_eur'), row.get('valor_eur'),
        row.get('usr1', 0), row.get('usr2', 0), row.get('diferenca_original'),
        row.get('status_pago', 'Pendente'), row.get('categoria_final'),
        1 if row.get('receita') else 0,
        row.get('comentarios'), row.get('conta_bancaria'), row.get('mes_referencia'),
    ))
    conn.commit()
    conn.close()


def update_despesa_mensal(user_email, d_id, row):
    conn = get_connection()
    conn.execute('''
        UPDATE despesas_mensais SET
        data=%s, descricao=%s, valor_original=%s, moeda=%s, cambio_eur=%s, valor_eur=%s,
        usr1=%s, usr2=%s, diferenca_original=%s, status_pago=%s, categoria_final=%s,
        receita=%s, comentarios=%s, conta_bancaria=%s, mes_referencia=%s
        WHERE id=%s AND user_email=%s
    ''', (
        row.get('data'), row.get('descricao'), row.get('valor_original'),
        row.get('moeda'), row.get('cambio_eur'), row.get('valor_eur'),
        row.get('usr1', 0), row.get('usr2', 0), row.get('diferenca_original'),
        row.get('status_pago', 'Pendente'), row.get('categoria_final'),
        1 if row.get('receita') else 0,
        row.get('comentarios'), row.get('conta_bancaria'), row.get('mes_referencia'),
        d_id, user_email,
    ))
    conn.commit()
    conn.close()


def delete_despesa_mensal(user_email, d_id):
    conn = get_connection()
    conn.execute('DELETE FROM despesas_mensais WHERE id=%s AND user_email=%s', (d_id, user_email))
    conn.commit()
    conn.close()


def delete_despesas_mensais_batch(user_email, ids):
    if not ids:
        return
    conn = get_connection()
    conn.execute('DELETE FROM despesas_mensais WHERE id IN %s AND user_email=%s', (tuple(ids), user_email))
    conn.commit()
    conn.close()


def clear_despesas_mensais(user_email, mes=None):
    conn = get_connection()
    if mes:
        conn.execute('DELETE FROM despesas_mensais WHERE user_email=%s AND mes_referencia=%s', (user_email, mes))
    else:
        conn.execute('DELETE FROM despesas_mensais WHERE user_email=%s', (user_email,))
    conn.commit()
    conn.close()


def consolidar_despesas_anuais(user_email, ano):
    conn = get_connection()
    rows = conn.execute('''
        SELECT categoria_final, SUM(usr1) as total_usr1, SUM(usr2) as total_usr2,
               SUM(usr1)+SUM(usr2) as total_geral
        FROM despesas_mensais
        WHERE user_email=%s AND substr(mes_referencia,1,4)=%s
        GROUP BY categoria_final
    ''', (user_email, str(ano))).fetchall()
    conn.execute('DELETE FROM despesas_anuais WHERE user_email=%s AND ano=%s', (user_email, ano))
    for r in rows:
        conn.execute('''
            INSERT INTO despesas_anuais (user_email, ano, categoria_final, total_usr1, total_usr2, total_geral)
            VALUES (%s,%s,%s,%s,%s,%s)
        ''', (user_email, ano, r['categoria_final'], r['total_usr1'], r['total_usr2'], r['total_geral']))
    conn.commit()
    conn.close()
    return len(rows)


def get_consolidacao_tipo_despesa(user_email, mes_referencia):
    conn = get_connection()
    rows = conn.execute('''
        SELECT
            COALESCE(cd.tipo_despesa, 'Sem Tipo') as tipo_despesa,
            dm.moeda,
            SUM(dm.usr1) as total_usr1,
            SUM(dm.usr2) as total_usr2,
            SUM(dm.usr1) + SUM(dm.usr2) as total_geral
        FROM despesas_mensais dm
        LEFT JOIN cad_despesas cd ON cd.despesa = dm.categoria_final
        WHERE dm.user_email = %s AND dm.mes_referencia = %s AND dm.receita = 0
        GROUP BY cd.tipo_despesa, dm.moeda
        ORDER BY cd.tipo_despesa, dm.moeda
    ''', (user_email, mes_referencia)).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_meses_disponiveis(user_email):
    conn = get_connection()
    rows = conn.execute(
        'SELECT DISTINCT mes_referencia FROM despesas_mensais WHERE user_email=%s ORDER BY mes_referencia DESC',
        (user_email,),
    ).fetchall()
    conn.close()
    return [r['mes_referencia'] for r in rows]
