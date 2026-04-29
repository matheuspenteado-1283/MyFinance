import os
import io
import pandas as pd
from flask import Flask, render_template, request, jsonify, send_file, session
from werkzeug.utils import secure_filename
from parser_utils import process_file, process_despesas_file
from database import (
    save_category_rule, register_user, verify_user, get_user_by_email,
    get_all_despesas, add_despesa, overwrite_despesas, update_despesa, delete_despesa,
    get_all_contas, add_conta, update_conta, delete_conta, get_senha_conta,
    get_all_receitas, add_receita, update_receita, delete_receita,
    get_all_investimentos, add_investimento, update_investimento, delete_investimento,
    get_all_usuarios, add_usuario, update_usuario, delete_usuario,
    get_despesas_mensais, save_despesas_mensais_batch, add_despesa_mensal,
    update_despesa_mensal, delete_despesa_mensal, consolidar_despesas_anuais,
    get_dashboard_data, get_annual_report,
    get_receitas_mensais, add_receita_mensal, update_receita_mensal, delete_receita_mensal,
    sync_receitas_from_despesas_mensais, get_totais_receitas
)
from exchange_api import get_exchange_rate

app = Flask(__name__)
app.secret_key = 'chave-super-secreta-extratos' # Necessário para usar session

# Configurações de Upload
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Max 16MB per upload

