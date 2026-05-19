from db.connection import get_connection

MONTH_LABELS = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']


def init_tables():
    pass  # tabelas criadas por despesas_mensais e receitas_mensais


def get_dashboard_data(user_email: str, mes_referencia: str):
    conn = get_connection()
    c = conn.cursor()

    c.execute('''
        SELECT categoria_final, SUM(valor_eur) as total
        FROM despesas_mensais
        WHERE user_email = %s AND mes_referencia = %s AND receita = 0
        GROUP BY categoria_final
    ''', (user_email, mes_referencia))
    exp_by_cat = [dict(row) for row in c.fetchall()]

    c.execute('''
        SELECT categoria_final, SUM(valor_eur) as total
        FROM despesas_mensais
        WHERE user_email = %s AND mes_referencia = %s AND receita = 1
        GROUP BY categoria_final
    ''', (user_email, mes_referencia))
    rec_by_cat = [dict(row) for row in c.fetchall()]

    ano = mes_referencia.split('-')[0]
    c.execute('''
        SELECT
            SUM(CASE WHEN receita = 1 THEN valor_eur ELSE 0 END) as total_rec,
            SUM(CASE WHEN receita = 0 THEN valor_eur ELSE 0 END) as total_exp
        FROM despesas_mensais
        WHERE user_email = %s AND mes_referencia LIKE %s
    ''', (user_email, f'{ano}-%'))
    row = c.fetchone()
    annual_net = (row['total_rec'] or 0) - (row['total_exp'] or 0)

    conn.close()
    return {
        'expenses_by_category': exp_by_cat,
        'revenues_by_category': rec_by_cat,
        'annual_net': annual_net,
        'ano': ano,
        'mes': mes_referencia,
    }


