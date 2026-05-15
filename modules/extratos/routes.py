import os
import io
import traceback
import pandas as pd
from flask import request, jsonify, send_file, current_app
from werkzeug.utils import secure_filename

from . import bp
from .parser import process_file, process_despesas_file, _debug_file
from .db import save_category_rule
from config import allowed_file


@bp.route('/upload', methods=['POST'])
def upload_file():
    if 'files[]' not in request.files:
        return jsonify({'error': 'Nenhum arquivo enviado'}), 400

    files = request.files.getlist('files[]')

    if not files or all(file.filename == '' for file in files):
        return jsonify({'error': 'Nenhum arquivo selecionado'}), 400

    all_transactions = []
    debug_info = []

    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            try:
                file_transactions = process_file(filepath)
                debug_info.append(_debug_file(filepath))
                all_transactions.extend(file_transactions)
            except Exception as e:
                debug_info.append({'file': filename, 'error': str(e), 'trace': traceback.format_exc()})

    if len(all_transactions) == 0:
        return jsonify({
            'error': 'Nenhuma transação foi extraída dos arquivos. Verifique os formatos ou as colunas.',
            'transactions': [],
            'debug': debug_info,
        }), 400

    return jsonify({
        'message': f'Extração concluída: {len(all_transactions)} transações processadas.',
        'transactions': all_transactions,
    }), 200


@bp.route('/save_category', methods=['POST'])
def save_category():
    data = request.json
    description = data.get('description')
    category = data.get('category')
    if description and category:
        save_category_rule(description, category)
        return jsonify({'status': 'ok'})
    return jsonify({'error': 'Dados inválidos'}), 400


@bp.route('/export', methods=['POST'])
def export_data():
    data = request.json
    transactions = data.get('transactions', [])

    if not transactions:
        return jsonify({'error': 'Nenhuma transação enviada'}), 400

    for t in transactions:
        p1 = float(t.get('pag1', 0))
        p2 = float(t.get('pag2', 0))
        orig = float(t.get('valor_original', 0))
        diff = abs((p1 + p2) - orig)
        t['diferenca'] = round(diff, 2)
        t['status'] = 'OK' if diff < 0.01 else 'NOK'

    df = pd.DataFrame(transactions)
    cols = ['data', 'descricao', 'valor_original', 'moeda', 'cambio', 'valor_eur', 'pag1', 'pag2', 'diferenca', 'status', 'categoria']
    cols = [c for c in cols if c in df.columns]
    df = df[cols]

    df.rename(columns={
        'data': 'Data',
        'descricao': 'Descrição',
        'valor_original': 'Valor Original',
        'moeda': 'Moeda Original',
        'cambio': 'Câmbio EUR',
        'valor_eur': 'Valor Final (EUR)',
        'pag1': 'Pag1',
        'pag2': 'Pag2',
        'diferenca': 'Diferença Original',
        'status': 'Status Pago',
        'categoria': 'Categoria Final',
    }, inplace=True)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Extratos')
    output.seek(0)

    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='Extratos_Processados.xlsx',
    )