ALLOWED_EXTENSIONS = {'pdf', 'csv', 'xls', 'xlsx', 'xml'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/cad_despesas', methods=['GET'])
def api_get_despesas():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    return jsonify(get_all_despesas())

@app.route('/api/cad_despesas', methods=['POST'])
def api_post_despesa():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    data = request.json
    add_despesa(data.get('despesa'), data.get('tipo_despesa'), data.get('fator_divisao'), data.get('prioridade'))
    return jsonify({'status': 'ok'})

@app.route('/api/cad_despesas/<int:d_id>', methods=['PUT'])
def api_put_despesa(d_id):
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    data = request.json
    update_despesa(d_id, data.get('despesa'), data.get('tipo_despesa'), data.get('fator_divisao'), data.get('prioridade'))
    return jsonify({'status': 'ok'})

@app.route('/api/cad_despesas/upload', methods=['POST'])
def api_upload_despesas():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    if 'file' not in request.files: return jsonify({'error': 'Nenhum arquivo enviado'}), 400
    file = request.files['file']
    if not file or not allowed_file(file.filename): return jsonify({'error': 'Arquivo inválido'}), 400
    
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
    file.save(filepath)
    despesas_processadas = process_despesas_file(filepath)
    
    if len(despesas_processadas) == 0:
        return jsonify({'error': 'Nenhuma despesa válida encontrada. Confira as colunas.'}), 400
        
    overwrite_despesas(despesas_processadas)
    return jsonify({'status': 'ok', 'message': f'{len(despesas_processadas)} despesas cadastradas!'})

@app.route('/api/cad_despesas/export', methods=['POST', 'GET'])
def api_export_despesas():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    despesas = get_all_despesas()
    df = pd.DataFrame(despesas)
    if not df.empty:
        df.drop(columns=['id'], errors='ignore', inplace=True)
        df.rename(columns={'despesa': 'Despesa', 'tipo_despesa': 'Tipo de Despesa',
                           'fator_divisao': 'Fator de Divisão', 'prioridade': 'Prioridade'}, inplace=True)
    else:
        df = pd.DataFrame(columns=['Despesa', 'Tipo de Despesa', 'Fator de Divisão', 'Prioridade'])
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Despesas')
    output.seek(0)
    return send_file(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     as_attachment=True, download_name="Despesas_Cadastradas.xlsx")

# ── Contas Bancárias ─────────────────────────────────────────────────────
@app.route('/api/cad_contas', methods=['GET'])
def api_get_contas():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    return jsonify(get_all_contas())

@app.route('/api/cad_contas', methods=['POST'])
def api_post_conta():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    d = request.json
    add_conta(d.get('descricao'), d.get('agencia'), d.get('conta'),
              d.get('dados_acesso'), d.get('senha'), d.get('comentarios'))
    return jsonify({'status': 'ok'})

@app.route('/api/cad_contas/<int:c_id>', methods=['PUT'])
def api_put_conta(c_id):
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    d = request.json
    update_conta(c_id, d.get('descricao'), d.get('agencia'), d.get('conta'),
                 d.get('dados_acesso'), d.get('senha'), d.get('comentarios'))
    return jsonify({'status': 'ok'})

@app.route('/api/cad_contas/<int:c_id>', methods=['DELETE'])
def api_delete_conta(c_id):
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    delete_conta(c_id)
    return jsonify({'status': 'ok'})

@app.route('/api/cad_contas/<int:c_id>/senha', methods=['POST'])
def api_reveal_senha(c_id):
    """Revela senha da conta, exigindo a senha do App do usuário logado."""
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    app_password = (request.json or {}).get('app_password', '')
    if not verify_user(session['user_email'], app_password):
        return jsonify({'error': 'Senha do App incorreta'}), 403
    senha = get_senha_conta(c_id)
    return jsonify({'senha': senha})

# ── Receitas ───────────────────────────────────────────────────────────────────
@app.route('/api/cad_receitas', methods=['GET'])
def api_get_receitas():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    return jsonify(get_all_receitas())

@app.route('/api/cad_receitas', methods=['POST'])
def api_post_receita():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    d = request.json
    add_receita(d.get('descricao'))
    return jsonify({'status': 'ok'})

@app.route('/api/cad_receitas/<int:r_id>', methods=['PUT'])
def api_put_receita(r_id):
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    d = request.json
    update_receita(r_id, d.get('descricao'))
    return jsonify({'status': 'ok'})

@app.route('/api/cad_receitas/<int:r_id>', methods=['DELETE'])
def api_delete_receita(r_id):
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    delete_receita(r_id)
    return jsonify({'status': 'ok'})

# ── Investimentos ───────────────────────────────────────────────────────────────
@app.route('/api/cad_investimentos', methods=['GET'])
def api_get_investimentos():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    return jsonify(get_all_investimentos())

@app.route('/api/cad_investimentos', methods=['POST'])
def api_post_investimento():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    d = request.json
    add_investimento(d.get('descricao'))
    return jsonify({'status': 'ok'})

@app.route('/api/cad_investimentos/<int:i_id>', methods=['PUT'])
def api_put_investimento(i_id):
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    d = request.json
    update_investimento(i_id, d.get('descricao'))
    return jsonify({'status': 'ok'})

@app.route('/api/cad_investimentos/<int:i_id>', methods=['DELETE'])
def api_delete_investimento(i_id):
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    delete_investimento(i_id)
    return jsonify({'status': 'ok'})

@app.route('/api/cad_despesas/<int:d_id>', methods=['DELETE'])
def api_delete_despesa(d_id):
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    delete_despesa(d_id)
    return jsonify({'status': 'ok'})

# ── Usuários ───────────────────────────────────────────────────────────────
@app.route('/api/cad_usuarios', methods=['GET'])
def api_get_usuarios():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    return jsonify(get_all_usuarios())

@app.route('/api/cad_usuarios', methods=['POST'])
def api_post_usuario():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    d = request.json
    add_usuario(d.get('chave_usr1'), d.get('chave_usr2'), d.get('nome'), d.get('fator_pagamento',1))
    return jsonify({'status': 'ok'})

@app.route('/api/cad_usuarios/<int:u_id>', methods=['PUT'])
def api_put_usuario(u_id):
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    d = request.json
    update_usuario(u_id, d.get('chave_usr1'), d.get('chave_usr2'), d.get('nome'), d.get('fator_pagamento',1))
    return jsonify({'status': 'ok'})

@app.route('/api/cad_usuarios/<int:u_id>', methods=['DELETE'])
def api_delete_usuario(u_id):
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    delete_usuario(u_id)
    return jsonify({'status': 'ok'})

# ── Despesas Mensais ───────────────────────────────────────────────────────────────
@app.route('/api/despesas_mensais', methods=['GET'])
def api_get_despesas_mensais():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    mes = request.args.get('mes')
    return jsonify(get_despesas_mensais(session['user_email'], mes))

@app.route('/api/despesas_mensais/batch', methods=['POST'])
def api_save_batch_despesas_mensais():
    """Salva todas as transações da tela de revisão de uma vez."""
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    rows = request.json or []
    count = save_despesas_mensais_batch(session['user_email'], rows)
    return jsonify({'status': 'ok', 'saved': count})

@app.route('/api/despesas_mensais', methods=['POST'])
def api_post_despesa_mensal():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    add_despesa_mensal(session['user_email'], request.json or {})
    return jsonify({'status': 'ok'})

@app.route('/api/despesas_mensais/<int:d_id>', methods=['PUT'])
def api_put_despesa_mensal(d_id):
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    update_despesa_mensal(d_id, request.json or {})
    return jsonify({'status': 'ok'})

@app.route('/api/despesas_mensais/<int:d_id>', methods=['DELETE'])
def api_delete_despesa_mensal(d_id):
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    delete_despesa_mensal(d_id)
    return jsonify({'status': 'ok'})

@app.route('/api/despesas_anuais/consolidar', methods=['POST'])
def api_consolidar_anuais():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    import datetime
    ano = (request.json or {}).get('ano', datetime.date.today().year)
    count = consolidar_despesas_anuais(session['user_email'], ano)
    return jsonify({'status': 'ok', 'categorias': count})

@app.route('/api/dashboard_data', methods=['GET'])
def api_get_dashboard_data():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    mes = request.args.get('mes') # YYYY-MM
    if not mes: return jsonify({'error': 'Mês não informado'}), 400
    data = get_dashboard_data(session['user_email'], mes)
    return jsonify(data)

@app.route('/api/relatorio_anual', methods=['GET'])
def api_get_relatorio_anual():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    ano = request.args.get('ano')
    if not ano: return jsonify({'error': 'Ano não informado'}), 400
    data = get_annual_report(session['user_email'], int(ano))
    return jsonify(data)

@app.route('/export/despesas_mensais', methods=['POST'])
def export_despesas_mensais():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    data = request.json or {}
    mes = data.get('mes')
    if not mes: return jsonify({'error': 'Mês não informado'}), 400
    
    despesas = get_despesas_mensais(session['user_email'], mes)
    df = pd.DataFrame(despesas)
    if not df.empty:
        df.drop(columns=['id', 'mes_referencia', 'user_email', 'criado_em'], errors='ignore', inplace=True)
        df.rename(columns={
            'data': 'Data', 'descricao': 'Descrição', 'valor_original': 'Valor Original',
            'moeda': 'Moeda Original', 'cambio_eur': 'Câmbio EUR', 'valor_eur': 'Valor Final (EUR)',
            'usr1': 'USR1', 'usr2': 'USR2', 'diferenca_original': 'Diferença Original',
            'status_pago': 'Status Pago', 'categoria_final': 'Categoria Final',
            'receita': 'Receita', 'comentarios': 'Comentários', 'conta_bancaria': 'Conta Bancária'
        }, inplace=True)
        df['Receita'] = df['Receita'].map({1: 'Sim', 0: 'Não'})
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Detalhes Lancamentos')
    output.seek(0)
    
    ano, mes_num = mes.split('-')
    mes_extenso = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'][int(mes_num)-1]
    filename = f"Detalhes_Lancamentos_{mes_extenso}_{ano}.xlsx"
    
    return send_file(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    as_attachment=True, download_name=filename)

@app.route('/export/consolidacao', methods=['POST'])
def export_consolidacao():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    data = request.json or {}
    mes = data.get('mes')
    if not mes: return jsonify({'error': 'Mês não informado'}), 400
    
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
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Consolidacao')
    output.seek(0)
    
    ano, mes_num = mes.split('-')
    mes_extenso = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'][int(mes_num)-1]
    filename = f"Consolidacao_{mes_extenso}_{ano}.xlsx"
    
    return send_file(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    as_attachment=True, download_name=filename)

# ── Receitas Mensais ───────────────────────────────────────────────────────────────
@app.route('/api/receitas_mensais', methods=['GET'])
def api_get_receitas_mensais():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    mes = request.args.get('mes')
    return jsonify(get_receitas_mensais(session['user_email'], mes))

@app.route('/api/receitas_mensais/sync', methods=['POST'])
def api_sync_receitas():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    mes = request.json.get('mes') if request.json else None
    if not mes: return jsonify({'error': 'Mês não informado'}), 400
    count = sync_receitas_from_despesas_mensais(session['user_email'], mes)
    return jsonify({'status': 'ok', 'synced': count})

@app.route('/api/receitas_mensais/totais', methods=['GET'])
def api_totais_receitas():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    mes = request.args.get('mes')
    if not mes: return jsonify({'error': 'Mês não informado'}), 400
    return jsonify(get_totais_receitas(session['user_email'], mes))

@app.route('/api/cotacao', methods=['GET'])
def api_get_cotacao():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    date = request.args.get('date', '')
    from_cur = request.args.get('from', 'BRL')
    to = request.args.get('to', 'EUR')
    try:
        rate = get_exchange_rate(date, from_cur, to)
        return jsonify({'cotacao': rate})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/receitas_mensais', methods=['POST'])
def api_post_receita_mensal():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    add_receita_mensal(session['user_email'], request.json or {})
    return jsonify({'status': 'ok'})

@app.route('/api/receitas_mensais/<int:r_id>', methods=['PUT'])
def api_put_receita_mensal(r_id):
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    update_receita_mensal(r_id, request.json or {})
    return jsonify({'status': 'ok'})

@app.route('/api/receitas_mensais/<int:r_id>', methods=['DELETE'])
def api_delete_receita_mensal(r_id):
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    delete_receita_mensal(r_id)
    return jsonify({'status': 'ok'})

@app.route('/export/receitas_mensais', methods=['POST'])
def export_receitas_mensais():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    data = request.json or {}
    mes = data.get('mes')
    if not mes: return jsonify({'error': 'Mês não informado'}), 400
    
    receitas = get_receitas_mensais(session['user_email'], mes)
    df = pd.DataFrame(receitas)
    if not df.empty:
        df.drop(columns=['id', 'mes_referencia', 'user_email', 'despesa_mensal_id', 'criado_em'], errors='ignore', inplace=True)
        df.rename(columns={
            'data': 'Data', 'tipo_receita': 'Tipo de Receita', 'valor_original': 'Valor Original',
            'moeda_original': 'Moeda Original', 'cotacao': 'Cotação', 'valor_eur': 'Valor EUR',
            'valor_brl': 'Valor BRL', 'conta_bancaria': 'Conta Bancária', 'comentarios': 'Comentários'
        }, inplace=True)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Receitas')
    output.seek(0)
    
    ano, mes_num = mes.split('-')
    mes_extenso = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'][int(mes_num)-1]
    filename = f"Receitas_{mes_extenso}_{ano}.xlsx"
    
    return send_file(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    as_attachment=True, download_name=filename)

@app.route('/api/despesas_mensais/meses', methods=['GET'])
def api_meses_disponiveis():
    """Lista os meses/anos já salvos para exibir no filtro."""
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    from database import get_connection
    conn = get_connection()
    rows = conn.execute(
        'SELECT DISTINCT mes_referencia FROM despesas_mensais WHERE user_email=? ORDER BY mes_referencia DESC',
        (session['user_email'],)).fetchall()
    conn.close()
    return jsonify([r['mes_referencia'] for r in rows])


@app.route('/api/me', methods=['GET'])
def api_me():
    if 'user_email' in session:
        return jsonify({'logged_in': True, 'email': session['user_email']})
    return jsonify({'logged_in': False}), 401

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({'error': 'E-mail e senha são obrigatórios'}), 400
        
    if register_user(email, password):
        session['user_email'] = email
        return jsonify({'status': 'ok'})
    else:
        return jsonify({'error': 'E-mail já cadastrado'}), 400

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    
    if verify_user(email, password):
        session['user_email'] = email
        return jsonify({'status': 'ok'})
    return jsonify({'error': 'Credenciais inválidas'}), 401

@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user_email', None)
    return jsonify({'status': 'ok'})

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'files[]' not in request.files:
        return jsonify({'error': 'Nenhum arquivo enviado'}), 400
    
    files = request.files.getlist('files[]')
    
    if not files or all(file.filename == '' for file in files):
        return jsonify({'error': 'Nenhum arquivo selecionado'}), 400
        
    all_transactions = []
    
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Processa o arquivo imediatamente e junta na lista final
            file_transactions = process_file(filepath)
            all_transactions.extend(file_transactions)
            
    if len(all_transactions) == 0:
         return jsonify({'error': 'Nenhuma transação foi extraída dos arquivos. Verifique os formatos ou as colunas.', 'transactions': []}), 400
            
    return jsonify({
        'message': f'Extração concluída: {len(all_transactions)} transações processadas.',
        'transactions': all_transactions
    }), 200

@app.route('/save_category', methods=['POST'])
def save_category():
    data = request.json
    description = data.get('description')
    category = data.get('category')
    
    if description and category:
        save_category_rule(description, category)
        return jsonify({'status': 'ok'})
    return jsonify({'error': 'Dados inválidos'}), 400

@app.route('/export', methods=['POST'])
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
        if diff < 0.01:
            t['status'] = 'OK'
        else:
            t['status'] = 'NOK'

    df = pd.DataFrame(transactions)
    # Reordenar colunas pro Excel final ficar bonito
    cols = ['data', 'descricao', 'valor_original', 'moeda', 'cambio', 'valor_eur', 'pag1', 'pag2', 'diferenca', 'status', 'categoria']
    
    # Filtra só colunas que existem
    cols = [c for c in cols if c in df.columns]
    df = df[cols]
    
    # Renomeando as colunas
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
        'categoria': 'Categoria Final'
    }, inplace=True)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Extratos')
    output.seek(0)
    
    # O user baixa diretamente pelo navegador
    return send_file(
        output, 
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
        as_attachment=True, 
        download_name="Extratos_Processados.xlsx"
    )

if __name__ == '__main__':
    app.run(debug=True, port=5001)
