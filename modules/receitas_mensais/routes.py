import io
import pandas as pd
from flask import request, jsonify, send_file, session

from . import bp
from .db import (
    get_receitas_mensais, add_receita_mensal, update_receita_mensal,
    delete_receita_mensal, sync_receitas_from_despesas_mensais, get_totais_receitas,
)
from exchange_api import get_exchange_rate


@bp.route('/api/receitas_mensais', methods=['GET'])
def api_get_receitas_mensais():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    mes = request.args.get('mes')
    return jsonify(get_receitas_mensais(session['user_email'], mes))


@bp.route('/api/receitas_mensais/sync', methods=['POST'])
def api_sync_receitas():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    mes = request.json.get('mes') if request.json else None
    if not mes:
        return jsonify({'error': 'Mês não informado'}), 400
    count = sync_receitas_from_despesas_mensais(session['user_email'], mes)
    return jsonify({'status': 'ok', 'synced': count})


@bp.route('/api/receitas_mensais/totais', methods=['GET'])
def api_totais_receitas():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    mes = request.args.get('mes')
    if not mes:
        return jsonify({'error': 'Mês não informado'}), 400
    return jsonify(get_totais_receitas(session['user_email'], mes))


@bp.route('/api/cotacao', methods=['GET'])
def api_get_cotacao():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    date = request.args.get('date') or 'latest'
    from_cur = request.args.get('from', 'BRL')
    to = request.args.get('to', 'EUR')
    try:
        rate = get_exchange_rate(date, from_cur, to)
        return jsonify({'cotacao': rate})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@bp.route('/api/receitas_mensais', methods=['POST'])
def api_post_receita_mensal():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    add_receita_mensal(session['user_email'], request.json or {})
    return jsonify({'status': 'ok'})


@bp.route('/api/receitas_mensais/<int:r_id>', methods=['PUT'])
def api_put_receita_mensal(r_id):
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    update_receita_mensal(session['user_email'], r_id, request.json or {})
    return jsonify({'status': 'ok'})


@bp.route('/api/receitas_mensais/<int:r_id>', methods=['DELETE'])
def api_delete_receita_mensal(r_id):
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    delete_receita_mensal(session['user_email'], r_id)
    return jsonify({'status': 'ok'})


@bp.route('/export/receitas_mensais', methods=['POST'])
def export_receitas_mensais():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    data = request.json or {}
    mes = data.get('mes')
    if not mes:
        return jsonify({'error': 'Mês não informado'}), 400

    receitas = get_receitas_mensais(session['user_email'], mes)
    df = pd.DataFrame(receitas)
    if not df.empty:
        df.drop(columns=['id', 'mes_referencia', 'user_email', 'despesa_mensal_id', 'criado_em'], errors='ignore', inplace=True)
        df.rename(columns={
            'data': 'Data', 'tipo_receita': 'Tipo de Receita', 'valor_original': 'Valor Original',
            'moeda_original': 'Moeda Original', 'cotacao': 'Cotação', 'valor_eur': 'Valor EUR',
            'valor_brl': 'Valor BRL', 'conta_bancaria': 'Conta Bancária', 'comentarios': 'Comentários',
        }, inplace=True)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Receitas')
    output.seek(0)

    ano, mes_num = mes.split('-')
    mes_extenso = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'][int(mes_num) - 1]
    filename = f'Receitas_{mes_extenso}_{ano}.xlsx'

    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name=filename)
