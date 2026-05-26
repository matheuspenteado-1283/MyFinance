import math
from db.connection import get_connection

MONTH_LABELS = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
MONTH_KEYS = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']
USR_VALID = ('all', 'usr1', 'usr2')


def _norm_usr(usr):
    return usr if usr in ('usr1', 'usr2') else 'all'


def _desp_value_expr(usr: str, alias: str = '', value_col: str = 'valor_eur') -> str:
    p = f'{alias}.' if alias else ''
    # Treat NULL and PostgreSQL NaN (stored in REAL columns) as 0
    col_safe = (
        f"CASE WHEN {p}{value_col} IS NULL OR ({p}{value_col})::text = 'NaN' "
        f"THEN 0::numeric ELSE {p}{value_col}::numeric END"
    )
    if usr == 'all':
        return col_safe
    # Safe TEXT→NUMERIC: strip 'nan' strings (pandas artifact) before casting
    def _usr_cast(col):
        return (
            f"COALESCE(CAST(NULLIF(NULLIF(LOWER(TRIM(COALESCE({p}{col}::TEXT, ''))), ''), 'nan') AS NUMERIC), 0)"
        )
    u1 = _usr_cast('usr1')
    u2 = _usr_cast('usr2')
    target = _usr_cast(usr)
    return f'{col_safe} * COALESCE({target} / NULLIF({u1} + {u2}, 0), 0)'


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


def _to_float(value):
    v = float(value or 0)
    return 0.0 if not math.isfinite(v) else v


def _months_for_year(ano):
    return [f'{ano}-{m:02d}' for m in range(1, 13)]


def _budget_month_col(mes):
    try:
        return f"valor_{MONTH_KEYS[int(mes.split('-')[1]) - 1]}"
    except Exception:
        return 'valor_jan'


def _monthly_expenses(conn, user_email, mes, usr='all'):
    usr = _norm_usr(usr)
    expr = _desp_value_expr(usr)
    row = conn.execute(f'''
        SELECT COALESCE(SUM({expr}), 0) AS total
        FROM despesas_mensais
        WHERE user_email=%s AND mes_referencia=%s AND (receita IS NULL OR receita=0)
    ''', (user_email, mes)).fetchone()
    return _to_float(row['total'])


def _monthly_revenues(conn, user_email, mes, usr='all'):
    usr = _norm_usr(usr)
    if usr == 'all':
        row = conn.execute('''
            SELECT COALESCE(SUM(r.valor_eur), 0) AS total
            FROM receitas_mensais r
            WHERE r.user_email=%s AND r.mes_referencia=%s
        ''', (user_email, mes)).fetchone()
    else:
        despesa_value_linked = _desp_value_expr(usr, alias='d')
        rec_value_expr = (
            f"CASE WHEN r.despesa_mensal_id IS NULL THEN r.valor_eur "
            f"ELSE {despesa_value_linked} END"
        )
        row = conn.execute(f'''
            SELECT COALESCE(SUM({rec_value_expr}), 0) AS total
            FROM receitas_mensais r
            LEFT JOIN despesas_mensais d
              ON d.id = r.despesa_mensal_id AND d.user_email = r.user_email
            WHERE r.user_email=%s AND r.mes_referencia=%s
              AND (
                (r.despesa_mensal_id IS NULL AND r.pagador_usr = %s)
                OR r.despesa_mensal_id IS NOT NULL
              )
        ''', (user_email, mes, usr)).fetchone()
    return _to_float(row['total'])


