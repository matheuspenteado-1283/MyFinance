import io
import os
import pandas as pd
from flask import request, jsonify, send_file, session
from werkzeug.utils import secure_filename

from . import bp
from .db import (
    get_budget_items, get_budget_summary, upsert_budget_item,
    update_budget_item, delete_budget_item, delete_budget_year, bulk_upsert_budget,
    get_comparativo, MONTHS
)
from config import allowed_file

UPLOAD_FOLDER = '/tmp/budget_uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def _auth():
    if 'user_email' not in session:
        return None
    return session['user_email']


@bp.route('/api/budget', methods=['GET'])
def api_get_budget():
    user = _auth()
    if not user:
        return jsonify({'error': 'Não logado'}), 401
    ano = request.args.get('ano', type=int)
    tipo = request.args.get('tipo', 'despesa')
    if not ano:
        return jsonify([])
    return jsonify(get_budget_items(user, ano, tipo))


@bp.route('/api/budget/summary', methods=['GET'])
def api_get_budget_summary():
    user = _auth()
    if not user:
        return jsonify({'error': 'Não logado'}), 401
    ano = request.args.get('ano', type=int)
    if not ano:
        return jsonify([])
    return jsonify(get_budget_summary(user, ano))


@bp.route('/api/budget', methods=['POST'])
def api_post_budget():
    user = _auth()
    if not user:
        return jsonify({'error': 'Não logado'}), 401
    d = request.json
    item_id = upsert_budget_item(
        user_email=user,
        ano=d.get('ano'),
        tipo=d.get('tipo', 'despesa'),
        categoria_id=d.get('categoria_id'),
        categoria_nome=d.get('categoria_nome', ''),
        tipo_categoria=d.get('tipo_categoria', ''),
        moeda=d.get('moeda', 'EUR'),
        valores_meses={m: d.get(f'valor_{m}', 0) for m in MONTHS},
        variacao_mensal_pct=d.get('variacao_mensal_pct', 0),
        variacao_anual_pct=d.get('variacao_anual_pct', 0),
    )
    return jsonify({'status': 'ok', 'id': item_id})


@bp.route('/api/budget/<int:item_id>', methods=['PUT'])
def api_put_budget(item_id):
    user = _auth()
    if not user:
        return jsonify({'error': 'Não logado'}), 401
    d = request.json
    update_budget_item(
        user_email=user,
        item_id=item_id,
        valores_meses={m: d.get(f'valor_{m}', 0) for m in MONTHS},
        variacao_mensal_pct=d.get('variacao_mensal_pct', 0),
        variacao_anual_pct=d.get('variacao_anual_pct', 0),
        moeda=d.get('moeda', 'EUR'),
    )
    return jsonify({'status': 'ok'})


@bp.route('/api/budget/<int:item_id>', methods=['DELETE'])
def api_delete_budget(item_id):
    user = _auth()
    if not user:
        return jsonify({'error': 'Não logado'}), 401
    delete_budget_item(user, item_id)
    return jsonify({'status': 'ok'})


@bp.route('/api/budget/comparativo', methods=['GET'])
def api_get_comparativo():
    user = _auth()
    if not user:
        return jsonify({'error': 'Não logado'}), 401
    mes_ano = request.args.get('mes_ano', '')
    if not mes_ano:
        return jsonify({'error': 'mes_ano obrigatório (YYYY-MM)'}), 400
    return jsonify(get_comparativo(user, mes_ano))


@bp.route('/api/budget/clear', methods=['DELETE'])
def api_clear_budget():
    user = _auth()
    if not user:
        return jsonify({'error': 'Não logado'}), 401
    ano = request.args.get('ano', type=int)
    tipo = request.args.get('tipo')
    if not ano:
        return jsonify({'error': 'Ano obrigatório'}), 400
    delete_budget_year(user, ano, tipo)
    return jsonify({'status': 'ok'})


