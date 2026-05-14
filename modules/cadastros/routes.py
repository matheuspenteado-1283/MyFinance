import os
import io
import pandas as pd
from flask import request, jsonify, send_file, session, current_app
from werkzeug.utils import secure_filename

from . import bp
from modules.auth.db import verify_user
from modules.extratos.parser import process_despesas_file
from .db.despesas import (
    get_all_despesas, add_despesa, update_despesa, delete_despesa, overwrite_despesas, clear_despesas,
)
from .db.contas import (
    get_all_contas, add_conta, update_conta, delete_conta, clear_contas, get_senha_conta,
)
from .db.receitas import (
    get_all_receitas, add_receita, update_receita, delete_receita, clear_receitas,
)
from .db.investimentos import (
    get_all_investimentos, add_investimento, update_investimento, delete_investimento, clear_investimentos,
)
from .db.usuarios import (
    get_all_usuarios, add_usuario, update_usuario, delete_usuario, clear_usuarios,
)
from .db.tipo_imposto import (
    get_all_tipo_imposto, add_tipo_imposto, update_tipo_imposto, delete_tipo_imposto, clear_tipo_imposto,
)
from config import allowed_file


# ── Despesas ──────────────────────────────────────────────────────────────────

@bp.route('/api/cad_despesas', methods=['GET'])
def api_get_despesas():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    return jsonify(get_all_despesas(session['user_email']))


@bp.route('/api/cad_despesas', methods=['POST'])
def api_post_despesa():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    data = request.json
    add_despesa(session['user_email'], data.get('despesa'), data.get('tipo_despesa'), data.get('fator_divisao'), data.get('prioridade'))
    return jsonify({'status': 'ok'})


@bp.route('/api/cad_despesas/<int:d_id>', methods=['PUT'])
def api_put_despesa(d_id):
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    data = request.json
    update_despesa(session['user_email'], d_id, data.get('despesa'), data.get('tipo_despesa'), data.get('fator_divisao'), data.get('prioridade'))
    return jsonify({'status': 'ok'})


@bp.route('/api/cad_despesas/<int:d_id>', methods=['DELETE'])
def api_delete_despesa(d_id):
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    delete_despesa(session['user_email'], d_id)
    return jsonify({'status': 'ok'})


@bp.route('/api/cad_despesas/upload', methods=['POST'])
def api_upload_despesas():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    if 'file' not in request.files:
        return jsonify({'error': 'Nenhum arquivo enviado'}), 400
    file = request.files['file']
    if not file or not allowed_file(file.filename):
        return jsonify({'error': 'Arquivo inválido'}), 400

    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
    file.save(filepath)
    despesas_processadas = process_despesas_file(filepath)

    if len(despesas_processadas) == 0:
        return jsonify({'error': 'Nenhuma despesa válida encontrada. Confira as colunas.'}), 400

    overwrite_despesas(session['user_email'], despesas_processadas)
    return jsonify({'status': 'ok', 'message': f'{len(despesas_processadas)} despesas cadastradas!'})


@bp.route('/api/cad_despesas/export', methods=['POST', 'GET'])
def api_export_despesas():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    despesas = get_all_despesas(session['user_email'])
    df = pd.DataFrame(despesas)
    if not df.empty:
        df.drop(columns=['id', 'user_email'], errors='ignore', inplace=True)
        df.rename(columns={
            'despesa': 'Despesa', 'tipo_despesa': 'Tipo de Despesa',
            'fator_divisao': 'Fator de Divisão', 'prioridade': 'Prioridade',
        }, inplace=True)
    else:
        df = pd.DataFrame(columns=['Despesa', 'Tipo de Despesa', 'Fator de Divisão', 'Prioridade'])
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Despesas')
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name='Despesas_Cadastradas.xlsx')


# ── Contas Bancárias ──────────────────────────────────────────────────────────

@bp.route('/api/cad_contas', methods=['GET'])
def api_get_contas():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    return jsonify(get_all_contas(session['user_email']))


@bp.route('/api/cad_contas', methods=['POST'])
def api_post_conta():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    d = request.json
    add_conta(session['user_email'], d.get('descricao'), d.get('agencia'), d.get('conta'),
              d.get('dados_acesso'), d.get('senha'), d.get('comentarios'))
    return jsonify({'status': 'ok'})


