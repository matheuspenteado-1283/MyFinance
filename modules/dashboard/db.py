from db.connection import get_connection


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