@bp.route('/api/budget/upload', methods=['POST'])
def api_upload_budget():
    user = _auth()
    if not user:
        return jsonify({'error': 'Não logado'}), 401

    file = request.files.get('file')
    ano = request.form.get('ano', type=int)
    tipo = request.form.get('tipo', 'despesa')

    if not file or not ano:
        return jsonify({'error': 'Arquivo e ano são obrigatórios'}), 400

    filename = secure_filename(file.filename)
    if not allowed_file(filename):
        return jsonify({'error': 'Formato inválido. Use .xlsx ou .csv'}), 400

    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    try:
        if filename.endswith('.csv'):
            df = pd.read_csv(filepath)
        else:
            df = pd.read_excel(filepath)

        df.columns = [str(c).strip().lower() for c in df.columns]

        col_map = {
            'categoria': 'categoria_nome', 'category': 'categoria_nome',
            'despesa': 'categoria_nome', 'receita': 'categoria_nome',
            'janeiro': 'valor_jan', 'jan': 'valor_jan',
            'fevereiro': 'valor_fev', 'fev': 'valor_fev',
            'março': 'valor_mar', 'mar': 'valor_mar', 'marco': 'valor_mar',
            'abril': 'valor_abr', 'abr': 'valor_abr',
            'maio': 'valor_mai', 'mai': 'valor_mai',
            'junho': 'valor_jun', 'jun': 'valor_jun',
            'julho': 'valor_jul', 'jul': 'valor_jul',
            'agosto': 'valor_ago', 'ago': 'valor_ago',
            'setembro': 'valor_set', 'set': 'valor_set',
            'outubro': 'valor_out', 'out': 'valor_out',
            'novembro': 'valor_nov', 'nov': 'valor_nov',
            'dezembro': 'valor_dez', 'dez': 'valor_dez',
            'variacao_mensal_%': 'variacao_mensal_pct', 'variação_mensal_%': 'variacao_mensal_pct',
            'variação mensal %': 'variacao_mensal_pct', 'variacao mensal %': 'variacao_mensal_pct',
            'var_mensal_%': 'variacao_mensal_pct', 'variacao_mensal_pct': 'variacao_mensal_pct',
            'variacao_anual_%': 'variacao_anual_pct', 'variação_anual_%': 'variacao_anual_pct',
            'variação anual %': 'variacao_anual_pct', 'variacao anual %': 'variacao_anual_pct',
            'var_anual_%': 'variacao_anual_pct', 'variacao_anual_pct': 'variacao_anual_pct',
            'moeda': 'moeda', 'tipo': 'tipo_categoria', 'tipo_categoria': 'tipo_categoria',
        }
        df.rename(columns=col_map, inplace=True)

        if 'categoria_nome' not in df.columns:
            return jsonify({'error': 'Coluna "Categoria" não encontrada na planilha'}), 400

        items = []
        for _, row in df.iterrows():
            cat = str(row.get('categoria_nome', '')).strip()
            if not cat or cat.lower() in ('nan', 'none', '') or cat.upper() == 'TOTAL':
                continue
            item = {
                'categoria_nome': cat,
                'tipo_categoria': str(row.get('tipo_categoria', '')),
                'moeda': str(row.get('moeda', 'EUR')),
                'variacao_mensal_pct': float(row.get('variacao_mensal_pct', 0) or 0),
                'variacao_anual_pct': float(row.get('variacao_anual_pct', 0) or 0),
            }
            for m in MONTHS:
                val = row.get(f'valor_{m}', 0)
                try:
                    item[f'valor_{m}'] = float(val) if val and str(val).lower() not in ('nan', '') else 0.0
                except (ValueError, TypeError):
                    item[f'valor_{m}'] = 0.0
            items.append(item)

        bulk_upsert_budget(user, ano, tipo, items)
        return jsonify({'status': 'ok', 'importados': len(items)})

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)


@bp.route('/api/budget/export', methods=['GET'])
def api_export_budget():
    user = _auth()
    if not user:
        return jsonify({'error': 'Não logado'}), 401

    ano = request.args.get('ano', type=int)
    tipo = request.args.get('tipo', 'despesa')

    if not ano:
        return jsonify({'error': 'Ano obrigatório'}), 400

    data = get_budget_items(user, ano, tipo)
    df = pd.DataFrame(data) if data else pd.DataFrame(
        columns=['categoria_nome'] + [f'valor_{m}' for m in MONTHS] +
                ['variacao_mensal_pct', 'variacao_anual_pct', 'moeda']
    )

    if not df.empty:
        month_labels = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
                        'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
        rename_map = {'categoria_nome': 'Categoria', 'tipo_categoria': 'Tipo',
                      'moeda': 'Moeda', 'variacao_mensal_pct': 'Variação Mensal %',
                      'variacao_anual_pct': 'Variação Anual %'}
        rename_map.update({f'valor_{MONTHS[i]}': month_labels[i] for i in range(12)})
        df.rename(columns=rename_map, inplace=True)
        cols_keep = ['Categoria', 'Tipo', 'Moeda'] + month_labels + ['Variação Mensal %', 'Variação Anual %']
        df = df[[c for c in cols_keep if c in df.columns]]

        total_row = {'Categoria': 'TOTAL'}
        for label in month_labels:
            if label in df.columns:
                total_row[label] = df[label].sum()
        df = pd.concat([df, pd.DataFrame([total_row])], ignore_index=True)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Budget')
    output.seek(0)

    tipo_label = 'Despesas' if tipo == 'despesa' else 'Receitas'
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'Budget_{tipo_label}_{ano}.xlsx'
    )


@bp.route('/api/budget/template', methods=['GET'])
def api_budget_template():
    tipo = request.args.get('tipo', 'despesa')
    tipo_label = 'Despesas' if tipo == 'despesa' else 'Receitas'
    month_labels = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
                    'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
    cols = ['Categoria', 'Tipo'] + month_labels + ['Variação Mensal %', 'Variação Anual %', 'Moeda']
    example = {
        'Categoria': f'Exemplo {tipo_label[:-1]}', 'Tipo': 'Fixo',
        'Variação Mensal %': 5, 'Variação Anual %': 10, 'Moeda': 'EUR'
    }
    for lbl in month_labels:
        example[lbl] = 0
    df = pd.DataFrame([example], columns=cols)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Template')
    output.seek(0)
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'Template_Budget_{tipo_label}.xlsx'
    )