@bp.route('/api/cad_contas/<int:c_id>', methods=['PUT'])
def api_put_conta(c_id):
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    d = request.json
    update_conta(session['user_email'], c_id, d.get('descricao'), d.get('agencia'), d.get('conta'),
                 d.get('dados_acesso'), d.get('senha'), d.get('comentarios'))
    return jsonify({'status': 'ok'})


@bp.route('/api/cad_contas/<int:c_id>', methods=['DELETE'])
def api_delete_conta(c_id):
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    delete_conta(session['user_email'], c_id)
    return jsonify({'status': 'ok'})


@bp.route('/api/cad_contas/<int:c_id>/senha', methods=['POST'])
def api_reveal_senha(c_id):
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    app_password = (request.json or {}).get('app_password', '')
    if not verify_user(session['user_email'], app_password):
        return jsonify({'error': 'Senha do App incorreta'}), 403
    senha = get_senha_conta(session['user_email'], c_id)
    return jsonify({'senha': senha})


@bp.route('/api/upload_contas', methods=['POST'])
def api_upload_contas():
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
        count = 0
        clear_contas(session['user_email'])
        df.columns = df.columns.str.strip().str.lower()
        col_desc = next((c for c in df.columns if 'descri' in c), 'descricao')
        col_age = next((c for c in df.columns if 'ag' in c), 'agencia')
        col_conta = next((c for c in df.columns if 'conta' in c and 'dados' not in c), 'conta')
        col_acesso = next((c for c in df.columns if 'acesso' in c), 'dados_acesso')
        col_senha = next((c for c in df.columns if 'senha' in c), 'senha')
        col_obs = next((c for c in df.columns if 'coment' in c), 'comentarios')
        for _, row in df.iterrows():
            def g(c):
                v = row.get(c)
                return '' if pd.isna(v) else str(v).strip()
            add_conta(session['user_email'], g(col_desc), g(col_age), g(col_conta), g(col_acesso), g(col_senha), g(col_obs))
            count += 1
        os.remove(filepath)
        return jsonify({'status': 'ok', 'count': count})
    except Exception as e:
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({'error': str(e)}), 400


@bp.route('/api/export_contas', methods=['GET'])
def api_export_contas():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    contas = get_all_contas(session['user_email'])
    df = pd.DataFrame(contas)
    if not df.empty:
        df.drop(columns=['id', 'user_email'], errors='ignore', inplace=True)
        df.rename(columns={
            'descricao': 'Descrição', 'agencia': 'Agência', 'conta': 'Conta',
            'dados_acesso': 'Dados Acesso', 'senha': 'Senha', 'comentarios': 'Comentários',
        }, inplace=True)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Contas')
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name='Cadastro_Contas.xlsx')


# ── Receitas ──────────────────────────────────────────────────────────────────

@bp.route('/api/cad_receitas', methods=['GET'])
def api_get_receitas():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    return jsonify(get_all_receitas(session['user_email']))


@bp.route('/api/cad_receitas', methods=['POST'])
def api_post_receita():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    d = request.json
    add_receita(session['user_email'], d.get('descricao'))
    return jsonify({'status': 'ok'})


@bp.route('/api/cad_receitas/<int:r_id>', methods=['PUT'])
def api_put_receita(r_id):
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    d = request.json
    update_receita(session['user_email'], r_id, d.get('descricao'))
    return jsonify({'status': 'ok'})


@bp.route('/api/cad_receitas/<int:r_id>', methods=['DELETE'])
def api_delete_receita(r_id):
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    delete_receita(session['user_email'], r_id)
    return jsonify({'status': 'ok'})


