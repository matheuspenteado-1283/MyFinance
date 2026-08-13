import math
from datetime import date

from db.connection import get_connection


def _to_float(value):
    v = float(value or 0)
    return 0.0 if not math.isfinite(v) else v


def _mes_atual():
    return date.today().strftime('%Y-%m')


def _mes_anterior(mes_referencia):
    ano, mes = (int(x) for x in mes_referencia.split('-'))
    if mes == 1:
        return f'{ano - 1}-12'
    return f'{ano}-{mes - 1:02d}'


def init_tables():
    conn = get_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS investimentos_posicoes (
            id SERIAL PRIMARY KEY,
            user_email TEXT,
            banco TEXT,
            tp_investimento TEXT,
            moeda TEXT DEFAULT 'BRL',
            data_inicio TEXT,
            valor_investido_inicial REAL DEFAULT 0,
            ativo INTEGER DEFAULT 1,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS investimentos_mensal (
            id SERIAL PRIMARY KEY,
            posicao_id INTEGER REFERENCES investimentos_posicoes(id) ON DELETE CASCADE,
            user_email TEXT,
            mes_referencia TEXT,
            valor_mercado REAL DEFAULT 0,
            aporte_mes REAL DEFAULT 0,
            resgate_mes REAL DEFAULT 0,
            taxa_mes REAL DEFAULT 0,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(posicao_id, mes_referencia)
        )
    ''')
    conn.commit()
    _migrar_legado(conn)
    conn.close()


def _migrar_legado(conn):
    """Migra lcto_investimentos (modelo antigo, 1 linha mutável por ativo) para
    investimentos_posicoes + investimentos_mensal (série histórica). Idempotente:
    só roda se a tabela legada ainda não foi renomeada."""
    c = conn.cursor()
    c.execute("SELECT to_regclass('lcto_investimentos_legacy')")
    if c.fetchone()['to_regclass']:
        return
    c.execute("SELECT to_regclass('lcto_investimentos')")
    if not c.fetchone()['to_regclass']:
        return

    c.execute('SELECT * FROM lcto_investimentos')
    rows = c.fetchall()
    for row in rows:
        valor_total_inv = (row.get('valor_inv') or 0) * (row.get('qtd') or 0)
        mes_ref = (row.get('data_inv') or '')[:7] or _mes_atual()
        c.execute('''
            INSERT INTO investimentos_posicoes
            (user_email, banco, tp_investimento, moeda, data_inicio, valor_investido_inicial)
            VALUES (%s,%s,%s,%s,%s,%s) RETURNING id
        ''', (row.get('user_email'), row.get('banco'), row.get('tp_investimento'),
              row.get('moeda') or 'BRL', row.get('data_inv'), valor_total_inv))
        posicao_id = c.fetchone()['id']

        val_mes_ant = row.get('val_mes_ant')
        if val_mes_ant:
            mes_ant = _mes_anterior(mes_ref)
            c.execute('''
                INSERT INTO investimentos_mensal (posicao_id, user_email, mes_referencia, valor_mercado)
                VALUES (%s,%s,%s,%s)
                ON CONFLICT (posicao_id, mes_referencia) DO NOTHING
            ''', (posicao_id, row.get('user_email'), mes_ant, val_mes_ant))

        c.execute('''
            INSERT INTO investimentos_mensal
            (posicao_id, user_email, mes_referencia, valor_mercado, aporte_mes, taxa_mes)
            VALUES (%s,%s,%s,%s,%s,%s)
            ON CONFLICT (posicao_id, mes_referencia) DO NOTHING
        ''', (posicao_id, row.get('user_email'), mes_ref, row.get('valor_atual') or 0,
              row.get('aporte') or 0, row.get('taxa') or 0))

    c.execute('ALTER TABLE lcto_investimentos RENAME TO lcto_investimentos_legacy')
    conn.commit()


def _calcular_pnl(valor_investido_inicial, snapshots_ordenados):
    """snapshots_ordenados: lista de dicts (mes_referencia, valor_mercado, aporte_mes,
    resgate_mes, taxa_mes) já ordenados por mes_referencia ascendente.
    Retorna cada snapshot enriquecido com custo_acumulado e pnl_mensal, mais os
    agregados finais (valor_atual, custo_acumulado, pnl_total, pct_rentabilidade)."""
    custo_acumulado = _to_float(valor_investido_inicial)
    valor_anterior = custo_acumulado
    taxas_acumuladas = 0.0
    aportes_acumulados = 0.0
    resgates_acumulados = 0.0
    enriquecidos = []

    for snap in snapshots_ordenados:
        aporte = _to_float(snap.get('aporte_mes'))
        resgate = _to_float(snap.get('resgate_mes'))
        taxa = _to_float(snap.get('taxa_mes'))
        valor_mercado = _to_float(snap.get('valor_mercado'))

        custo_acumulado += aporte - resgate
        taxas_acumuladas += taxa
        aportes_acumulados += aporte
        resgates_acumulados += resgate
        pnl_mensal = valor_mercado - valor_anterior - aporte + resgate

        enriquecido = dict(snap)
        enriquecido['custo_acumulado'] = custo_acumulado
        enriquecido['pnl_mensal'] = pnl_mensal
        enriquecidos.append(enriquecido)

        valor_anterior = valor_mercado

    valor_atual = valor_anterior if snapshots_ordenados else _to_float(valor_investido_inicial)
    pnl_total = valor_atual - custo_acumulado - taxas_acumuladas
    pct_rentabilidade = (pnl_total / custo_acumulado * 100) if custo_acumulado else 0.0

    return {
        'snapshots': enriquecidos,
        'valor_atual': valor_atual,
        'custo_acumulado': custo_acumulado,
        'taxas_acumuladas': taxas_acumuladas,
        'aportes_acumulados': aportes_acumulados,
        'resgates_acumulados': resgates_acumulados,
        'pnl_total': pnl_total,
        'pnl_mensal': enriquecidos[-1]['pnl_mensal'] if enriquecidos else 0.0,
        'pct_rentabilidade': pct_rentabilidade,
    }


def get_all_posicoes(user_email: str):
    conn = get_connection()
    posicoes = conn.execute(
        'SELECT * FROM investimentos_posicoes WHERE user_email=%s AND ativo=1 ORDER BY id DESC',
        (user_email,),
    ).fetchall()

    resultado = []
    for pos in posicoes:
        pos = dict(pos)
        snapshots = conn.execute(
            'SELECT * FROM investimentos_mensal WHERE posicao_id=%s ORDER BY mes_referencia ASC',
            (pos['id'],),
        ).fetchall()
        calc = _calcular_pnl(pos['valor_investido_inicial'], [dict(s) for s in snapshots])
        pos.update({
            'valor_atual': calc['valor_atual'],
            'custo_acumulado': calc['custo_acumulado'],
            'taxas_acumuladas': calc['taxas_acumuladas'],
            'aportes_acumulados': calc['aportes_acumulados'],
            'pnl_total': calc['pnl_total'],
            'pnl_mensal': calc['pnl_mensal'],
            'pct_rentabilidade': calc['pct_rentabilidade'],
            'qtd_meses': len(snapshots),
            'ultimo_mes': snapshots[-1]['mes_referencia'] if snapshots else None,
        })
        resultado.append(pos)
    conn.close()
    return resultado


def add_posicao(user_email, banco, tp_investimento, moeda, data_inicio, valor_investido_inicial):
    conn = get_connection()
    row = conn.execute('''
        INSERT INTO investimentos_posicoes
        (user_email, banco, tp_investimento, moeda, data_inicio, valor_investido_inicial)
        VALUES (%s,%s,%s,%s,%s,%s) RETURNING id
    ''', (user_email, banco, tp_investimento, moeda or 'BRL', data_inicio, valor_investido_inicial or 0)).fetchone()
    conn.commit()
    conn.close()
    return row['id']


def update_posicao(pos_id, user_email, banco, tp_investimento, moeda, data_inicio, valor_investido_inicial):
    conn = get_connection()
    conn.execute('''
        UPDATE investimentos_posicoes SET
        banco=%s, tp_investimento=%s, moeda=%s, data_inicio=%s, valor_investido_inicial=%s
        WHERE id=%s AND user_email=%s
    ''', (banco, tp_investimento, moeda or 'BRL', data_inicio, valor_investido_inicial or 0, pos_id, user_email))
    conn.commit()
    conn.close()


def delete_posicao(pos_id, user_email):
    conn = get_connection()
    conn.execute('DELETE FROM investimentos_posicoes WHERE id=%s AND user_email=%s', (pos_id, user_email))
    conn.commit()
    conn.close()


def clear_posicoes(user_email):
    """Remove todas as posições do usuário (cascade apaga os snapshots mensais)."""
    conn = get_connection()
    conn.execute('DELETE FROM investimentos_posicoes WHERE user_email=%s', (user_email,))
    conn.commit()
    conn.close()


def get_mensal(pos_id: int):
    conn = get_connection()
    rows = conn.execute(
        'SELECT * FROM investimentos_mensal WHERE posicao_id=%s ORDER BY mes_referencia ASC',
        (pos_id,),
    ).fetchall()
    pos = conn.execute(
        'SELECT valor_investido_inicial FROM investimentos_posicoes WHERE id=%s', (pos_id,)
    ).fetchone()
    conn.close()
    valor_inicial = pos['valor_investido_inicial'] if pos else 0
    calc = _calcular_pnl(valor_inicial, [dict(r) for r in rows])
    return calc['snapshots']


def upsert_mensal(pos_id, user_email, mes_referencia, valor_mercado, aporte_mes, resgate_mes, taxa_mes):
    conn = get_connection()
    conn.execute('''
        INSERT INTO investimentos_mensal
        (posicao_id, user_email, mes_referencia, valor_mercado, aporte_mes, resgate_mes, taxa_mes)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (posicao_id, mes_referencia) DO UPDATE SET
            valor_mercado = EXCLUDED.valor_mercado,
            aporte_mes = EXCLUDED.aporte_mes,
            resgate_mes = EXCLUDED.resgate_mes,
            taxa_mes = EXCLUDED.taxa_mes
    ''', (pos_id, user_email, mes_referencia, valor_mercado or 0, aporte_mes or 0,
          resgate_mes or 0, taxa_mes or 0))
    conn.commit()
    conn.close()


def delete_mensal(snapshot_id, user_email):
    conn = get_connection()
    conn.execute('DELETE FROM investimentos_mensal WHERE id=%s AND user_email=%s', (snapshot_id, user_email))
    conn.commit()
    conn.close()


def get_resumo(user_email: str):
    """KPIs consolidados por moeda (sem conversão cambial entre moedas)."""
    posicoes = get_all_posicoes(user_email)
    por_moeda = {}
    for pos in posicoes:
        moeda = (pos.get('moeda') or 'BRL').upper()
        acc = por_moeda.setdefault(moeda, {
            'moeda': moeda, 'valor_investido_inicial': 0.0, 'custo_acumulado': 0.0,
            'valor_atual': 0.0, 'pnl_mensal': 0.0, 'pnl_total': 0.0,
        })
        acc['valor_investido_inicial'] += _to_float(pos.get('valor_investido_inicial'))
        acc['custo_acumulado'] += _to_float(pos.get('custo_acumulado'))
        acc['valor_atual'] += _to_float(pos.get('valor_atual'))
        acc['pnl_mensal'] += _to_float(pos.get('pnl_mensal'))
        acc['pnl_total'] += _to_float(pos.get('pnl_total'))

    for acc in por_moeda.values():
        acc['pct_rentabilidade'] = (acc['pnl_total'] / acc['custo_acumulado'] * 100) if acc['custo_acumulado'] else 0.0

    return {'por_moeda': list(por_moeda.values()), 'posicoes': posicoes}