def get_annual_report(user_email: str, ano: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        SELECT categoria_final, total_usr1, total_usr2, total_geral
        FROM despesas_anuais
        WHERE user_email = %s AND ano = %s
        ORDER BY total_geral DESC
    ''', (user_email, ano))
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return rows


def get_relatorio_anual_despesas(user_email: str, ano: int):
    conn = get_connection()
    c = conn.cursor()

    c.execute(
        'SELECT despesa, tipo_despesa FROM cad_despesas WHERE user_email=%s ORDER BY prioridade, despesa',
        (user_email,)
    )
    all_cats = [dict(r) for r in c.fetchall()]

    c.execute(
        'SELECT chave_usr1, chave_usr2 FROM cad_usuarios WHERE user_email=%s ORDER BY id ASC',
        (user_email,)
    )
    all_users = [dict(r) for r in c.fetchall()]
    usr1_nome = next((r['chave_usr1'] for r in all_users if r.get('chave_usr1')), 'USR1')
    usr2_nome = next((r['chave_usr2'] for r in all_users if r.get('chave_usr2')), 'USR2')

    c.execute('''
        SELECT categoria_final, mes_referencia, moeda,
               COALESCE(SUM(CAST(usr1 AS NUMERIC)), 0) as total_usr1,
               COALESCE(SUM(CAST(usr2 AS NUMERIC)), 0) as total_usr2,
               COALESCE(SUM(valor_original), 0) as total_original
        FROM despesas_mensais
        WHERE user_email=%s AND mes_referencia LIKE %s AND receita=0
        GROUP BY categoria_final, mes_referencia, moeda
        ORDER BY categoria_final, mes_referencia, moeda
    ''', (user_email, f'{ano}-%'))
    raw_rows = [dict(r) for r in c.fetchall()]
    conn.close()

    months = [f'{ano}-{m:02d}' for m in range(1, 13)]

    data_map = {}
    currencies_set = set()
    for d in raw_rows:
        cat = d['categoria_final'] or 'Sem Categoria'
        moeda = d['moeda'] or 'EUR'
        mes = d['mes_referencia']
        currencies_set.add(moeda)
        data_map.setdefault(cat, {}).setdefault(moeda, {})[mes] = {
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
            moeda_data = data_map.get(cat, {}).get(moeda, {})
            mes_vals = {}
            t_usr1 = t_usr2 = t_total = 0
            n_meses = 0
            for mes in months:
                v = moeda_data.get(mes, {'usr1': 0, 'usr2': 0, 'total': 0})
                mes_vals[mes] = v
                t_usr1 += v['usr1']
                t_usr2 += v['usr2']
                t_total += v['total']
                if v['total'] > 0:
                    n_meses += 1
            valores[moeda] = {
                'meses': mes_vals,
                'total_usr1': t_usr1,
                'total_usr2': t_usr2,
                'total': t_total,
                'media': t_total / 12,
                'meses_com_dados': n_meses,
            }
        rows.append({
            'categoria': cat,
            'tipo_despesa': cat_info['tipo_despesa'] or '',
            'valores': valores,
        })

    cards = {}
    for moeda in currencies:
        total_m = sum(float(d['total_original'] or 0) for d in raw_rows if d['moeda'] == moeda)
        meses_m = {d['mes_referencia'] for d in raw_rows if d['moeda'] == moeda and float(d['total_original'] or 0) > 0}
        cards[moeda] = {
            'total': total_m,
            'media_mensal': total_m / 12,
            'meses_com_dados': len(meses_m),
        }

    return {
        'currencies': currencies,
        'months': months,
        'month_labels': MONTH_LABELS,
        'rows': rows,
        'cards': cards,
        'usr1_nome': usr1_nome,
        'usr2_nome': usr2_nome,
        'ano': ano,
    }


def get_relatorio_anual_receitas(user_email: str, ano: int):
    conn = get_connection()
    c = conn.cursor()

    c.execute('''
        SELECT tipo_receita, mes_referencia, moeda_original,
               COALESCE(SUM(valor_original), 0) as total_original
        FROM receitas_mensais
        WHERE user_email=%s AND mes_referencia LIKE %s
        GROUP BY tipo_receita, mes_referencia, moeda_original
        ORDER BY tipo_receita, mes_referencia, moeda_original
    ''', (user_email, f'{ano}-%'))
    raw_rows = [dict(r) for r in c.fetchall()]
    conn.close()

    months = [f'{ano}-{m:02d}' for m in range(1, 13)]

    data_map = {}
    currencies_set = set()
    tipos_seen = set()

    for d in raw_rows:
        tipo = d['tipo_receita'] or 'Sem Tipo'
        moeda = d['moeda_original'] or 'EUR'
        mes = d['mes_referencia']
        currencies_set.add(moeda)
        tipos_seen.add(tipo)
        data_map.setdefault(tipo, {}).setdefault(moeda, {})[mes] = float(d['total_original'] or 0)

    currencies = sorted(currencies_set)

    rows = []
    for tipo in sorted(tipos_seen):
        valores = {}
        for moeda in currencies:
            moeda_data = data_map.get(tipo, {}).get(moeda, {})
            mes_vals = {}
            t_total = 0
            n_meses = 0
            for mes in months:
                v = moeda_data.get(mes, 0)
                mes_vals[mes] = v
                t_total += v
                if v > 0:
                    n_meses += 1
            valores[moeda] = {
                'meses': mes_vals,
                'total': t_total,
                'media': t_total / 12,
                'meses_com_dados': n_meses,
            }
        rows.append({'tipo': tipo, 'valores': valores})

    cards = {}
    for moeda in currencies:
        total_m = sum(float(d['total_original'] or 0) for d in raw_rows if d['moeda_original'] == moeda)
        meses_m = {d['mes_referencia'] for d in raw_rows if d['moeda_original'] == moeda and float(d['total_original'] or 0) > 0}
        cards[moeda] = {
            'total': total_m,
            'media_mensal': total_m / 12,
            'meses_com_dados': len(meses_m),
        }

    return {
        'currencies': currencies,
        'months': months,
        'month_labels': MONTH_LABELS,
        'rows': rows,
        'cards': cards,
        'ano': ano,
    }
