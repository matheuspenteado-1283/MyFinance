import re

from db.connection import get_connection

_DDMM = re.compile(r'^(\d{2})/(\d{2})/(\d{4})$')


def _norm_data(d):
    """Normaliza data DD/MM/AAAA -> AAAA-MM-DD. Passa o resto inalterado."""
    if not d:
        return d
    s = str(d).strip()
    m = _DDMM.match(s)
    if m:
        return f'{m.group(3)}-{m.group(2)}-{m.group(1)}'
    return s


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
            pagador_usr TEXT,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute('ALTER TABLE receitas_mensais ADD COLUMN IF NOT EXISTS pagador_usr TEXT')
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


def _normalize_pagador(value):
    v = (value or '').strip().lower() if isinstance(value, str) else value
    return v if v in ('usr1', 'usr2') else None


def add_receita_mensal(user_email, row):
    conn = get_connection()
    conn.execute('''
        INSERT INTO receitas_mensais
        (user_email, data, tipo_receita, valor_original, moeda_original, cotacao, valor_eur, valor_brl,
         conta_bancaria, mes_referencia, despesa_mensal_id, comentarios, pagador_usr)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    ''', (
        user_email,
        _norm_data(row.get('data')), row.get('tipo_receita'), row.get('valor_original'),
        row.get('moeda_original'), row.get('cotacao', 1), row.get('valor_eur'),
        row.get('valor_brl'), row.get('conta_bancaria'), row.get('mes_referencia'),
        row.get('despesa_mensal_id'), row.get('comentarios'),
        _normalize_pagador(row.get('pagador_usr')),
    ))
    conn.commit()
    conn.close()


def update_receita_mensal(user_email, r_id, row):
    conn = get_connection()
    conn.execute('''
        UPDATE receitas_mensais SET
        data=%s, tipo_receita=%s, valor_original=%s, moeda_original=%s, cotacao=%s, valor_eur=%s, valor_brl=%s,
        conta_bancaria=%s, mes_referencia=%s, comentarios=%s, pagador_usr=%s
        WHERE id=%s AND user_email=%s
    ''', (
        _norm_data(row.get('data')), row.get('tipo_receita'), row.get('valor_original'),
        row.get('moeda_original'), row.get('cotacao', 1), row.get('valor_eur'),
        row.get('valor_brl'), row.get('conta_bancaria'), row.get('mes_referencia'),
        row.get('comentarios'), _normalize_pagador(row.get('pagador_usr')),
        r_id, user_email,
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


def get_relatorio_receitas_v2(user_email, mes_referencia):
    conn = get_connection()
    c = conn.cursor()

    # Todas as categorias cadastradas (mesmo sem lançamento)
    c.execute(
        'SELECT descricao FROM cad_receitas WHERE user_email=%s ORDER BY descricao',
        (user_email,)
    )
    all_cats = [dict(r) for r in c.fetchall()]

    # Receitas do mês agrupadas por tipo + moeda
    c.execute('''
        SELECT tipo_receita, moeda_original,
               COALESCE(SUM(valor_original), 0) as total_original,
               COALESCE(SUM(valor_eur), 0)      as total_eur,
               COALESCE(SUM(valor_brl), 0)      as total_brl
        FROM receitas_mensais
        WHERE user_email=%s AND mes_referencia=%s
        GROUP BY tipo_receita, moeda_original
        ORDER BY tipo_receita, moeda_original
    ''', (user_email, mes_referencia))
    rec_rows = [dict(r) for r in c.fetchall()]
    conn.close()

    data_map = {}
    currencies_set = set()
    for r in rec_rows:
        cat   = r['tipo_receita']    or 'Sem Categoria'
        moeda = r['moeda_original']  or 'EUR'
        currencies_set.add(moeda)
        data_map.setdefault(cat, {})[moeda] = {
            'total':     float(r['total_original'] or 0),
            'total_eur': float(r['total_eur']      or 0),
            'total_brl': float(r['total_brl']      or 0),
        }

    currencies = sorted(currencies_set)

    rows = []
    for cat_info in all_cats:
        cat    = cat_info['descricao']
        valores = {
            m: data_map.get(cat, {}).get(m, {'total': 0, 'total_eur': 0, 'total_brl': 0})
            for m in currencies
        }
        rows.append({'categoria': cat, 'valores': valores})

    # Adiciona categorias com lançamentos mas sem cadastro (não deixa sumir)
    cats_cadastradas = {r['categoria'] for r in rows}
    for r in rec_rows:
        cat = r['tipo_receita'] or 'Sem Categoria'
        if cat not in cats_cadastradas:
            valores = {
                m: data_map.get(cat, {}).get(m, {'total': 0, 'total_eur': 0, 'total_brl': 0})
                for m in currencies
            }
            rows.append({'categoria': cat, 'valores': valores})
            cats_cadastradas.add(cat)

    cards = {
        m: {'total': sum(float(r['total_original'] or 0) for r in rec_rows if r['moeda_original'] == m)}
        for m in currencies
    }

    return {'rows': rows, 'currencies': currencies, 'cards': cards}