@bp.route('/api/upload_receitas', methods=['POST'])
def api_upload_receitas():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    if 'file' not in request.files:
        return jsonify({'error': 'Nenhum arquivo'}), 400
    file = request.files['file']
    if not file.filename.endswith(('.csv', '.xls', '.xlsx')):
        return jsonify({'error': 'Arquivo inválido'}), 400
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
    file.save(filepath)
    try:
        filename = file.filename.lower()
        df = pd.read_excel(filepath) if filename.endswith(('.xls', '.xlsx')) else pd.read_csv(filepath)
        count = 0
        clear_receitas(session['user_email'])
        df.columns = df.columns.str.strip().str.lower()
        col_desc = next((c for c in df.columns if 'descri' in c), 'descricao')
        for _, row in df.iterrows():
            val = row.get(col_desc)
            if pd.notna(val) and str(val).strip():
                add_receita(session['user_email'], str(val).strip())
                count += 1
        os.remove(filepath)
        return jsonify({'status': 'ok', 'count': count})
    except Exception as e:
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({'error': str(e)}), 400


@bp.route('/api/export_receitas', methods=['GET'])
def api_export_receitas():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    receitas = get_all_receitas(session['user_email'])
    df = pd.DataFrame(receitas)
    if not df.empty:
        df.drop(columns=['id', 'user_email'], errors='ignore', inplace=True)
    df.rename(columns={'descricao': 'Descrição'}, inplace=True)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Receitas')
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name='Cadastro_Receitas.xlsx')


# ── Investimentos ─────────────────────────────────────────────────────────────

@bp.route('/api/cad_investimentos', methods=['GET'])
def api_get_investimentos():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    return jsonify(get_all_investimentos(session['user_email']))


@bp.route('/api/cad_investimentos', methods=['POST'])
def api_post_investimento():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    d = request.json
    add_investimento(session['user_email'], d.get('descricao'))
    return jsonify({'status': 'ok'})


@bp.route('/api/cad_investimentos/<int:i_id>', methods=['PUT'])
def api_put_investimento(i_id):
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    d = request.json
    update_investimento(session['user_email'], i_id, d.get('descricao'))
    return jsonify({'status': 'ok'})


@bp.route('/api/cad_investimentos/<int:i_id>', methods=['DELETE'])
def api_delete_investimento(i_id):
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    delete_investimento(session['user_email'], i_id)
    return jsonify({'status': 'ok'})


@bp.route('/api/upload_investimentos', methods=['POST'])
def api_upload_investimentos():
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
        count = 0
        clear_investimentos(session['user_email'])
        df.columns = df.columns.str.strip().str.lower()
        col_desc = next((c for c in df.columns if 'descri' in c), 'descricao')
        for _, row in df.iterrows():
            val = row.get(col_desc)
            if pd.notna(val) and str(val).strip():
                add_investimento(session['user_email'], str(val).strip())
                count += 1
        os.remove(filepath)
        return jsonify({'status': 'ok', 'count': count})
    except Exception as e:
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({'error': str(e)}), 400


@bp.route('/api/export_investimentos', methods=['GET'])
def api_export_investimentos():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    investimentos = get_all_investimentos(session['user_email'])
    df = pd.DataFrame(investimentos)
    if not df.empty:
        df.drop(columns=['id', 'user_email'], errors='ignore', inplace=True)
    df.rename(columns={'descricao': 'Descrição'}, inplace=True)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Investimentos')
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name='Cadastro_Investimentos.xlsx')


# ── Usuários ──────────────────────────────────────────────────────────────────

@bp.route('/api/cad_usuarios', methods=['GET'])
def api_get_usuarios():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    return jsonify(get_all_usuarios(session['user_email']))


@bp.route('/api/cad_usuarios', methods=['POST'])
def api_post_usuario():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    d = request.json
    add_usuario(session['user_email'], d.get('chave_usr1'), d.get('chave_usr2'), d.get('nome'), d.get('fator_pagamento', 1))
    return jsonify({'status': 'ok'})


@bp.route('/api/cad_usuarios/<int:u_id>', methods=['PUT'])
def api_put_usuario(u_id):
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    d = request.json
    update_usuario(session['user_email'], u_id, d.get('chave_usr1'), d.get('chave_usr2'), d.get('nome'), d.get('fator_pagamento', 1))
    return jsonify({'status': 'ok'})


@bp.route('/api/cad_usuarios/<int:u_id>', methods=['DELETE'])
def api_delete_usuario(u_id):
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    delete_usuario(session['user_email'], u_id)
    return jsonify({'status': 'ok'})