def _investment_summary(conn, user_email):
    row = conn.execute('''
        SELECT
            COALESCE(SUM(COALESCE(valor_atual, 0)), 0) AS valor_atual,
            COALESCE(SUM(CASE WHEN UPPER(COALESCE(moeda, 'BRL')) = 'EUR'
                THEN COALESCE(valor_atual, 0) ELSE 0 END), 0) AS valor_atual_eur,
            COALESCE(SUM(CASE WHEN UPPER(COALESCE(moeda, 'BRL')) != 'EUR'
                THEN COALESCE(valor_atual, 0) ELSE 0 END), 0) AS valor_atual_brl,
            COALESCE(SUM(COALESCE(valor_inv, 0) * COALESCE(qtd, 0)), 0) AS valor_investido,
            COALESCE(SUM(CASE WHEN UPPER(COALESCE(moeda, 'BRL')) = 'EUR'
                THEN COALESCE(valor_inv, 0) * COALESCE(qtd, 0) ELSE 0 END), 0) AS valor_investido_eur,
            COALESCE(SUM(CASE WHEN UPPER(COALESCE(moeda, 'BRL')) != 'EUR'
                THEN COALESCE(valor_inv, 0) * COALESCE(qtd, 0) ELSE 0 END), 0) AS valor_investido_brl,
            COALESCE(SUM(COALESCE(taxa, 0)), 0) AS taxas,
            COALESCE(SUM(COALESCE(aporte, 0)), 0) AS aportes
        FROM lcto_investimentos
        WHERE user_email=%s
    ''', (user_email,)).fetchone()
    valor_atual = _to_float(row['valor_atual'])
    valor_atual_eur = _to_float(row['valor_atual_eur'])
    valor_atual_brl = _to_float(row['valor_atual_brl'])
    valor_investido = _to_float(row['valor_investido'])
    valor_investido_eur = _to_float(row['valor_investido_eur'])
    valor_investido_brl = _to_float(row['valor_investido_brl'])
    taxas = _to_float(row['taxas'])
    pnl = valor_atual - valor_investido - taxas
    pnl_eur = valor_atual_eur - valor_investido_eur
    pnl_brl = valor_atual_brl - valor_investido_brl
    return {
        'valor_atual': valor_atual,
        'valor_atual_eur': valor_atual_eur,
        'valor_atual_brl': valor_atual_brl,
        'valor_investido': valor_investido,
        'valor_investido_eur': valor_investido_eur,
        'valor_investido_brl': valor_investido_brl,
        'taxas': taxas,
        'aportes': _to_float(row['aportes']),
        'pnl': pnl,
        'pnl_eur': pnl_eur,
        'pnl_brl': pnl_brl,
        'pnl_pct': (pnl / valor_investido * 100) if valor_investido else 0,
    }


def _debt_summary(conn, user_email):
    row = conn.execute('''
        SELECT
            COALESCE(SUM(CASE WHEN tipo = 'Empréstimo' THEN valor_operacao ELSE 0 END), 0) AS total_emprestado,
            COALESCE(SUM(CASE WHEN tipo IN ('Pagamento', 'Abatimento') THEN valor_operacao ELSE 0 END), 0) AS total_pago
        FROM lcto_emprestimos
        WHERE user_email=%s
    ''', (user_email,)).fetchone()
    total_emprestado = _to_float(row['total_emprestado'])
    total_pago = _to_float(row['total_pago'])
    saldo = total_emprestado - total_pago
    return {
        'total_emprestado': total_emprestado,
        'total_pago': total_pago,
        'saldo': saldo,
        'saldo_brl': saldo,  # empréstimos sempre em BRL
    }


def _cash_balance_until(conn, user_email, mes, usr='all'):
    usr = _norm_usr(usr)
    desp_expr = _desp_value_expr(usr)
    row = conn.execute(f'''
        SELECT COALESCE(SUM(CASE WHEN receita=0 OR receita IS NULL THEN {desp_expr} ELSE 0 END), 0) AS despesas
        FROM despesas_mensais
        WHERE user_email=%s AND mes_referencia <= %s
    ''', (user_email, mes)).fetchone()

    if usr == 'all':
        rec_row = conn.execute('''
            SELECT COALESCE(SUM(r.valor_eur), 0) AS total
            FROM receitas_mensais r
            WHERE r.user_email=%s AND r.mes_referencia <= %s
        ''', (user_email, mes)).fetchone()
    else:
        despesa_value_linked = _desp_value_expr(usr, alias='d')
        rec_value_expr = (
            f"CASE WHEN r.despesa_mensal_id IS NULL THEN r.valor_eur "
            f"ELSE {despesa_value_linked} END"
        )
        rec_row = conn.execute(f'''
            SELECT COALESCE(SUM({rec_value_expr}), 0) AS total
            FROM receitas_mensais r
            LEFT JOIN despesas_mensais d
              ON d.id = r.despesa_mensal_id AND d.user_email = r.user_email
            WHERE r.user_email=%s AND r.mes_referencia <= %s
              AND (
                (r.despesa_mensal_id IS NULL AND r.pagador_usr = %s)
                OR r.despesa_mensal_id IS NOT NULL
              )
        ''', (user_email, mes, usr)).fetchone()
    return _to_float(rec_row['total']) - _to_float(row['despesas'])


