import os
import io
import pandas as pd
from flask import request, jsonify, send_file, session, current_app
from werkzeug.utils import secure_filename

from . import bp
from .db import (
    get_all_posicoes, add_posicao, update_posicao, delete_posicao, clear_posicoes,
    get_mensal, upsert_mensal, delete_mensal, get_resumo, _mes_atual,
)


@bp.route('/api/investimentos/posicoes', methods=['GET'])
def api_get_posicoes():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    return jsonify(get_all_posicoes(session['user_email']))


@bp.route('/api/investimentos/posicoes', methods=['POST'])
def api_post_posicao():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    d = request.json or {}
    add_posicao(
        session['user_email'], d.get('banco'), d.get('tp_investimento'),
        d.get('moeda', 'BRL'), d.get('data_inicio'), d.get('valor_investido_inicial'),
    )
    return jsonify({'status': 'ok'})


@bp.route('/api/investimentos/posicoes/<int:pos_id>', methods=['PUT'])
def api_put_posicao(pos_id):
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    d = request.json or {}
    update_posicao(
        pos_id, session['user_email'], d.get('banco'), d.get('tp_investimento'),
        d.get('moeda', 'BRL'), d.get('data_inicio'), d.get('valor_investido_inicial'),
    )
    return jsonify({'status': 'ok'})


@bp.route('/api/investimentos/posicoes/<int:pos_id>', methods=['DELETE'])
def api_delete_posicao(pos_id):
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    delete_posicao(pos_id, session['user_email'])
    return jsonify({'status': 'ok'})


@bp.route('/api/investimentos/posicoes/<int:pos_id>/mensal', methods=['GET'])
def api_get_mensal(pos_id):
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    return jsonify(get_mensal(pos_id))


@bp.route('/api/investimentos/posicoes/<int:pos_id>/mensal', methods=['POST'])
def api_post_mensal(pos_id):
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    d = request.json or {}
    upsert_mensal(
        pos_id, session['user_email'], d.get('mes_referencia') or _mes_atual(),
        d.get('valor_mercado'), d.get('aporte_mes'), d.get('resgate_mes'), d.get('taxa_mes'),
    )
    return jsonify({'status': 'ok'})


@bp.route('/api/investimentos/mensal/<int:snapshot_id>', methods=['DELETE'])
def api_delete_mensal(snapshot_id):
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    delete_mensal(snapshot_id, session['user_email'])
    return jsonify({'status': 'ok'})


@bp.route('/api/investimentos/resumo', methods=['GET'])
def api_get_resumo():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    return jsonify(get_resumo(session['user_email']))


@bp.route('/api/upload_lcto_investimentos', methods=['POST'])
def api_upload_lcto_investimentos():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    if 'file' not in request.files:
        return jsonify({'error': 'Nenhum arquivo'}), 400
    file = request.files['file']
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
    file.save(filepath)
    try:
        filename = file.filename.lower()
        df = pd.read_excel(filepath) if filename.endswith(('.xls', '.xlsx')) else pd.read_csv(filepath)
        clear_posicoes(session['user_email'])
        for _, row in df.iterrows():
            valor_inv = float(row.get('valor_inv', row.get('Valor Investimento', 0)) or 0)
            qtd = float(row.get('qtd', row.get('Quantidade', 1)) or 1)
            data_inicio = str(row.get('data_inv', row.get('Data Investimento', '')) or '')
            pos_id = add_posicao(
                session['user_email'],
                str(row.get('banco', row.get('Banco', ''))),
                str(row.get('tp_investimento', row.get('Tipo Investimento', ''))),
                str(row.get('moeda', row.get('Moeda', 'BRL'))),
                data_inicio,
                valor_inv * qtd,
            )
            valor_atual = float(row.get('valor_atual', row.get('Valor Atual', 0)) or 0)
            aporte = float(row.get('aporte', row.get('Aporte', 0)) or 0)
            taxa = float(row.get('taxa', row.get('Taxa', 0)) or 0)
            mes_referencia = data_inicio[:7] if len(data_inicio) >= 7 else _mes_atual()
            upsert_mensal(pos_id, session['user_email'], mes_referencia, valor_atual, aporte, 0, taxa)
        os.remove(filepath)
        return jsonify({'status': 'ok'})
    except Exception as e:
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({'error': str(e)}), 400


@bp.route('/api/export_lcto_investimentos', methods=['GET'])
def api_export_lcto_investimentos():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    posicoes = get_all_posicoes(session['user_email'])

    df_posicoes = pd.DataFrame(posicoes)
    if not df_posicoes.empty:
        df_posicoes = df_posicoes.drop(columns=['user_email', 'ativo'], errors='ignore')
        df_posicoes.rename(columns={
            'id': 'ID', 'banco': 'Banco', 'tp_investimento': 'Tipo Investimento', 'moeda': 'Moeda',
            'data_inicio': 'Data Início', 'valor_investido_inicial': 'Valor Investido Inicial',
            'criado_em': 'Criado Em', 'valor_atual': 'Valor Atual', 'custo_acumulado': 'Custo Acumulado',
            'pnl_total': 'P&L Total', 'pnl_mensal': 'P&L Mês', 'pct_rentabilidade': '% Rentabilidade',
            'qtd_meses': 'Meses Registrados',
        }, inplace=True)

    historico_rows = []
    for pos in posicoes:
        for snap in get_mensal(pos['id']):
            historico_rows.append({
                'Posição ID': pos['id'], 'Banco': pos.get('banco'), 'Tipo': pos.get('tp_investimento'),
                'Mês': snap.get('mes_referencia'), 'Valor de Mercado': snap.get('valor_mercado'),
                'Aporte': snap.get('aporte_mes'), 'Resgate': snap.get('resgate_mes'),
                'Taxa': snap.get('taxa_mes'), 'Custo Acumulado': snap.get('custo_acumulado'),
                'P&L Mês': snap.get('pnl_mensal'),
            })
    df_historico = pd.DataFrame(historico_rows)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_posicoes.to_excel(writer, index=False, sheet_name='Posições')
        df_historico.to_excel(writer, index=False, sheet_name='Histórico Mensal')
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name='Investimentos.xlsx')