@bp.route('/api/upload_usuarios', methods=['POST'])
def api_upload_usuarios():
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
        count = 0
        clear_usuarios(session['user_email'])
        for _, row in df.iterrows():
            add_usuario(
                session['user_email'],
                str(row.get('chave_usr1', row.get('Chave Usr1', ''))),
                str(row.get('chave_usr2', row.get('Chave Usr2', ''))),
                str(row.get('nome', row.get('Nome', ''))),
                int(row.get('fator_pagamento', row.get('Fator Pagamento', 1))),
            )
            count += 1
        os.remove(filepath)
        return jsonify({'status': 'ok', 'count': count})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@bp.route('/api/export_usuarios', methods=['GET'])
def api_export_usuarios():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    usuarios = get_all_usuarios(session['user_email'])
    df = pd.DataFrame(usuarios)
    if not df.empty:
        df.drop(columns=['id', 'user_email'], errors='ignore', inplace=True)
    df.rename(columns={
        'nome': 'Nome', 'chave_usr1': 'Chave Usr1', 'chave_usr2': 'Chave Usr2',
        'fator_pagamento': 'Fator Pagamento',
    }, inplace=True)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Usuarios')
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name='Cadastro_Usuarios.xlsx')


# ── Tipo Imposto ──────────────────────────────────────────────────────────────

@bp.route('/api/cad_tipo_imposto', methods=['GET'])
def api_get_tipo_imposto():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    return jsonify(get_all_tipo_imposto(session['user_email']))


@bp.route('/api/cad_tipo_imposto', methods=['POST'])
def api_post_tipo_imposto():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    d = request.json
    add_tipo_imposto(session['user_email'], d.get('tp_imposto'), d.get('alq_imposto'), d.get('pagamento'))
    return jsonify({'status': 'ok'})


@bp.route('/api/cad_tipo_imposto/<int:ti_id>', methods=['PUT'])
def api_put_tipo_imposto(ti_id):
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    d = request.json
    update_tipo_imposto(session['user_email'], ti_id, d.get('tp_imposto'), d.get('alq_imposto'), d.get('pagamento'))
    return jsonify({'status': 'ok'})


@bp.route('/api/cad_tipo_imposto/<int:ti_id>', methods=['DELETE'])
def api_delete_tipo_imposto(ti_id):
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    delete_tipo_imposto(session['user_email'], ti_id)
    return jsonify({'status': 'ok'})


@bp.route('/api/upload_tipo_imposto', methods=['POST'])
def api_upload_tipo_imposto():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    if 'file' not in request.files:
        return jsonify({'error': 'Nenhum arquivo'}), 400
    file = request.files['file']
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
    file.save(filepath)
    try:
        df = pd.read_excel(filepath) if filepath.endswith(('.xls', '.xlsx')) else pd.read_csv(filepath)
        count = 0
        clear_tipo_imposto(session['user_email'])
        for _, row in df.iterrows():
            tp = row.get('tp_imposto') if pd.notna(row.get('tp_imposto')) else row.get('Tipo Imposto')
            alq = row.get('alq_imposto') if pd.notna(row.get('alq_imposto')) else row.get('Alíquota (%)')
            pag = row.get('pagamento') if pd.notna(row.get('pagamento')) else row.get('Pagamento')
            if pd.notna(tp):
                add_tipo_imposto(session['user_email'], str(tp), float(alq) if pd.notna(alq) else None, str(pag if pd.notna(pag) else ''))
                count += 1
        os.remove(filepath)
        return jsonify({'status': 'ok', 'count': count})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@bp.route('/api/export_tipo_imposto', methods=['GET'])
def api_export_tipo_imposto():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    tipos = get_all_tipo_imposto(session['user_email'])
    df = pd.DataFrame(tipos)
    if not df.empty:
        df.drop(columns=['id', 'user_email'], errors='ignore', inplace=True)
    df.rename(columns={
        'tp_imposto': 'Tipo Imposto', 'alq_imposto': 'Alíquota (%)', 'pagamento': 'Pagamento',
    }, inplace=True)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Tipo Imposto')
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name='Cadastro_Tipo_Imposto.xlsx')
