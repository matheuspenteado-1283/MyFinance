import json
from db.connection import get_connection


def init_tables():
    conn = get_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS relatorios_configurados (
            id SERIAL PRIMARY KEY,
            user_email TEXT,
            nome_relatorio TEXT,
            tabelas TEXT,
            campos TEXT,
            agrupador TEXT,
            mes_inicio TEXT,
            mes_fim TEXT,
            moedas TEXT,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()


def save_relatorio_dinamico(user_email, nome, tabelas, campos, agrupador, mes_inicio, mes_fim, moedas):
    conn = get_connection()
    conn.execute('''
        INSERT INTO relatorios_configurados
        (user_email, nome_relatorio, tabelas, campos, agrupador, mes_inicio, mes_fim, moedas)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    ''', (user_email, nome, json.dumps(tabelas), json.dumps(campos), agrupador, mes_inicio, mes_fim, json.dumps(moedas)))
    conn.commit()
    conn.close()


def get_all_relatorios_dinamicos(user_email):
    conn = get_connection()
    rows = conn.execute(
        'SELECT * FROM relatorios_configurados WHERE user_email=%s ORDER BY criado_em DESC',
        (user_email,),
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        row = dict(r)
        row['tabelas'] = json.loads(row['tabelas']) if row.get('tabelas') else []
        row['campos'] = json.loads(row['campos']) if row.get('campos') else []
        row['moedas'] = json.loads(row['moedas']) if row.get('moedas') else []
        result.append(row)
    return result


def delete_relatorio_dinamico(user_email, r_id):
    conn = get_connection()
    conn.execute('DELETE FROM relatorios_configurados WHERE id=%s AND user_email=%s', (r_id, user_email))
    conn.commit()
    conn.close()


def get_tabelas_campos():
    return {
        'despesas_mensais': ['data', 'descricao', 'valor_original', 'moeda', 'cambio_eur', 'valor_eur', 'usr1', 'usr2', 'categoria_final', 'status_pago', 'receita', 'conta_bancaria', 'mes_referencia'],
        'receitas_mensais': ['data', 'tipo_receita', 'valor_original', 'moeda_original', 'cotacao', 'valor_eur', 'valor_brl', 'conta_bancaria', 'mes_referencia'],
        'lcto_impostos': ['mes_ano', 'tp_imposto', 'moeda_faturado', 'valor_faturado', 'valor_imposto', 'moeda_pagamento', 'pagamento', 'pagamento_mes_ano', 'desconto_iva'],
        'lcto_emprestimos': ['tipo', 'beneficiario', 'valor_operacao', 'moeda_emp', 'data_emprestimo', 'data_operacao', 'obs', 'status'],
        'lcto_investimentos': ['banco', 'tp_investimento', 'data_inv', 'valor_inv', 'moeda', 'qtd', 'taxa', 'valor_atual', 'val_mes_ant', 'aporte'],
        'cad_despesas': ['id', 'despesa', 'tipo_despesa', 'fator_divisao', 'prioridade'],
        'cad_contas': ['id', 'descricao', 'agencia', 'conta', 'dados_acesso', 'senha', 'comentarios'],
        'cad_receitas': ['id', 'descricao'],
        'cad_investimentos': ['id', 'descricao'],
        'cad_usuarios': ['id', 'chave_usr1', 'chave_usr2', 'nome', 'fator_pagamento'],
        'tb_tipo_imposto': ['id', 'tp_imposto', 'alq_imposto', 'pagamento'],
    }


def get_dados_relatorio_dinamico(user_email, tabelas, campos, agrupador, mes_inicio, mes_fim, moedas):
    conn = get_connection()
    c = conn.cursor()

    resultado = {}
    meses_periodo = []

    if mes_inicio and mes_fim and mes_inicio <= mes_fim:
        try:
            mes_atual = mes_inicio
            while mes_atual <= mes_fim:
                meses_periodo.append(mes_atual)
                ano = mes_atual.split('-')[0]
                mes_num = int(mes_atual.split('-')[1])
                mes_atual = f'{ano}-{mes_num + 1:02d}' if mes_num < 12 else f'{int(ano) + 1}-01'
        except Exception as e:
            print(f'Erro ao gerar meses: {e}')
            meses_periodo = []

    agrupadores_encontrados = set()

    for tabela in tabelas:
        if tabela == 'despesas_mensais':
            c.execute('''
                SELECT categoria_final, mes_referencia, SUM(valor_original) as valor_original,
                       SUM(valor_eur) as valor_eur, moeda
                FROM despesas_mensais
                WHERE user_email=%s AND mes_referencia >= %s AND mes_referencia <= %s
                GROUP BY categoria_final, mes_referencia, moeda
            ''', (user_email, mes_inicio, mes_fim))
            for row in c.fetchall():
                agr = row['categoria_final'] or 'Sem Categoria'
                agrupadores_encontrados.add(agr)
                if agr not in resultado:
                    resultado[agr] = {'valores': {}, 'moedas': set()}
                if row['mes_referencia'] not in resultado[agr]['valores']:
                    resultado[agr]['valores'][row['mes_referencia']] = {}
                resultado[agr]['valores'][row['mes_referencia']][row['moeda']] = row['valor_original']
                resultado[agr]['valores'][row['mes_referencia']]['EUR'] = row['valor_eur']
                resultado[agr]['moedas'].add(row['moeda'])

        elif tabela == 'receitas_mensais':
            c.execute('''
                SELECT tipo_receita, mes_referencia, SUM(valor_original) as valor_original,
                       SUM(valor_eur) as valor_eur, SUM(valor_brl) as valor_brl, moeda_original
                FROM receitas_mensais
                WHERE user_email=%s AND mes_referencia >= %s AND mes_referencia <= %s
                GROUP BY tipo_receita, mes_referencia, moeda_original
            ''', (user_email, mes_inicio, mes_fim))
            for row in c.fetchall():
                agr = row['tipo_receita'] or 'Sem Tipo'
                agrupadores_encontrados.add(agr)
                if agr not in resultado:
                    resultado[agr] = {'valores': {}, 'moedas': set()}
                if row['mes_referencia'] not in resultado[agr]['valores']:
                    resultado[agr]['valores'][row['mes_referencia']] = {}
                resultado[agr]['valores'][row['mes_referencia']][row['moeda_original']] = row['valor_original']
                resultado[agr]['valores'][row['mes_referencia']]['EUR'] = row['valor_eur']
                resultado[agr]['valores'][row['mes_referencia']]['BRL'] = row['valor_brl']
                resultado[agr]['moedas'].add(row['moeda_original'])

        elif tabela == 'lcto_impostos':
            c.execute('''
                SELECT tp_imposto, pagamento_mes_ano, SUM(valor_imposto) as valor_imposto,
                       SUM(valor_faturado) as valor_faturado, moeda_faturado, moeda_pagamento
                FROM lcto_impostos
                WHERE user_email=%s AND pagamento_mes_ano >= %s AND pagamento_mes_ano <= %s
                GROUP BY tp_imposto, pagamento_mes_ano, moeda_faturado, moeda_pagamento
            ''', (user_email, mes_inicio, mes_fim))
            for row in c.fetchall():
                agr = row['tp_imposto'] or 'Sem Tipo'
                agrupadores_encontrados.add(agr)
                if agr not in resultado:
                    resultado[agr] = {'valores': {}, 'moedas': set()}
                if row['pagamento_mes_ano'] not in resultado[agr]['valores']:
                    resultado[agr]['valores'][row['pagamento_mes_ano']] = {}
                resultado[agr]['valores'][row['pagamento_mes_ano']][row['moeda_faturado']] = row['valor_faturado']
                resultado[agr]['valores'][row['pagamento_mes_ano']][row['moeda_pagamento']] = row['valor_imposto']
                resultado[agr]['moedas'].add(row['moeda_faturado'])
                resultado[agr]['moedas'].add(row['moeda_pagamento'])

        elif tabela == 'lcto_emprestimos':
            c.execute('''
                SELECT beneficiario, data_operacao, valor_operacao, moeda_emp
                FROM lcto_emprestimos
                WHERE user_email=%s AND substr(data_operacao,1,7) >= %s AND substr(data_operacao,1,7) <= %s
            ''', (user_email, mes_inicio, mes_fim))
            for row in c.fetchall():
                agr = row['beneficiario'] or 'Sem Beneficiario'
                data_mes = row['data_operacao'][:7] if row['data_operacao'] else mes_inicio
                agrupadores_encontrados.add(agr)
                if agr not in resultado:
                    resultado[agr] = {'valores': {}, 'moedas': set()}
                if data_mes not in resultado[agr]['valores']:
                    resultado[agr]['valores'][data_mes] = {}
                resultado[agr]['valores'][data_mes][row['moeda_emp']] = row['valor_operacao']
                resultado[agr]['moedas'].add(row['moeda_emp'])

        elif tabela == 'lcto_investimentos':
            c.execute('''
                SELECT banco, tp_investimento, data_inv, valor_atual, valor_inv, moeda
                FROM lcto_investimentos
                WHERE user_email=%s AND substr(data_inv,1,7) >= %s AND substr(data_inv,1,7) <= %s
            ''', (user_email, mes_inicio, mes_fim))
            for row in c.fetchall():
                agr = f"{row['banco']} - {row['tp_investimento']}" if row['banco'] else 'Sem Banco'
                data_mes = row['data_inv'][:7] if row['data_inv'] else mes_inicio
                agrupadores_encontrados.add(agr)
                if agr not in resultado:
                    resultado[agr] = {'valores': {}, 'moedas': set()}
                if data_mes not in resultado[agr]['valores']:
                    resultado[agr]['valores'][data_mes] = {}
                resultado[agr]['valores'][data_mes][row['moeda']] = row['valor_atual'] or row['valor_inv']
                resultado[agr]['moedas'].add(row['moeda'])

        elif tabela == 'cad_despesas':
            c.execute('SELECT despesa, tipo_despesa, fator_divisao, prioridade FROM cad_despesas')
            for row in c.fetchall():
                agr = row['despesa'] or 'Sem Nome'
                agrupadores_encontrados.add(agr)
                if agr not in resultado:
                    resultado[agr] = {'valores': {}, 'moedas': set(), 'dados': {}}
                resultado[agr]['dados']['tipo_despesa'] = row['tipo_despesa']
                resultado[agr]['dados']['fator_divisao'] = row['fator_divisao']
                resultado[agr]['dados']['prioridade'] = row['prioridade']

        elif tabela == 'cad_contas':
            c.execute('SELECT descricao, agencia, conta, comentarios FROM cad_contas')
            for row in c.fetchall():
                agr = row['descricao'] or 'Sem Nome'
                agrupadores_encontrados.add(agr)
                if agr not in resultado:
                    resultado[agr] = {'valores': {}, 'moedas': set(), 'dados': {}}
                resultado[agr]['dados']['agencia'] = row['agencia']
                resultado[agr]['dados']['conta'] = row['conta']
                resultado[agr]['dados']['comentarios'] = row['comentarios']

        elif tabela == 'cad_receitas':
            c.execute('SELECT descricao FROM cad_receitas')
            for row in c.fetchall():
                agr = row['descricao'] or 'Sem Nome'
                agrupadores_encontrados.add(agr)
                if agr not in resultado:
                    resultado[agr] = {'valores': {}, 'moedas': set(), 'dados': {}}

        elif tabela == 'cad_investimentos':
            c.execute('SELECT descricao FROM cad_investimentos')
            for row in c.fetchall():
                agr = row['descricao'] or 'Sem Nome'
                agrupadores_encontrados.add(agr)
                if agr not in resultado:
                    resultado[agr] = {'valores': {}, 'moedas': set(), 'dados': {}}

        elif tabela == 'cad_usuarios':
            c.execute('SELECT nome, chave_usr1, chave_usr2, fator_pagamento FROM cad_usuarios')
            for row in c.fetchall():
                agr = row['nome'] or 'Sem Nome'
                agrupadores_encontrados.add(agr)
                if agr not in resultado:
                    resultado[agr] = {'valores': {}, 'moedas': set(), 'dados': {}}
                resultado[agr]['dados']['chave_usr1'] = row['chave_usr1']
                resultado[agr]['dados']['chave_usr2'] = row['chave_usr2']
                resultado[agr]['dados']['fator_pagamento'] = row['fator_pagamento']

        elif tabela == 'tb_tipo_imposto':
            c.execute('SELECT tp_imposto, alq_imposto, pagamento FROM tb_tipo_imposto')
            for row in c.fetchall():
                agr = row['tp_imposto'] or 'Sem Nome'
                agrupadores_encontrados.add(agr)
                if agr not in resultado:
                    resultado[agr] = {'valores': {}, 'moedas': set(), 'dados': {}}
                resultado[agr]['dados']['alq_imposto'] = row['alq_imposto']
                resultado[agr]['dados']['pagamento'] = row['pagamento']

    conn.close()

    total_por_agrupador = {}
    total_geral = {}
    for k, v in resultado.items():
        total_por_agrupador[k] = {}
        for mes, moedas_vals in v.get('valores', {}).items():
            for moeda, val in moedas_vals.items():
                total_por_agrupador[k][moeda] = total_por_agrupador[k].get(moeda, 0) + (val or 0)
                if mes not in total_geral:
                    total_geral[mes] = {}
                total_geral[mes][moeda] = total_geral[mes].get(moeda, 0) + (val or 0)

    return {
        'agrupadores': [
            {
                'nome': k,
                'valores': v.get('valores', {}),
                'moedas': list(v.get('moedas', set())),
                'dados': v.get('dados', {}),
            }
            for k, v in resultado.items()
        ],
        'meses': meses_periodo,
        'total_por_agrupador': total_por_agrupador,
        'total_geral': total_geral,
    }
