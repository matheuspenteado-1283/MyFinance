import io
import math
import traceback

import pandas as pd
from flask import request, jsonify, send_file, session

from . import bp


def _sanitize(obj):
    """Recursively replace non-finite floats (NaN, Inf) with 0 before JSON serialization."""
    if isinstance(obj, float):
        return 0.0 if not math.isfinite(obj) else obj
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    return obj
from .db import (
    get_dashboard_data, get_annual_report,
    get_dashboard_overview, get_dashboard_expenses, get_dashboard_revenues,
    get_dashboard_budget, get_dashboard_investments, get_dashboard_pnl,
    get_dashboard_cashflow, get_dashboard_net_worth,
    get_relatorio_anual_despesas, get_relatorio_anual_receitas,
    MONTH_LABELS,
)


@bp.route('/api/dashboard_data', methods=['GET'])
def api_get_dashboard_data():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    mes = request.args.get('mes')
    if not mes:
        return jsonify({'error': 'Mês não informado'}), 400
    data = get_dashboard_data(session['user_email'], mes)
    return jsonify(data)


def _dashboard_params():
    from datetime import datetime
    today = datetime.now()
    mes = request.args.get('mes') or today.strftime('%Y-%m')
    ano = request.args.get('ano', type=int) or int(mes[:4])
    usr = (request.args.get('usr') or 'all').lower()
    if usr not in ('all', 'usr1', 'usr2'):
        usr = 'all'
    return mes, ano, usr


def _json_dashboard(loader, pass_usr=True):
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    mes, ano, usr = _dashboard_params()
    try:
        if pass_usr:
            result = loader(session['user_email'], mes, ano, usr)
        else:
            result = loader(session['user_email'], mes, ano)
        return jsonify(_sanitize(result))
    except Exception:
        traceback.print_exc()
        return jsonify({'error': 'Erro interno'}), 500


@bp.route('/api/dashboard/overview', methods=['GET'])
def api_dashboard_overview():
    return _json_dashboard(get_dashboard_overview)


@bp.route('/api/dashboard/despesas', methods=['GET'])
def api_dashboard_despesas():
    return _json_dashboard(get_dashboard_expenses)


@bp.route('/api/dashboard/receitas', methods=['GET'])
def api_dashboard_receitas():
    return _json_dashboard(get_dashboard_revenues)


@bp.route('/api/dashboard/budget', methods=['GET'])
def api_dashboard_budget():
    return _json_dashboard(get_dashboard_budget)


@bp.route('/api/dashboard/investimentos', methods=['GET'])
def api_dashboard_investimentos():
    return _json_dashboard(get_dashboard_investments, pass_usr=False)


@bp.route('/api/dashboard/pnl', methods=['GET'])
def api_dashboard_pnl():
    return _json_dashboard(get_dashboard_pnl, pass_usr=False)


@bp.route('/api/dashboard/fluxo-caixa', methods=['GET'])
def api_dashboard_fluxo_caixa():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    _, ano, usr = _dashboard_params()
    try:
        return jsonify(_sanitize(get_dashboard_cashflow(session['user_email'], ano, usr)))
    except Exception:
        traceback.print_exc()
        return jsonify({'error': 'Erro interno'}), 500


@bp.route('/api/dashboard/patrimonio', methods=['GET'])
def api_dashboard_patrimonio():
    return _json_dashboard(get_dashboard_net_worth)


@bp.route('/api/relatorio_anual', methods=['GET'])
def api_get_relatorio_anual():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    ano = request.args.get('ano')
    if not ano:
        return jsonify({'error': 'Ano não informado'}), 400
    data = get_annual_report(session['user_email'], int(ano))
    return jsonify(data)


@bp.route('/api/relatorio_anual_despesas', methods=['GET'])
def api_relatorio_anual_despesas():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    from datetime import datetime
    ano = int(request.args.get('ano', datetime.now().year))
    try:
        return jsonify(get_relatorio_anual_despesas(session['user_email'], ano))
    except Exception:
        traceback.print_exc()
        return jsonify({'error': 'Erro interno'}), 500


@bp.route('/api/relatorio_anual_receitas', methods=['GET'])
def api_relatorio_anual_receitas():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    from datetime import datetime
    ano = int(request.args.get('ano', datetime.now().year))
    try:
        return jsonify(get_relatorio_anual_receitas(session['user_email'], ano))
    except Exception:
        traceback.print_exc()
        return jsonify({'error': 'Erro interno'}), 500


@bp.route('/api/relatorio_anual_despesas/exportar', methods=['GET'])
def api_relatorio_anual_despesas_exportar():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    from datetime import datetime
    ano = int(request.args.get('ano', datetime.now().year))
    try:
        data = get_relatorio_anual_despesas(session['user_email'], ano)
        months = data['months']
        currencies = data['currencies']
        rows = data['rows']
        usr1_nome = data['usr1_nome']
        usr2_nome = data['usr2_nome']

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            for moeda in currencies:
                cols = ['Categoria', 'Tipo'] + MONTH_LABELS + ['Total', 'Média Mensal']
                excel_rows = []
                for row in rows:
                    v = row['valores'].get(moeda, {})
                    mes_vals = [v.get('meses', {}).get(m, {}).get('total', 0) for m in months]
                    excel_rows.append([row['categoria'], row['tipo_despesa']] + mes_vals + [v.get('total', 0), v.get('media', 0)])
                df = pd.DataFrame(excel_rows, columns=cols)
                sheet = f'Despesas {moeda}'[:31]
                df.to_excel(writer, index=False, sheet_name=sheet)
                ws = writer.sheets[sheet]
                for ci in range(3, len(cols) + 1):
                    for ri in range(2, len(excel_rows) + 2):
                        ws.cell(row=ri, column=ci).number_format = '#,##0.00'

        output.seek(0)
        return send_file(output,
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                         as_attachment=True,
                         download_name=f'Relatorio_Anual_Despesas_{ano}.xlsx')
    except Exception:
        traceback.print_exc()
        return jsonify({'error': 'Erro ao gerar Excel'}), 500


@bp.route('/api/relatorio_anual_receitas/exportar', methods=['GET'])
def api_relatorio_anual_receitas_exportar():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    from datetime import datetime
    ano = int(request.args.get('ano', datetime.now().year))
    try:
        data = get_relatorio_anual_receitas(session['user_email'], ano)
        months = data['months']
        currencies = data['currencies']
        rows = data['rows']

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            for moeda in currencies:
                cols = ['Tipo de Receita'] + MONTH_LABELS + ['Total', 'Média Mensal']
                excel_rows = []
                for row in rows:
                    v = row['valores'].get(moeda, {})
                    mes_vals = [v.get('meses', {}).get(m, 0) for m in months]
                    excel_rows.append([row['tipo']] + mes_vals + [v.get('total', 0), v.get('media', 0)])
                df = pd.DataFrame(excel_rows, columns=cols)
                sheet = f'Receitas {moeda}'[:31]
                df.to_excel(writer, index=False, sheet_name=sheet)
                ws = writer.sheets[sheet]
                for ci in range(2, len(cols) + 1):
                    for ri in range(2, len(excel_rows) + 2):
                        ws.cell(row=ri, column=ci).number_format = '#,##0.00'

        output.seek(0)
        return send_file(output,
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                         as_attachment=True,
                         download_name=f'Relatorio_Anual_Receitas_{ano}.xlsx')
    except Exception:
        traceback.print_exc()
        return jsonify({'error': 'Erro ao gerar Excel'}), 500
