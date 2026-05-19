import os
import io
import traceback
import datetime
import pandas as pd
from flask import request, jsonify, send_file, session, current_app
from werkzeug.utils import secure_filename

from . import bp
from .db import (
    get_despesas_mensais, save_despesas_mensais_batch, add_despesa_mensal,
    update_despesa_mensal, delete_despesa_mensal, delete_despesas_mensais_batch,
    clear_despesas_mensais, consolidar_despesas_anuais, get_consolidacao_tipo_despesa,
    get_meses_disponiveis, check_duplicates_with_data, get_relatorio_mensal_v2,
)


@bp.route('/api/despesas_mensais/check_duplicates', methods=['POST'])
def api_check_duplicates_despesas_mensais():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    payload = request.json or {}
    candidates = payload.get('candidates', [])
    if not candidates:
        return jsonify({'matches': {}})
    matches = check_duplicates_with_data(session['user_email'], candidates)
    return jsonify({'matches': matches})


@bp.route('/api/despesas_mensais', methods=['GET'])
def api_get_despesas_mensais():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    mes = request.args.get('mes')
    return jsonify(get_despesas_mensais(session['user_email'], mes))


@bp.route('/api/despesas_mensais/batch', methods=['POST'])
def api_save_batch_despesas_mensais():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    rows = request.json or []
    result = save_despesas_mensais_batch(session['user_email'], rows)
    return jsonify({'status': 'ok', **result})


@bp.route('/api/despesas_mensais', methods=['POST'])
def api_post_despesa_mensal():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    add_despesa_mensal(session['user_email'], request.json or {})
    return jsonify({'status': 'ok'})


@bp.route('/api/despesas_mensais/<int:d_id>', methods=['PUT'])
def api_put_despesa_mensal(d_id):
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    update_despesa_mensal(session['user_email'], d_id, request.json or {})
    return jsonify({'status': 'ok'})


@bp.route('/api/despesas_mensais/<int:d_id>', methods=['DELETE'])
def api_delete_despesa_mensal(d_id):
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    delete_despesa_mensal(session['user_email'], d_id)
    return jsonify({'status': 'ok'})


@bp.route('/api/despesas_mensais/batch_delete', methods=['POST'])
def api_batch_delete_despesas_mensais():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    data = request.json or {}
    ids = data.get('ids', [])
    if ids:
        delete_despesas_mensais_batch(session['user_email'], ids)
    return jsonify({'status': 'ok'})


@bp.route('/api/despesas_mensais/clear', methods=['POST'])
def api_clear_despesas_mensais():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    mes = (request.json or {}).get('mes')
    clear_despesas_mensais(session['user_email'], mes)
    return jsonify({'status': 'ok', 'message': f'Registros {"do mês " + mes if mes else ""} removidos com sucesso!'})


@bp.route('/api/despesas_mensais/meses', methods=['GET'])
def api_meses_disponiveis():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    return jsonify(get_meses_disponiveis(session['user_email']))