def get_dashboard_expenses(user_email: str, mes: str, ano: int, usr: str = 'all'):
    usr = _norm_usr(usr)
    expr = _desp_value_expr(usr)
    conn = get_connection()
    c = conn.cursor()
    c.execute(f'''
        SELECT COALESCE(categoria_final, 'Sem Categoria') AS categoria, COALESCE(SUM({expr}), 0) AS total
        FROM despesas_mensais
        WHERE user_email=%s AND mes_referencia=%s AND (receita IS NULL OR receita=0)
        GROUP BY COALESCE(categoria_final, 'Sem Categoria')
        ORDER BY total DESC
    ''', (user_email, mes))
    by_category = [dict(r) for r in c.fetchall()]

    c.execute(f'''
        SELECT COALESCE(conta_bancaria, 'Sem Conta') AS conta, COALESCE(SUM({expr}), 0) AS total
        FROM despesas_mensais
        WHERE user_email=%s AND mes_referencia=%s AND (receita IS NULL OR receita=0)
        GROUP BY COALESCE(conta_bancaria, 'Sem Conta')
        ORDER BY total DESC
    ''', (user_email, mes))
    by_account = [dict(r) for r in c.fetchall()]

    c.execute(f'''
        SELECT mes_referencia AS mes, COALESCE(SUM({expr}), 0) AS total
        FROM despesas_mensais
        WHERE user_email=%s AND mes_referencia LIKE %s AND (receita IS NULL OR receita=0)
        GROUP BY mes_referencia
        ORDER BY mes_referencia
    ''', (user_email, f'{ano}-%'))
    monthly_map = {r['mes']: _to_float(r['total']) for r in c.fetchall()}

    c.execute(f'''
        SELECT data, descricao, COALESCE(categoria_final, 'Sem Categoria') AS categoria,
               COALESCE(conta_bancaria, 'Sem Conta') AS conta, {expr} AS valor_eur
        FROM despesas_mensais
        WHERE user_email=%s AND mes_referencia=%s AND (receita IS NULL OR receita=0)
        ORDER BY {expr} DESC
        LIMIT 8
    ''', (user_email, mes))
    top_transactions = [dict(r) for r in c.fetchall()]
    conn.close()

    total = sum(_to_float(r['total']) for r in by_category)
    return {
        'mes': mes,
        'ano': ano,
        'total': total,
        'by_category': by_category,
        'by_account': by_account,
        'monthly': [{'mes': m, 'label': MONTH_LABELS[i], 'total': monthly_map.get(m, 0)} for i, m in enumerate(_months_for_year(ano))],
        'top_transactions': top_transactions,
    }


