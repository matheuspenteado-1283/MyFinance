import math
from datetime import date

from db.connection import get_connection

# Moeda-âncora usada para "congelar" valores no momento do registo (mesmo padrão já
# usado por despesas/receitas: valor_original + moeda + valor_eur). A "moeda base"
# escolhida pelo usuário (modules.settings) é aplicada só na camada de apresentação,
# convertendo o total já congelado em EUR uma única vez — nunca reconverte histórico.
MOEDA_ANCORA = 'EUR'


def _to_float(value):
    v = float(value or 0)
    return 0.0 if not math.isfinite(v) else v


def _mes_atual():
    return date.today().strftime('%Y-%m')


def init_tables():
    conn = get_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS reservas_posicoes (
            id SERIAL PRIMARY KEY,
            user_email TEXT,
            banco TEXT,
            tp_reserva TEXT,
            moeda TEXT DEFAULT 'BRL',
            data_inicio TEXT,
            valor_investido_inicial REAL DEFAULT 0,
            valor_investido_inicial_eur REAL DEFAULT 0,
            cambio_eur_inicio REAL DEFAULT 1,
            ativo INTEGER DEFAULT 1,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS reservas_mensal (
            id SERIAL PRIMARY KEY,
            posicao_id INTEGER REFERENCES reservas_posicoes(id) ON DELETE CASCADE,
            user_email TEXT,
            mes_referencia TEXT,
            valor_mercado REAL DEFAULT 0,
            valor_mercado_eur REAL DEFAULT 0,
            aporte_mes REAL DEFAULT 0,
            aporte_mes_eur REAL DEFAULT 0,
            resgate_mes REAL DEFAULT 0,
            resgate_mes_eur REAL DEFAULT 0,
            taxa_mes REAL DEFAULT 0,
            cambio_eur REAL DEFAULT 1,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(posicao_id, mes_referencia)
        )
    ''')
    conn.commit()
    conn.close()


def _calcular_pnl(valor_investido_inicial, valor_investido_inicial_eur, snapshots_ordenados):
    """snapshots_ordenados: lista de dicts (mes_referencia, valor_mercado[_eur], aporte_mes[_eur],
    resgate_mes[_eur], taxa_mes, cambio_eur) já ordenados por mes_referencia ascendente.
    Calcula os agregados em duas trilhas paralelas: moeda nativa (para os cards por moeda)
    e EUR (moeda-âncora, para os totais consolidados e o dashboard)."""
    custo_acumulado = _to_float(valor_investido_inicial)
    custo_acumulado_eur = _to_float(valor_investido_inicial_eur)
    valor_anterior = custo_acumulado
    valor_anterior_eur = custo_acumulado_eur
    taxas_acumuladas = 0.0
    taxas_acumuladas_eur = 0.0
    aportes_acumulados = 0.0
    aportes_acumulados_eur = 0.0
    resgates_acumulados = 0.0
    enriquecidos = []

    for snap in snapshots_ordenados:
        aporte = _to_float(snap.get('aporte_mes'))
        aporte_eur = _to_float(snap.get('aporte_mes_eur'))
        resgate = _to_float(snap.get('resgate_mes'))
        resgate_eur = _to_float(snap.get('resgate_mes_eur'))
        taxa = _to_float(snap.get('taxa_mes'))
        cambio = _to_float(snap.get('cambio_eur')) or 1.0
        valor_mercado = _to_float(snap.get('valor_mercado'))
        valor_mercado_eur = _to_float(snap.get('valor_mercado_eur'))

        custo_acumulado += aporte - resgate
        custo_acumulado_eur += aporte_eur - resgate_eur
        taxas_acumuladas += taxa
        taxas_acumuladas_eur += taxa * cambio
        aportes_acumulados += aporte
        aportes_acumulados_eur += aporte_eur
        resgates_acumulados += resgate
        pnl_mensal = valor_mercado - valor_anterior - aporte + resgate

        enriquecido = dict(snap)
        enriquecido['custo_acumulado'] = custo_acumulado
        enriquecido['pnl_mensal'] = pnl_mensal
        enriquecidos.append(enriquecido)

        valor_anterior = valor_mercado
        valor_anterior_eur = valor_mercado_eur

    valor_atual = valor_anterior if snapshots_ordenados else _to_float(valor_investido_inicial)
    valor_atual_eur = valor_anterior_eur if snapshots_ordenados else _to_float(valor_investido_inicial_eur)
    pnl_total = valor_atual - custo_acumulado - taxas_acumuladas
    pnl_total_eur = valor_atual_eur - custo_acumulado_eur - taxas_acumuladas_eur
    pct_rentabilidade = (pnl_total / custo_acumulado * 100) if custo_acumulado else 0.0

    return {
        'snapshots': enriquecidos,
        'valor_atual': valor_atual,
        'valor_atual_eur': valor_atual_eur,
        'custo_acumulado': custo_acumulado,
        'custo_acumulado_eur': custo_acumulado_eur,
        'taxas_acumuladas': taxas_acumuladas,
        'taxas_acumuladas_eur': taxas_acumuladas_eur,
        'aportes_acumulados': aportes_acumulados,
        'aportes_acumulados_eur': aportes_acumulados_eur,
        'resgates_acumulados': resgates_acumulados,
        'pnl_total': pnl_total,
        'pnl_total_eur': pnl_total_eur,
        'pnl_mensal': enriquecidos[-1]['pnl_mensal'] if enriquecidos else 0.0,
        'pct_rentabilidade': pct_rentabilidade,
    }


def _investimentos_como_reservas(user_email: str):
    """Lê as posições de Investimentos (fonte de verdade lá) e devolve-as no formato
    de posição de Reservas, só para leitura/exibição — nada é persistido aqui. Os
    campos _eur são recalculados com a cotação ATUAL (get_exchange_rate 'latest'),
    pois Investimentos não guarda histórico de câmbio por mês como Reservas faz
    (congelamento); é uma aproximação aceite só para exibição e total consolidado."""
    from modules.investimentos.db import get_all_posicoes as get_all_investimentos
    from exchange_api import get_exchange_rate

    investimentos = get_all_investimentos(user_email)
    cache_rate = {}
    resultado = []
    for pos in investimentos:
        pos = dict(pos)
        moeda = (pos.get('moeda') or 'BRL').upper()
        if moeda not in cache_rate:
            cache_rate[moeda] = (
                get_exchange_rate('latest', moeda, MOEDA_ANCORA) if moeda != MOEDA_ANCORA else 1.0
            )
        rate = cache_rate[moeda]

        pos['moeda'] = moeda
        pos['tp_reserva'] = pos.pop('tp_investimento', None)
        pos['origem'] = 'investimentos'
        pos['valor_investido_inicial_eur'] = _to_float(pos.get('valor_investido_inicial')) * rate
        pos['valor_atual_eur'] = _to_float(pos.get('valor_atual')) * rate
        pos['custo_acumulado_eur'] = _to_float(pos.get('custo_acumulado')) * rate
        pos['pnl_total_eur'] = pos['valor_atual_eur'] - pos['custo_acumulado_eur'] - _to_float(pos.get('taxas_acumuladas')) * rate
        resultado.append(pos)
    return resultado


def get_all_posicoes(user_email: str):
    conn = get_connection()
    posicoes = conn.execute(
        'SELECT * FROM reservas_posicoes WHERE user_email=%s AND ativo=1 ORDER BY id DESC',
        (user_email,),
    ).fetchall()

    resultado = []
    for pos in posicoes:
        pos = dict(pos)
        pos['origem'] = 'manual'
        snapshots = conn.execute(
            'SELECT * FROM reservas_mensal WHERE posicao_id=%s ORDER BY mes_referencia ASC',
            (pos['id'],),
        ).fetchall()
        calc = _calcular_pnl(
            pos['valor_investido_inicial'], pos.get('valor_investido_inicial_eur'),
            [dict(s) for s in snapshots],
        )
        pos.update({
            'valor_atual': calc['valor_atual'],
            'valor_atual_eur': calc['valor_atual_eur'],
            'custo_acumulado': calc['custo_acumulado'],
            'custo_acumulado_eur': calc['custo_acumulado_eur'],
            'taxas_acumuladas': calc['taxas_acumuladas'],
            'taxas_acumuladas_eur': calc['taxas_acumuladas_eur'],
            'aportes_acumulados': calc['aportes_acumulados'],
            'aportes_acumulados_eur': calc['aportes_acumulados_eur'],
            'pnl_total': calc['pnl_total'],
            'pnl_total_eur': calc['pnl_total_eur'],
            'pnl_mensal': calc['pnl_mensal'],
            'pct_rentabilidade': calc['pct_rentabilidade'],
            'qtd_meses': len(snapshots),
            'ultimo_mes': snapshots[-1]['mes_referencia'] if snapshots else None,
        })
        resultado.append(pos)
    conn.close()
    resultado.extend(_investimentos_como_reservas(user_email))
    return resultado


def add_posicao(user_email, banco, tp_reserva, moeda, data_inicio, valor_investido_inicial):
    from exchange_api import get_exchange_rate

    moeda = (moeda or 'BRL').upper()
    valor_investido_inicial = valor_investido_inicial or 0
    data_cambio = (data_inicio or '')[:10] or 'latest'
    rate = get_exchange_rate(data_cambio, moeda, MOEDA_ANCORA) if moeda != MOEDA_ANCORA else 1.0

    conn = get_connection()
    row = conn.execute('''
        INSERT INTO reservas_posicoes
        (user_email, banco, tp_reserva, moeda, data_inicio, valor_investido_inicial,
         valor_investido_inicial_eur, cambio_eur_inicio)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
    ''', (user_email, banco, tp_reserva, moeda, data_inicio, valor_investido_inicial,
          valor_investido_inicial * rate, rate)).fetchone()
    conn.commit()
    conn.close()
    return row['id']


def update_posicao(pos_id, user_email, banco, tp_reserva, moeda, data_inicio, valor_investido_inicial):
    from exchange_api import get_exchange_rate

    moeda = (moeda or 'BRL').upper()
    valor_investido_inicial = valor_investido_inicial or 0
    data_cambio = (data_inicio or '')[:10] or 'latest'
    rate = get_exchange_rate(data_cambio, moeda, MOEDA_ANCORA) if moeda != MOEDA_ANCORA else 1.0

    conn = get_connection()
    conn.execute('''
        UPDATE reservas_posicoes SET
        banco=%s, tp_reserva=%s, moeda=%s, data_inicio=%s, valor_investido_inicial=%s,
        valor_investido_inicial_eur=%s, cambio_eur_inicio=%s
        WHERE id=%s AND user_email=%s
    ''', (banco, tp_reserva, moeda, data_inicio, valor_investido_inicial,
          valor_investido_inicial * rate, rate, pos_id, user_email))
    conn.commit()
    conn.close()


def delete_posicao(pos_id, user_email):
    conn = get_connection()
    conn.execute('DELETE FROM reservas_posicoes WHERE id=%s AND user_email=%s', (pos_id, user_email))
    conn.commit()
    conn.close()


def clear_posicoes(user_email):
    """Remove todas as posições do usuário (cascade apaga os snapshots mensais)."""
    conn = get_connection()
    conn.execute('DELETE FROM reservas_posicoes WHERE user_email=%s', (user_email,))
    conn.commit()
    conn.close()


def get_mensal(pos_id: int):
    conn = get_connection()
    rows = conn.execute(
        'SELECT * FROM reservas_mensal WHERE posicao_id=%s ORDER BY mes_referencia ASC',
        (pos_id,),
    ).fetchall()
    pos = conn.execute(
        'SELECT valor_investido_inicial, valor_investido_inicial_eur FROM reservas_posicoes WHERE id=%s',
        (pos_id,),
    ).fetchone()
    conn.close()
    valor_inicial = pos['valor_investido_inicial'] if pos else 0
    valor_inicial_eur = pos['valor_investido_inicial_eur'] if pos else 0
    calc = _calcular_pnl(valor_inicial, valor_inicial_eur, [dict(r) for r in rows])
    return calc['snapshots']


def upsert_mensal(pos_id, user_email, mes_referencia, valor_mercado, aporte_mes, resgate_mes, taxa_mes):
    from exchange_api import get_exchange_rate

    conn = get_connection()
    pos = conn.execute('SELECT moeda FROM reservas_posicoes WHERE id=%s', (pos_id,)).fetchone()
    moeda = ((pos['moeda'] if pos else None) or 'BRL').upper()
    data_cambio = f'{mes_referencia}-01' if mes_referencia else 'latest'
    rate = get_exchange_rate(data_cambio, moeda, MOEDA_ANCORA) if moeda != MOEDA_ANCORA else 1.0

    valor_mercado = valor_mercado or 0
    aporte_mes = aporte_mes or 0
    resgate_mes = resgate_mes or 0
    taxa_mes = taxa_mes or 0

    conn.execute('''
        INSERT INTO reservas_mensal
        (posicao_id, user_email, mes_referencia, valor_mercado, valor_mercado_eur,
         aporte_mes, aporte_mes_eur, resgate_mes, resgate_mes_eur, taxa_mes, cambio_eur)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (posicao_id, mes_referencia) DO UPDATE SET
            valor_mercado = EXCLUDED.valor_mercado,
            valor_mercado_eur = EXCLUDED.valor_mercado_eur,
            aporte_mes = EXCLUDED.aporte_mes,
            aporte_mes_eur = EXCLUDED.aporte_mes_eur,
            resgate_mes = EXCLUDED.resgate_mes,
            resgate_mes_eur = EXCLUDED.resgate_mes_eur,
            taxa_mes = EXCLUDED.taxa_mes,
            cambio_eur = EXCLUDED.cambio_eur
    ''', (pos_id, user_email, mes_referencia, valor_mercado, valor_mercado * rate,
          aporte_mes, aporte_mes * rate, resgate_mes, resgate_mes * rate, taxa_mes, rate))
    conn.commit()
    conn.close()


def delete_mensal(snapshot_id, user_email):
    conn = get_connection()
    conn.execute('DELETE FROM reservas_mensal WHERE id=%s AND user_email=%s', (snapshot_id, user_email))
    conn.commit()
    conn.close()


def get_resumo(user_email: str, moeda_base=None):
    """KPIs por moeda nativa (sem conversão, para os cards) + um total consolidado
    na moeda base do usuário (uma única conversão, a partir dos valores já
    congelados em EUR)."""
    posicoes = get_all_posicoes(user_email)
    por_moeda = {}
    for pos in posicoes:
        moeda = (pos.get('moeda') or 'BRL').upper()
        acc = por_moeda.setdefault(moeda, {
            'moeda': moeda, 'valor_investido_inicial': 0.0, 'custo_acumulado': 0.0,
            'valor_atual': 0.0, 'pnl_mensal': 0.0, 'pnl_total': 0.0,
            'valor_atual_eur': 0.0,
        })
        acc['valor_investido_inicial'] += _to_float(pos.get('valor_investido_inicial'))
        acc['custo_acumulado'] += _to_float(pos.get('custo_acumulado'))
        acc['valor_atual'] += _to_float(pos.get('valor_atual'))
        acc['pnl_mensal'] += _to_float(pos.get('pnl_mensal'))
        acc['pnl_total'] += _to_float(pos.get('pnl_total'))
        acc['valor_atual_eur'] += _to_float(pos.get('valor_atual_eur'))

    for acc in por_moeda.values():
        acc['pct_rentabilidade'] = (acc['pnl_total'] / acc['custo_acumulado'] * 100) if acc['custo_acumulado'] else 0.0

    if moeda_base is None:
        from modules.settings.db import get_moeda_base
        moeda_base = get_moeda_base(user_email)
    moeda_base = (moeda_base or MOEDA_ANCORA).upper()

    total_eur = sum(_to_float(p.get('valor_atual_eur')) for p in posicoes)
    custo_eur = sum(_to_float(p.get('custo_acumulado_eur')) for p in posicoes)
    pnl_eur = total_eur - custo_eur

    from exchange_api import get_exchange_rate
    rate = get_exchange_rate('latest', MOEDA_ANCORA, moeda_base) if moeda_base != MOEDA_ANCORA else 1.0
    total_consolidado = {
        'moeda': moeda_base,
        'valor_atual': total_eur * rate,
        'custo_acumulado': custo_eur * rate,
        'pnl_total': pnl_eur * rate,
        'pct_rentabilidade': (pnl_eur / custo_eur * 100) if custo_eur else 0.0,
    }

    return {'por_moeda': list(por_moeda.values()), 'posicoes': posicoes, 'total_consolidado': total_consolidado}