@bp.route('/api/despesas_mensais/upload', methods=['POST'])
def api_upload_despesas_mensais():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    if 'file' not in request.files:
        return jsonify({'error': 'Nenhum arquivo'}), 400
    file = request.files['file']
    if not file.filename.endswith(('.csv', '.xls', '.xlsx')):
        return jsonify({'error': 'Arquivo inválido'}), 400

    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
    file.save(filepath)
    preview_data = []
    try:
        filename = file.filename.lower()
        df = pd.read_excel(filepath) if filename.endswith(('.xls', '.xlsx')) else pd.read_csv(filepath)
        df.columns = df.columns.str.strip().str.lower()

        mes_ref = (request.form or {}).get('mes') or (request.json or {}).get('mes') if request.form or request.json else None
        if not mes_ref:
            return jsonify({'error': 'Mês de referência não informado'}), 400

        force_moeda = (request.form or {}).get('moeda') or (request.json or {}).get('moeda') if request.form or request.json else None

        is_revolut = any(c in df.columns for c in ['descrição', 'descricao', 'description']) or any(c in df.columns for c in ['tipo', 'type'])
        has_moeda_col = 'moeda' in df.columns

        if not has_moeda_col and not force_moeda:
            if is_revolut:
                force_moeda = 'EUR'
            else:
                return jsonify({'needs_moeda': True, 'message': 'Moeda não identificada no arquivo. Selecione a moeda manualmente.', 'filename': file.filename}), 200

        idx = 0
        for _, row in df.iterrows():
            try:
                if is_revolut:
                    data_raw = str(row.get('data de início', '') or row.get('data de conclusão', '') or row.get('data de conclusao', '') or row.get('started date', '') or row.get('completed date', ''))
                    data = data_raw[:10] if data_raw and data_raw.lower() not in ['nan', 'none', 'nat'] else ''
                    desc = str(row.get('descrição') or row.get('descricao') or row.get('description') or row.get('tipo') or row.get('type') or '').strip()
                    val_orig = abs(float(row.get('montante') or row.get('amount') or 0))
                    moeda = 'EUR'
                    cambio = 1
                    val_eur = val_orig
                else:
                    data = row.get('data') or row.get('Data') or ''
                    desc = row.get('descricao') or row.get('descrição') or row.get('descricao') or ''
                    val_orig = float(row.get('valor_original') or row.get('valor original') or row.get('valor') or 0) or 0

                    if force_moeda:
                        moeda = force_moeda.upper()
                    else:
                        moeda_raw = row.get('moeda') or row.get('Moeda')
                        if moeda_raw and str(moeda_raw).strip():
                            moeda = 'EUR' if str(moeda_raw).upper().strip() == 'EUR' else 'BRL'
                    cambio = float(row.get('cambio_eur') or row.get('cambio eur') or row.get('câmbio') or 1) or 1
                    val_eur = float(row.get('valor_eur') or row.get('valor eur') or val_orig * cambio) or (val_orig * cambio)

                if desc.lower() in ['nan', 'none', ''] or not desc:
                    continue
                if val_orig == 0:
                    continue

                if is_revolut:
                    if val_orig > 0 and ('carregamento' in desc.lower() or 'top-up' in desc.lower() or 'top up' in desc.lower()):
                        continue

                desc = desc[:200]
                usr1 = str(row.get('usr1') or row.get('Usr1') or '') or ''
                usr2 = str(row.get('usr2') or row.get('Usr2') or '') or ''
                status = str(row.get('status_pago') or row.get('status') or 'Pendente')
                cat = str(row.get('categoria_final') or row.get('categoria') or '') or 'Não Categorizado'
                receita = 1 if str(row.get('receita') or '').lower() in ['sim', 'yes', '1', 'true'] else 0
                comentario = str(row.get('comentarios') or '') or ''
                conta = str(row.get('conta_bancaria') or row.get('conta') or '') or ''
                if is_revolut:
                    conta = 'Revolut'

                if desc:
                    preview_data.append({
                        'idx': idx,
                        'data': data,
                        'descricao': desc,
                        'valor_original': val_orig,
                        'moeda': moeda,
                        'cambio_eur': cambio,
                        'valor_eur': val_eur,
                        'usr1': usr1,
                        'usr2': usr2,
                        'status_pago': status,
                        'categoria_final': cat,
                        'receita': receita,
                        'comentarios': comentario,
                        'conta_bancaria': conta,
                        'mes_referencia': mes_ref,
                    })
                    idx += 1
            except Exception:
                continue
        os.remove(filepath)
        return jsonify({'preview': True, 'data': preview_data, 'mes': mes_ref})
    except Exception as e:
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({'error': str(e)}), 400


@bp.route('/api/despesas_mensais/upload_confirm', methods=['POST'])
def api_upload_despesas_mensais_confirm():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    rows = request.json.get('rows', [])
    if not rows:
        return jsonify({'error': 'Nenhuma linha selecionada'}), 400

    count = 0
    for row in rows:
        if row.get('selected', True):
            try:
                add_despesa_mensal(session['user_email'], {
                    'data': row.get('data', ''),
                    'descricao': row.get('descricao', ''),
                    'valor_original': row.get('valor_original', 0),
                    'moeda': row.get('moeda', 'BRL'),
                    'cambio_eur': row.get('cambio_eur', 1),
                    'valor_eur': row.get('valor_eur', 0),
                    'usr1': row.get('usr1', ''),
                    'usr2': row.get('usr2', ''),
                    'diferenca_original': abs(row.get('valor_original', 0) - (float(row.get('usr1') or 0) + float(row.get('usr2') or 0))),
                    'status_pago': row.get('status_pago', 'Pendente'),
                    'categoria_final': row.get('categoria_final') or 'Não Categorizado',
                    'receita': row.get('receita', 0),
                    'comentarios': row.get('comentarios', ''),
                    'conta_bancaria': row.get('conta_bancaria', ''),
                    'mes_referencia': row.get('mes_referencia', ''),
                })
                count += 1
            except Exception as e:
                print(f'Erro ao salvar linha: {e}')
                continue
    return jsonify({'status': 'ok', 'count': count, 'message': f'{count} despesas importadas!'})


@bp.route('/api/despesas_mensais/consolidacao', methods=['GET'])
def api_consolidacao_tipo_despesa():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    mes = request.args.get('mes')
    if not mes:
        return jsonify({'error': 'Mês não informado'}), 400
    data = get_consolidacao_tipo_despesa(session['user_email'], mes)
    return jsonify(data)