def get_dashboard_revenues(user_email: str, mes: str, ano: int, usr: str = 'all'):
    usr = _norm_usr(usr)
    conn = get_connection()
    c = conn.cursor()

    if usr == 'all':
        rec_value_expr = 'r.valor_eur'
        rec_filter = ''
        join_clause = ''
    else:
        despesa_value_linked = _desp_value_expr(usr, alias='d')
        rec_value_expr = (
            f"CASE WHEN r.despesa_mensal_id IS NULL THEN r.valor_eur "
            f"ELSE {despesa_value_linked} END"
        )
        rec_filter = (
            " AND ((r.despesa_mensal_id IS NULL AND r.pagador_usr=%s) "
            "OR r.despesa_mensal_id IS NOT NULL)"
        )
        join_clause = (
            " LEFT JOIN despesas_mensais d "
            "ON d.id = r.despesa_mensal_id AND d.user_email = r.user_email"
        )

    base_params = [user_email, mes]
    if usr != 'all':
        base_params.append(usr)

    c.execute(f'''
        SELECT COALESCE(r.tipo_receita, 'Sem Tipo') AS tipo,
               COALESCE(SUM({rec_value_expr}), 0) AS total
        FROM receitas_mensais r{join_clause}
        WHERE r.user_email=%s AND r.mes_referencia=%s{rec_filter}
        GROUP BY COALESCE(r.tipo_receita, 'Sem Tipo')
        ORDER BY total DESC
    ''', tuple(base_params))
    by_type = [dict(r) for r in c.fetchall()]

    year_params = [user_email, f'{ano}-%']
    if usr != 'all':
        year_params.append(usr)
    year_filter = (
        " AND ((r.despesa_mensal_id IS NULL AND r.pagador_usr=%s) "
        "OR r.despesa_mensal_id IS NOT NULL)"
    ) if usr != 'all' else ''
    c.execute(f'''
        SELECT r.mes_referencia AS mes, COALESCE(SUM({rec_value_expr}), 0) AS total
        FROM receitas_mensais r{join_clause}
        WHERE r.user_email=%s AND r.mes_referencia LIKE %s{year_filter}
        GROUP BY r.mes_referencia
        ORDER BY r.mes_referencia
    ''', tuple(year_params))
    monthly_map = {r['mes']: _to_float(r['total']) for r in c.fetchall()}

    c.execute(f'''
        SELECT r.data AS data, COALESCE(r.tipo_receita, 'Sem Tipo') AS tipo,
               COALESCE(r.conta_bancaria, 'Sem Conta') AS conta,
               {rec_value_expr} AS valor_eur, r.moeda_original AS moeda_original
        FROM receitas_mensais r{join_clause}
        WHERE r.user_email=%s AND r.mes_referencia=%s{rec_filter}
        ORDER BY {rec_value_expr} DESC
        LIMIT 8
    ''', tuple(base_params))
    top_transactions = [dict(r) for r in c.fetchall()]
    conn.close()

    total = sum(_to_float(r['total']) for r in by_type)
    months = _months_for_year(ano)
    non_zero = [monthly_map.get(m, 0) for m in months if monthly_map.get(m, 0) > 0]
    return {
        'mes': mes,
        'ano': ano,
        'total': total,
        'media_mensal': sum(non_zero) / len(non_zero) if non_zero else 0,
        'by_type': by_type,
        'monthly': [{'mes': m, 'label': MONTH_LABELS[i], 'total': monthly_map.get(m, 0)} for i, m in enumerate(months)],
        'top_transactions': top_transactions,
    }


