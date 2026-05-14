from db.connection import get_connection


def init_tables():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS lcto_impostos (
            id SERIAL PRIMARY KEY,
            user_email TEXT,
            mes_ano TEXT NOT NULL,
            tp_imposto TEXT,
            moeda_faturado TEXT DEFAULT 'EUR',
            valor_faturado REAL DEFAULT 0,
            valor_imposto REAL DEFAULT 0,
            moeda_pagamento TEXT DEFAULT 'EUR',
            pagamento TEXT,
            pagamento_mes_ano TEXT,
            desconto_iva REAL DEFAULT 0,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    # migração de coluna
    try:
        c.execute('SELECT pagamento_mes_ano FROM lcto_impostos LIMIT 1')
    except Exception:
        c.execute('ALTER TABLE lcto_impostos ADD COLUMN pagamento_mes_ano TEXT')
        conn.commit()
    conn.close()


def get_all_lcto_impostos(user_email: str):
    conn = get_connection()
    rows = conn.execute(
        'SELECT * FROM lcto_impostos WHERE user_email=%s ORDER BY mes_ano DESC, tp_imposto',
        (user_email,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_lcto_imposto(user_email, mes_ano, tp_imposto, moeda_faturado, valor_faturado,
                     valor_imposto, moeda_pagamento, pagamento, pagamento_mes_ano, desconto_iva):
    conn = get_connection()
    conn.execute('''
        INSERT INTO lcto_impostos
        (user_email, mes_ano, tp_imposto, moeda_faturado, valor_faturado, valor_imposto,
         moeda_pagamento, pagamento, pagamento_mes_ano, desconto_iva)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ''', (user_email, mes_ano, tp_imposto, moeda_faturado, valor_faturado, valor_imposto,
          moeda_pagamento, pagamento, pagamento_mes_ano, desconto_iva))
    conn.commit()
    conn.close()


def update_lcto_imposto(li_id, mes_ano, tp_imposto, moeda_faturado, valor_faturado,
                        valor_imposto, moeda_pagamento, pagamento, pagamento_mes_ano, desconto_iva):
    conn = get_connection()
    conn.execute('''
        UPDATE lcto_impostos SET
        mes_ano=%s, tp_imposto=%s, moeda_faturado=%s, valor_faturado=%s, valor_imposto=%s,
        moeda_pagamento=%s, pagamento=%s, pagamento_mes_ano=%s, desconto_iva=%s
        WHERE id=%s
    ''', (mes_ano, tp_imposto, moeda_faturado, valor_faturado, valor_imposto,
          moeda_pagamento, pagamento, pagamento_mes_ano, desconto_iva, li_id))
    conn.commit()
    conn.close()


def delete_lcto_imposto(li_id):
    conn = get_connection()
    conn.execute('DELETE FROM lcto_impostos WHERE id=%s', (li_id,))
    conn.commit()
    conn.close()


def get_dashboard_impostos(user_email: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        SELECT
            tp_imposto, pagamento,
            SUM(valor_imposto) as total_imposto,
            SUM(desconto_iva) as total_desconto,
            SUM(valor_imposto - COALESCE(desconto_iva, 0)) as valor_liquido,
            pagamento_mes_ano
        FROM lcto_impostos
        WHERE user_email = %s
        GROUP BY tp_imposto, pagamento, pagamento_mes_ano
        ORDER BY tp_imposto, pagamento_mes_ano DESC
    ''', (user_email,))
    rows = [dict(row) for row in c.fetchall()]
    conn.close()

    tipo_imposto_map = {}
    for r in rows:
        tp = r['tp_imposto'] or 'Não especificado'
        pag = r['pagamento'] or 'Não especificado'
        key = f'{tp}|{pag}'
        if key not in tipo_imposto_map:
            tipo_imposto_map[key] = {'tp_imposto': tp, 'pagamento': pag, 'total_imposto': 0,
                                      'total_desconto': 0, 'valor_liquido': 0, 'periodos': []}
        tipo_imposto_map[key]['total_imposto'] += r['total_imposto'] or 0
        tipo_imposto_map[key]['total_desconto'] += r['total_desconto'] or 0
        tipo_imposto_map[key]['valor_liquido'] += r['valor_liquido'] or 0
        if r['pagamento_mes_ano']:
            tipo_imposto_map[key]['periodos'].append(r['pagamento_mes_ano'])

    return list(tipo_imposto_map.values())
