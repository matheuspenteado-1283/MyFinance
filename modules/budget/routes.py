import io
import math
import os
import pandas as pd
import re
import unicodedata
from flask import request, jsonify, send_file, session
from werkzeug.utils import secure_filename

from . import bp
from .db import (
    get_budget_items, get_budget_summary, upsert_budget_item,
    update_budget_item, delete_budget_item, delete_budget_year, bulk_replace_budget,
    get_budget_import_audit, get_comparativo, MONTHS
)
from config import allowed_file

UPLOAD_FOLDER = '/tmp/budget_uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def _auth():
    if 'user_email' not in session:
        return None
    return session['user_email']


def _normalize_header(value):
    text = str(value).strip().lower()
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r'[\s\-]+', '_', text)
    return re.sub(r'[^a-z0-9_%]+', '', text)


def _clean_text(value, default=''):
    if pd.isna(value):
        return default
    text = str(value).strip()
    return re.sub(r'\s+', ' ', text) or default


def _parse_budget_number(value):
    if value is None or pd.isna(value):
        return 0.0
    if isinstance(value, (int, float)):
        return 0.0 if math.isnan(value) else float(value)

    text = str(value).strip()
    if not text or text.lower() in ('nan', 'none', '-'):
        return 0.0

    text = text.replace('€', '').replace('R$', '').replace('$', '')
    text = text.replace('%', '').replace('\xa0', '').strip()

    if ',' in text and '.' in text:
        if text.rfind(',') > text.rfind('.'):
            text = text.replace('.', '').replace(',', '.')
        else:
            text = text.replace(',', '')
    elif ',' in text:
        text = text.replace(',', '.')

    try:
        return float(text)
    except ValueError:
        return 0.0


def _budget_items_from_dataframe(df):
    df.columns = [_normalize_header(c) for c in df.columns]

    col_map = {
        'categoria': 'categoria_nome', 'category': 'categoria_nome',
        'despesa': 'categoria_nome', 'receita': 'categoria_nome',
        'janeiro': 'valor_jan', 'jan': 'valor_jan',
        'fevereiro': 'valor_fev', 'fev': 'valor_fev',
        'marco': 'valor_mar', 'mar': 'valor_mar',
        'abril': 'valor_abr', 'abr': 'valor_abr',
        'maio': 'valor_mai', 'mai': 'valor_mai',
        'junho': 'valor_jun', 'jun': 'valor_jun',
        'julho': 'valor_jul', 'jul': 'valor_jul',
        'agosto': 'valor_ago', 'ago': 'valor_ago',
        'setembro': 'valor_set', 'set': 'valor_set',
        'outubro': 'valor_out', 'out': 'valor_out',
        'novembro': 'valor_nov', 'nov': 'valor_nov',
        'dezembro': 'valor_dez', 'dez': 'valor_dez',
        'variacao_mensal_%': 'variacao_mensal_pct',
        'variacao_mensal': 'variacao_mensal_pct',
        'var_mensal_%': 'variacao_mensal_pct',
        'variacao_mensal_pct': 'variacao_mensal_pct',
        'variacao_anual_%': 'variacao_anual_pct',
        'variacao_anual': 'variacao_anual_pct',
        'var_anual_%': 'variacao_anual_pct',
        'variacao_anual_pct': 'variacao_anual_pct',
        'moeda': 'moeda', 'tipo': 'tipo_categoria', 'tipo_categoria': 'tipo_categoria',
    }
    df.rename(columns=col_map, inplace=True)

    if 'categoria_nome' not in df.columns:
        raise ValueError('Coluna "Categoria" não encontrada na planilha')

    items = []
    for _, row in df.iterrows():
        cat = _clean_text(row.get('categoria_nome'))
        if not cat or cat.lower() in ('nan', 'none') or cat.upper() == 'TOTAL':
            continue

        item = {
            'categoria_nome': cat,
            'tipo_categoria': _clean_text(row.get('tipo_categoria')),
            'moeda': _clean_text(row.get('moeda'), 'EUR'),
            'variacao_mensal_pct': _parse_budget_number(row.get('variacao_mensal_pct')),
            'variacao_anual_pct': _parse_budget_number(row.get('variacao_anual_pct')),
        }
        for m in MONTHS:
            item[f'valor_{m}'] = _parse_budget_number(row.get(f'valor_{m}'))
        items.append(item)
    return items


def _budget_import_total(items):
    return sum(sum(item.get(f'valor_{m}', 0) for m in MONTHS) for item in items)


def _budget_rows_match_upload(saved_rows, items):
    if len(saved_rows) != len(items):
        return False
    numeric_fields = [f'valor_{m}' for m in MONTHS] + ['variacao_mensal_pct', 'variacao_anual_pct']
    for saved, item in zip(saved_rows, items):
        if _clean_text(saved.get('categoria_nome')) != item.get('categoria_nome'):
            return False
        if _clean_text(saved.get('tipo_categoria')) != item.get('tipo_categoria'):
            return False
        if _clean_text(saved.get('moeda'), 'EUR') != item.get('moeda'):
            return False
        for field in numeric_fields:
            if round(float(saved.get(field) or 0), 2) != round(float(item.get(field) or 0), 2):
                return False
    return True


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
    file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    if not allowed_file(filename) or file_ext not in {'csv', 'xls', 'xlsx'}:
        return jsonify({'error': 'Formato inválido. Use .xlsx ou .csv'}), 400

    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    try:
        if file_ext == 'csv':
            df = pd.read_csv(filepath)
        else:
            df = pd.read_excel(filepath)

        items = _budget_items_from_dataframe(df)
        bulk_replace_budget(user, ano, tipo, items)
        audit = get_budget_import_audit(user, ano, tipo)
        saved_rows = get_budget_items(user, ano, tipo)
        total_upload = _budget_import_total(items)
        total_salvo = float(audit['total_anual'] or 0)

        if (
            audit['count'] != len(items)
            or round(total_salvo, 2) != round(total_upload, 2)
            or not _budget_rows_match_upload(saved_rows, items)
        ):
            return jsonify({
                'error': 'Importação gravada com divergência. Tente importar novamente.',
                'importados': len(items),
                'total_upload': total_upload,
                'total_salvo': total_salvo,
                'audit': audit,
            }), 500

        return jsonify({
            'status': 'ok',
            'importados': len(items),
            'total_upload': total_upload,
            'total_salvo': total_salvo,
            'preview': audit['preview'],
        })

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
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