def get_dashboard_budget(user_email: str, mes: str, ano: int, usr: str = 'all'):
    usr = _norm_usr(usr)
    desp_expr = _desp_value_expr(usr)
    conn = get_connection()
    month_col = _budget_month_col(mes)
    budget_rows = conn.execute(f'''
        SELECT tipo, categoria_nome, tipo_categoria, COALESCE({month_col}, 0) AS valor_budget
        FROM budget_items
        WHERE user_email=%s AND ano=%s
        ORDER BY tipo, categoria_nome
    ''', (user_email, ano)).fetchall()

    desp_rows = conn.execute(f'''
        SELECT LOWER(TRIM(COALESCE(categoria_final, ''))) AS key, COALESCE(SUM({desp_expr}), 0) AS total
        FROM despesas_mensais
        WHERE user_email=%s AND mes_referencia=%s AND (receita IS NULL OR receita=0)
        GROUP BY LOWER(TRIM(COALESCE(categoria_final, '')))
    ''', (user_email, mes)).fetchall()

    if usr == 'all':
        rec_value_expr = 'r.valor_eur'
        rec_filter = ''
        join_clause = ''
        rec_params = (user_email, mes)
    else:
        despesa_value_linked = _desp_value_expr(usr, alias='d')
        rec_value_expr = (
            f"CASE WHEN r.despesa_mensal_id IS NULL THEN r.valor_eur "
            f"ELSE {despesa_value_linked} END"
        )
        rec_filter = (
            " AND ((r.despesa_mensal_id IS NULL AND r.pagador_usr=%s) "
            "OR r.despesa_mensal_id IS NOT NULL)"
        )
        join_clause = (
            " LEFT JOIN despesas_mensais d "
            "ON d.id = r.despesa_mensal_id AND d.user_email = r.user_email"
        )
        rec_params = (user_email, mes, usr)

    rec_rows = conn.execute(f'''
        SELECT LOWER(TRIM(COALESCE(r.tipo_receita, ''))) AS key,
               COALESCE(SUM({rec_value_expr}), 0) AS total
        FROM receitas_mensais r{join_clause}
        WHERE r.user_email=%s AND r.mes_referencia=%s{rec_filter}
        GROUP BY LOWER(TRIM(COALESCE(r.tipo_receita, '')))
    ''', rec_params).fetchall()
    conn.close()

    desp_map = {r['key']: _to_float(r['total']) for r in desp_rows}
    rec_map = {r['key']: _to_float(r['total']) for r in rec_rows}

    rows = []
    for row in budget_rows:
        b = dict(row)
        key = (b['categoria_nome'] or '').strip().lower()
        real = rec_map.get(key, 0) if b['tipo'] == 'receita' else desp_map.get(key, 0)
        budget = _to_float(b['valor_budget'])
        diff = real - budget
        rows.append({
            'tipo': b['tipo'],
            'categoria': b['categoria_nome'],
            'grupo': b['tipo_categoria'] or '',
            'budget': budget,
            'real': real,
            'diff': diff,
            'used_pct': (real / budget * 100) if budget else 0,
        })

    desp_budget = sum(r['budget'] for r in rows if r['tipo'] == 'despesa')
    desp_real = sum(r['real'] for r in rows if r['tipo'] == 'despesa')
    rec_budget = sum(r['budget'] for r in rows if r['tipo'] == 'receita')
    rec_real = sum(r['real'] for r in rows if r['tipo'] == 'receita')
    return {
        'mes': mes,
        'ano': ano,
        'summary': {
            'despesas_budget': desp_budget,
            'despesas_real': desp_real,
            'receitas_budget': rec_budget,
            'receitas_real': rec_real,
            'saldo_budget': rec_budget - desp_budget,
            'saldo_real': rec_real - desp_real,
            'despesas_used_pct': (desp_real / desp_budget * 100) if desp_budget else 0,
        },
        'rows': rows,
        'top_over': sorted([r for r in rows if r['tipo'] == 'despesa'], key=lambda x: x['diff'], reverse=True)[:8],
    }


def get_dashboard_investments(user_email: str, mes: str, ano: int):
    conn = get_connection()
    c = conn.cursor()
    summary = _investment_summary(conn, user_email)

    c.execute('''
        SELECT COALESCE(tp_investimento, 'Sem Tipo') AS tipo,
               COALESCE(SUM(valor_atual), 0) AS valor_atual,
               COALESCE(SUM(COALESCE(valor_inv, 0) * COALESCE(qtd, 0)), 0) AS valor_investido
        FROM lcto_investimentos
        WHERE user_email=%s
        GROUP BY COALESCE(tp_investimento, 'Sem Tipo')
        ORDER BY valor_atual DESC
    ''', (user_email,))
    by_type = [dict(r) for r in c.fetchall()]

    c.execute('''
        SELECT COALESCE(banco, 'Sem Banco') AS banco, COALESCE(SUM(valor_atual), 0) AS valor_atual
        FROM lcto_investimentos
        WHERE user_email=%s
        GROUP BY COALESCE(banco, 'Sem Banco')
        ORDER BY valor_atual DESC
    ''', (user_email,))
    by_bank = [dict(r) for r in c.fetchall()]

    c.execute('''
        SELECT tp_investimento, banco, moeda, valor_atual,
               COALESCE(valor_inv, 0) * COALESCE(qtd, 0) AS valor_investido,
               COALESCE(valor_atual, 0) - (COALESCE(valor_inv, 0) * COALESCE(qtd, 0)) - COALESCE(taxa, 0) AS pnl
        FROM lcto_investimentos
        WHERE user_email=%s
        ORDER BY valor_atual DESC
        LIMIT 10
    ''', (user_email,))
    positions = [dict(r) for r in c.fetchall()]
    conn.close()
    return {'mes': mes, 'ano': ano, 'summary': summary, 'by_type': by_type, 'by_bank': by_bank, 'positions': positions}