@bp.route('/api/despesas_anuais/consolidar', methods=['POST'])
def api_consolidar_anuais():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    ano = (request.json or {}).get('ano', datetime.date.today().year)
    count = consolidar_despesas_anuais(session['user_email'], ano)
    return jsonify({'status': 'ok', 'categorias': count})


@bp.route('/export/despesas_mensais', methods=['POST'])
def export_despesas_mensais():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    data = request.json or {}
    mes = data.get('mes')
    if not mes:
        return jsonify({'error': 'Mês não informado'}), 400

    despesas = get_despesas_mensais(session['user_email'], mes)
    df = pd.DataFrame(despesas)
    if not df.empty:
        df.drop(columns=['id', 'mes_referencia', 'user_email', 'criado_em'], errors='ignore', inplace=True)
        df.rename(columns={
            'data': 'Data', 'descricao': 'Descrição', 'valor_original': 'Valor Original',
            'moeda': 'Moeda Original', 'cambio_eur': 'Câmbio EUR', 'valor_eur': 'Valor Final (EUR)',
            'usr1': 'USR1', 'usr2': 'USR2', 'diferenca_original': 'Diferença Original',
            'status_pago': 'Status Pago', 'categoria_final': 'Categoria Final',
            'receita': 'Receita', 'comentarios': 'Comentários', 'conta_bancaria': 'Conta Bancária',
        }, inplace=True)
        df['Receita'] = df['Receita'].map({1: 'Sim', 0: 'Não'})

        num_cols = ['Valor Original', 'Câmbio EUR', 'Valor Final (EUR)', 'USR1', 'USR2', 'Diferença Original']
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '.'), errors='coerce')

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Detalhes Lancamentos')
        worksheet = writer.sheets['Detalhes Lancamentos']
        num_cols = ['Valor Original', 'Câmbio EUR', 'Valor Final (EUR)', 'USR1', 'USR2', 'Diferença Original']
        for col in num_cols:
            if col in df.columns:
                col_idx = df.columns.get_loc(col) + 1
                for row in range(2, len(df) + 2):
                    worksheet.cell(row=row, column=col_idx).number_format = '#,##0.00'
    output.seek(0)

    ano, mes_num = mes.split('-')
    mes_extenso = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'][int(mes_num) - 1]
    filename = f'Detalhes_Lancamentos_{mes_extenso}_{ano}.xlsx'

    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name=filename)


@bp.route('/export/consolidacao', methods=['POST'])
def export_consolidacao():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    data = request.json or {}
    mes = data.get('mes')
    if not mes:
        return jsonify({'error': 'Mês não informado'}), 400

    despesas = get_despesas_mensais(session['user_email'], mes)

    sumMap = {}
    for d in despesas:
        cat = d.get('categoria_final') or 'Sem Categoria'
        if cat not in sumMap:
            sumMap[cat] = {'usr1': 0, 'usr2': 0, 'total': 0}
        sumMap[cat]['usr1'] += d.get('usr1') or 0
        sumMap[cat]['usr2'] += d.get('usr2') or 0
        sumMap[cat]['total'] += (d.get('usr1') or 0) + (d.get('usr2') or 0)

    rows = [{'Categoria': cat, 'Total Usr1': sumMap[cat]['usr1'],
             'Total Usr2': sumMap[cat]['usr2'], 'Total Geral': sumMap[cat]['total']}
            for cat in sorted(sumMap.keys())]

    df = pd.DataFrame(rows)
    num_cols = ['Total Usr1', 'Total Usr2', 'Total Geral']
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Consolidacao')
        worksheet = writer.sheets['Consolidacao']
        for col in num_cols:
            if col in df.columns:
                col_idx = df.columns.get_loc(col) + 1
                for row in range(2, len(df) + 2):
                    worksheet.cell(row=row, column=col_idx).number_format = '#,##0.00'
    output.seek(0)

    ano, mes_num = mes.split('-')
    mes_extenso = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'][int(mes_num) - 1]
    filename = f'Consolidacao_{mes_extenso}_{ano}.xlsx'

    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name=filename)


@bp.route('/api/relatorio_mensal', methods=['GET'])
def api_relatorio_mensal():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    mes = request.args.get('mes', '')
    if not mes:
        return jsonify({'rows': [], 'currencies': [], 'cards': {}, 'usr1_nome': 'USR1', 'usr2_nome': 'USR2'})
    try:
        return jsonify(get_relatorio_mensal_v2(session['user_email'], mes))
    except Exception:
        traceback.print_exc()
        return jsonify({'error': 'Erro interno'}), 500
