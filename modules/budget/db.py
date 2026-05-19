from db.connection import get_connection

MONTHS = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun',
          'jul', 'ago', 'set', 'out', 'nov', 'dez']


def init_tables():
    conn = get_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS budget_items (
            id SERIAL PRIMARY KEY,
            user_email TEXT,
            ano INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            categoria_id INTEGER,
            categoria_nome TEXT NOT NULL,
            tipo_categoria TEXT,
            moeda TEXT DEFAULT 'EUR',
            valor_jan REAL DEFAULT 0,
            valor_fev REAL DEFAULT 0,
            valor_mar REAL DEFAULT 0,
            valor_abr REAL DEFAULT 0,
            valor_mai REAL DEFAULT 0,
            valor_jun REAL DEFAULT 0,
            valor_jul REAL DEFAULT 0,
            valor_ago REAL DEFAULT 0,
            valor_set REAL DEFAULT 0,
            valor_out REAL DEFAULT 0,
            valor_nov REAL DEFAULT 0,
            valor_dez REAL DEFAULT 0,
            variacao_mensal_pct REAL DEFAULT 0,
            variacao_anual_pct REAL DEFAULT 0,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()


def get_budget_items(user_email: str, ano: int, tipo: str):
    conn = get_connection()
    rows = conn.execute(
        '''SELECT * FROM budget_items
           WHERE user_email=%s AND ano=%s AND tipo=%s
           ORDER BY categoria_nome''',
        (user_email, ano, tipo)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_budget_summary(user_email: str, ano: int):
    conn = get_connection()
    rows = conn.execute(
        '''SELECT tipo,
            SUM(valor_jan+valor_fev+valor_mar+valor_abr+valor_mai+valor_jun+
                valor_jul+valor_ago+valor_set+valor_out+valor_nov+valor_dez) as total_anual
           FROM budget_items
           WHERE user_email=%s AND ano=%s
           GROUP BY tipo''',
        (user_email, ano)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def upsert_budget_item(user_email, ano, tipo, categoria_id, categoria_nome,
                       tipo_categoria, moeda, valores_meses,
                       variacao_mensal_pct, variacao_anual_pct):
    conn = get_connection()
    existing = conn.execute(
        'SELECT id FROM budget_items WHERE user_email=%s AND ano=%s AND categoria_nome=%s AND tipo=%s',
        (user_email, ano, categoria_nome, tipo)
    ).fetchone()

    cols_val = {f'valor_{m}': valores_meses.get(m, 0) for m in MONTHS}

    if existing:
        set_clause = ', '.join([f'valor_{m}=%s' for m in MONTHS])
        set_clause += ', variacao_mensal_pct=%s, variacao_anual_pct=%s, moeda=%s, tipo_categoria=%s, categoria_id=%s'
        params = [cols_val[f'valor_{m}'] for m in MONTHS]
        params += [variacao_mensal_pct, variacao_anual_pct, moeda, tipo_categoria, categoria_id,
                   existing['id'], user_email]
        conn.execute(
            f'UPDATE budget_items SET {set_clause} WHERE id=%s AND user_email=%s',
            params
        )
        item_id = existing['id']
    else:
        month_cols = ', '.join([f'valor_{m}' for m in MONTHS])
        month_phs = ', '.join(['%s'] * 12)
        conn.execute(
            f'''INSERT INTO budget_items
                (user_email, ano, tipo, categoria_id, categoria_nome, tipo_categoria, moeda,
                 {month_cols}, variacao_mensal_pct, variacao_anual_pct)
                VALUES (%s,%s,%s,%s,%s,%s,%s,{month_phs},%s,%s)''',
            [user_email, ano, tipo, categoria_id, categoria_nome, tipo_categoria, moeda] +
            [cols_val[f'valor_{m}'] for m in MONTHS] +
            [variacao_mensal_pct, variacao_anual_pct]
        )
        item_id = conn.execute(
            'SELECT id FROM budget_items WHERE user_email=%s AND ano=%s AND categoria_nome=%s AND tipo=%s ORDER BY id DESC LIMIT 1',
            (user_email, ano, categoria_nome, tipo)
        ).fetchone()['id']

    conn.commit()
    conn.close()
    return item_id


def update_budget_item(user_email, item_id, valores_meses, variacao_mensal_pct, variacao_anual_pct, moeda):
    conn = get_connection()
    set_parts = [f'valor_{m}=%s' for m in MONTHS]
    set_parts += ['variacao_mensal_pct=%s', 'variacao_anual_pct=%s', 'moeda=%s']
    params = [valores_meses.get(m, 0) for m in MONTHS]
    params += [variacao_mensal_pct, variacao_anual_pct, moeda, item_id, user_email]
    conn.execute(
        f'UPDATE budget_items SET {", ".join(set_parts)} WHERE id=%s AND user_email=%s',
        params
    )
    conn.commit()
    conn.close()


def delete_budget_item(user_email, item_id):
    conn = get_connection()
    conn.execute('DELETE FROM budget_items WHERE id=%s AND user_email=%s', (item_id, user_email))
    conn.commit()
    conn.close()


def delete_budget_year(user_email, ano, tipo=None):
    conn = get_connection()
    if tipo:
        conn.execute('DELETE FROM budget_items WHERE user_email=%s AND ano=%s AND tipo=%s',
                     (user_email, ano, tipo))
    else:
        conn.execute('DELETE FROM budget_items WHERE user_email=%s AND ano=%s',
                     (user_email, ano))
    conn.commit()
    conn.close()


def bulk_upsert_budget(user_email, ano, tipo, items):
    for item in items:
        upsert_budget_item(
            user_email=user_email,
            ano=ano,
            tipo=tipo,
            categoria_id=item.get('categoria_id'),
            categoria_nome=item.get('categoria_nome', ''),
            tipo_categoria=item.get('tipo_categoria', ''),
            moeda=item.get('moeda', 'EUR'),
            valores_meses={m: item.get(f'valor_{m}', 0) for m in MONTHS},
            variacao_mensal_pct=item.get('variacao_mensal_pct', 0),
            variacao_anual_pct=item.get('variacao_anual_pct', 0),
        )
