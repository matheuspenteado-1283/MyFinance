import math

from db.connection import get_connection


def _clean(row_dict):
    """Converte NaN/Inf para None — evita JSON inválido na serialização Flask."""
    result = {}
    for k, v in row_dict.items():
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            result[k] = None
        else:
            result[k] = v
    return result


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
            'SELECT * FROM despesas_mensais WHERE user_email=%s AND SUBSTR(data, 1, 7)=%s ORDER BY data, id',
            (user_email, mes),
        ).fetchall()
    else:
        rows = conn.execute(
            'SELECT * FROM despesas_mensais WHERE user_email=%s ORDER BY SUBSTR(data, 1, 7) DESC, data, id',
            (user_email,),
        ).fetchall()
    conn.close()
    return [_clean(dict(r)) for r in rows]


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


def check_duplicates_with_data(user_email, candidates):
    """Recebe lista de candidatos {data, descricao, valor_original, moeda, conta_bancaria}.
    Retorna dict {index: dados_salvos} para os que já existem em despesas_mensais."""
    conn = get_connection()
    matches = {}
    for i, c in enumerate(candidates):
        key = _despesa_duplicate_key(user_email, c)
        if not key:
            continue
        _, conta_bancaria, data, descricao, valor_original, moeda = key
        row = conn.execute('''
            SELECT usr1, usr2, categoria_final, receita, comentarios, status_pago, conta_bancaria
            FROM despesas_mensais
            WHERE user_email = %s
              AND TRIM(COALESCE(conta_bancaria, '')) = %s
              AND data = %s
              AND LOWER(TRIM(COALESCE(descricao, ''))) = %s
              AND ABS(COALESCE(valor_original, 0) - %s) < 0.005
              AND UPPER(TRIM(COALESCE(moeda, ''))) = %s
            LIMIT 1
        ''', (user_email, conta_bancaria, data, descricao, valor_original, moeda)).fetchone()
        if row:
            matches[i] = _clean(dict(row))
    conn.close()
    return matches


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
        conn.execute('DELETE FROM despesas_mensais WHERE user_email=%s AND SUBSTR(data, 1, 7)=%s', (user_email, mes))
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
        WHERE dm.user_email = %s AND SUBSTR(dm.data, 1, 7) = %s AND dm.receita = 0
        GROUP BY cd.tipo_despesa, dm.moeda
        ORDER BY cd.tipo_despesa, dm.moeda
    ''', (user_email, mes_referencia)).fetchall()
    conn.close()
    return [_clean(dict(row)) for row in rows]


def get_meses_disponiveis(user_email):
    conn = get_connection()
    rows = conn.execute(
        'SELECT DISTINCT mes_referencia FROM despesas_mensais WHERE user_email=%s ORDER BY mes_referencia DESC',
        (user_email,),
    ).fetchall()
    conn.close()
    return [r['mes_referencia'] for r in rows]


def get_relatorio_mensal_v2(user_email, mes_referencia):
    conn = get_connection()
    c = conn.cursor()

    c.execute(
        'SELECT despesa, tipo_despesa FROM cad_despesas WHERE user_email=%s ORDER BY prioridade, despesa',
        (user_email,)
    )
    all_cats = [dict(r) for r in c.fetchall()]

    c.execute('''
        SELECT categoria_final, moeda,
               COALESCE(SUM(CAST(usr1 AS NUMERIC)), 0) as total_usr1,
               COALESCE(SUM(CAST(usr2 AS NUMERIC)), 0) as total_usr2,
               COALESCE(SUM(valor_original), 0) as total_original
        FROM despesas_mensais
        WHERE user_email=%s AND SUBSTR(data, 1, 7)=%s AND receita=0
        GROUP BY categoria_final, moeda
        ORDER BY categoria_final, moeda
    ''', (user_email, mes_referencia))
    despesas_rows = [dict(r) for r in c.fetchall()]

    c.execute(
        'SELECT chave_usr1, chave_usr2 FROM cad_usuarios WHERE user_email=%s ORDER BY id ASC',
        (user_email,)
    )
    all_users = [dict(r) for r in c.fetchall()]
    usr1_nome = next((r['chave_usr1'] for r in all_users if r.get('chave_usr1')), 'USR1')
    usr2_nome = next((r['chave_usr2'] for r in all_users if r.get('chave_usr2')), 'USR2')

    conn.close()

    data_map = {}
    currencies_set = set()
    for d in despesas_rows:
        cat = d['categoria_final'] or 'Sem Categoria'
        moeda = d['moeda'] or 'EUR'
        currencies_set.add(moeda)
        if cat not in data_map:
            data_map[cat] = {}
        data_map[cat][moeda] = {
            'usr1': float(d['total_usr1'] or 0),
            'usr2': float(d['total_usr2'] or 0),
            'total': float(d['total_original'] or 0),
        }

    currencies = sorted(currencies_set)

    rows = []
    for cat_info in all_cats:
        cat = cat_info['despesa']
        valores = {}
        for moeda in currencies:
            valores[moeda] = data_map.get(cat, {}).get(moeda, {'usr1': 0, 'usr2': 0, 'total': 0})
        rows.append({
            'categoria': cat,
            'tipo_despesa': cat_info['tipo_despesa'] or '',
            'valores': valores,
        })

    cards = {}
    for moeda in currencies:
        u1 = sum(float(d.get('total_usr1') or 0) for d in despesas_rows if d['moeda'] == moeda)
        u2 = sum(float(d.get('total_usr2') or 0) for d in despesas_rows if d['moeda'] == moeda)
        t = sum(float(d.get('total_original') or 0) for d in despesas_rows if d['moeda'] == moeda)
        cards[moeda] = {'usr1': u1, 'usr2': u2, 'total': t}

    return {
        'rows': rows,
        'currencies': currencies,
        'cards': cards,
        'usr1_nome': usr1_nome,
        'usr2_nome': usr2_nome,
    }