def get_dashboard_pnl(user_email: str, mes: str, ano: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        SELECT COALESCE(tp_investimento, 'Investimentos') AS grupo,
               COALESCE(SUM(valor_atual), 0) - COALESCE(SUM(COALESCE(valor_inv, 0) * COALESCE(qtd, 0)), 0) - COALESCE(SUM(taxa), 0) AS pnl
        FROM lcto_investimentos
        WHERE user_email=%s
        GROUP BY COALESCE(tp_investimento, 'Investimentos')
        ORDER BY pnl DESC
    ''', (user_email,))
    investment_pnl = [dict(r) for r in c.fetchall()]

    pnl_by_cur = conn.execute('''
        SELECT
            CASE WHEN UPPER(COALESCE(moeda, 'BRL')) = 'EUR' THEN 'EUR' ELSE 'BRL' END AS moeda_group,
            COALESCE(SUM(valor_atual), 0) - COALESCE(SUM(COALESCE(valor_inv, 0) * COALESCE(qtd, 0)), 0) - COALESCE(SUM(taxa), 0) AS pnl
        FROM lcto_investimentos
        WHERE user_email=%s
        GROUP BY moeda_group
    ''', (user_email,)).fetchall()
    pnl_invest_eur = sum(_to_float(r['pnl']) for r in pnl_by_cur if r['moeda_group'] == 'EUR')
    pnl_invest_brl = sum(_to_float(r['pnl']) for r in pnl_by_cur if r['moeda_group'] == 'BRL')

    c.execute('''
        SELECT COALESCE(symbol, 'Sem Ativo') AS grupo, COALESCE(SUM(gross_pl), 0) AS pnl
        FROM trader_positions
        WHERE user_email=%s AND (periodo=%s OR open_time LIKE %s OR close_time LIKE %s)
        GROUP BY COALESCE(symbol, 'Sem Ativo')
        ORDER BY pnl DESC
    ''', (user_email, mes, f'{mes}%', f'{mes}%'))
    trader_pnl = [dict(r) for r in c.fetchall()]
    conn.close()

    total_investments = sum(_to_float(r['pnl']) for r in investment_pnl)
    total_trader = sum(_to_float(r['pnl']) for r in trader_pnl)
    combined = [{'origem': 'Investimentos', **r} for r in investment_pnl] + [{'origem': 'Trader', **r} for r in trader_pnl]
    return {
        'mes': mes,
        'ano': ano,
        'summary': {
            'pnl_investimentos': total_investments,
            'pnl_investimentos_eur': pnl_invest_eur,
            'pnl_investimentos_brl': pnl_invest_brl,
            'pnl_trader': total_trader,
            'pnl_total': total_investments + total_trader,
        },
        'by_group': combined,
        'top_gains': sorted(combined, key=lambda x: _to_float(x['pnl']), reverse=True)[:5],
        'top_losses': sorted(combined, key=lambda x: _to_float(x['pnl']))[:5],
    }


def get_dashboard_cashflow(user_email: str, ano: int, usr: str = 'all'):
    usr = _norm_usr(usr)
    conn = get_connection()
    months = _months_for_year(ano)
    rows = []
    saldo = 0
    for i, mes in enumerate(months):
        receitas = _monthly_revenues(conn, user_email, mes, usr)
        despesas = _monthly_expenses(conn, user_email, mes, usr)
        net = receitas - despesas
        saldo += net
        rows.append({
            'mes': mes,
            'label': MONTH_LABELS[i],
            'receitas': receitas,
            'despesas': despesas,
            'saldo_mes': net,
            'saldo_acumulado': saldo,
        })
    conn.close()
    return {
        'ano': ano,
        'rows': rows,
        'summary': {
            'receitas': sum(r['receitas'] for r in rows),
            'despesas': sum(r['despesas'] for r in rows),
            'saldo': sum(r['saldo_mes'] for r in rows),
            'menor_saldo': min([r['saldo_acumulado'] for r in rows], default=0),
        },
    }


def get_dashboard_net_worth(user_email: str, mes: str, ano: int, usr: str = 'all'):
    usr = _norm_usr(usr)
    conn = get_connection()
    investimentos = _investment_summary(conn, user_email)
    dividas = _debt_summary(conn, user_email)
    caixa = _cash_balance_until(conn, user_email, mes, usr)

    cashflow = []
    saldo = 0
    for i, month in enumerate(_months_for_year(ano)):
        saldo += _monthly_revenues(conn, user_email, month, usr) - _monthly_expenses(conn, user_email, month, usr)
        cashflow.append({
            'mes': month,
            'label': MONTH_LABELS[i],
            'caixa_acumulado': saldo,  # em EUR; frontend calcula patrimônio com taxa de câmbio
        })
    conn.close()
    return {
        'mes': mes,
        'ano': ano,
        'summary': {
            'investimentos': investimentos['valor_atual'],
            'investimentos_eur': investimentos['valor_atual_eur'],
            'investimentos_brl': investimentos['valor_atual_brl'],
            'caixa_estimado': caixa,       # em EUR
            'a_receber': dividas['saldo_brl'],
            'a_receber_brl': dividas['saldo_brl'],  # explícito: sempre BRL
            'dividas': dividas['saldo'],   # compat. retroativa
        },
        'composition': [
            {'label': 'Invest. EUR', 'value': investimentos['valor_atual_eur']},
            {'label': 'Invest. BRL', 'value': investimentos['valor_atual_brl']},
            {'label': 'Caixa (EUR)', 'value': caixa},
            {'label': 'A Receber', 'value': dividas['saldo']},
        ],
        'monthly': cashflow,
    }


def get_dashboard_overview(user_email: str, mes: str, ano: int, usr: str = 'all'):
    usr = _norm_usr(usr)
    conn = get_connection()
    receitas = _monthly_revenues(conn, user_email, mes, usr)
    despesas = _monthly_expenses(conn, user_email, mes, usr)
    investimentos = _investment_summary(conn, user_email)
    dividas = _debt_summary(conn, user_email)
    caixa = _cash_balance_until(conn, user_email, mes, usr)
    budget_col = _budget_month_col(mes)
    row = conn.execute(f'''
        SELECT
            COALESCE(SUM(CASE WHEN tipo='despesa' THEN {budget_col} ELSE 0 END), 0) AS budget_despesas,
            COALESCE(SUM(CASE WHEN tipo='receita' THEN {budget_col} ELSE 0 END), 0) AS budget_receitas
        FROM budget_items
        WHERE user_email=%s AND ano=%s
    ''', (user_email, ano)).fetchone()
    conn.close()

    cashflow = get_dashboard_cashflow(user_email, ano, usr)
    budget_despesas = _to_float(row['budget_despesas'])
    budget_receitas = _to_float(row['budget_receitas'])
    saldo = receitas - despesas
    insights = []
    if budget_despesas and despesas > budget_despesas:
        insights.append({'tone': 'negative', 'text': 'Despesas acima do budget mensal.'})
    elif budget_despesas:
        insights.append({'tone': 'positive', 'text': 'Despesas dentro do budget mensal.'})
    if investimentos['pnl'] < 0:
        insights.append({'tone': 'negative', 'text': 'P&L de investimentos está negativo.'})
    elif investimentos['valor_investido']:
        insights.append({'tone': 'positive', 'text': 'Carteira de investimentos com P&L positivo.'})
    if saldo < 0:
        insights.append({'tone': 'warning', 'text': 'Saldo do mês está negativo; revise despesas variáveis.'})
    if not insights:
        insights.append({'tone': 'neutral', 'text': 'Ainda não há dados suficientes para insights automáticos.'})

    return {
        'mes': mes,
        'ano': ano,
        'kpis': {
            'receitas': receitas,
            'despesas': despesas,
            'saldo': saldo,
            'budget_usado_pct': (despesas / budget_despesas * 100) if budget_despesas else 0,
            'budget_despesas': budget_despesas,
            'budget_receitas': budget_receitas,
            'investimentos': investimentos['valor_atual'],
            'investimentos_eur': investimentos['valor_atual_eur'],
            'investimentos_brl': investimentos['valor_atual_brl'],
            'pnl': investimentos['pnl'],
            'pnl_eur': investimentos['pnl_eur'],
            'pnl_brl': investimentos['pnl_brl'],
            'caixa_estimado': caixa,           # em EUR; frontend calcula patrimônio
            'a_receber': dividas['saldo_brl'],
            'a_receber_brl': dividas['saldo_brl'],  # explícito: sempre BRL
            'dividas': dividas['saldo'],       # compat. retroativa
        },
        'cashflow': cashflow['rows'],
        'insights': insights,
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
