import os
import io
import pandas as pd
from flask import Flask, render_template, request, jsonify, send_file, session
from werkzeug.utils import secure_filename
from parser_utils import process_file, process_despesas_file
from database import save_category_rule, register_user, verify_user, get_user_by_email, get_all_despesas, add_despesa, overwrite_despesas, update_despesa

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
        df.rename(columns={
            'despesa': 'Despesa',
            'tipo_despesa': 'Tipo de Despesa',
            'fator_divisao': 'Fator de Divisão',
            'prioridade': 'Prioridade'
        }, inplace=True)
    else:
        df = pd.DataFrame(columns=['Despesa', 'Tipo de Despesa', 'Fator de Divisão', 'Prioridade'])
        
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Despesas')
    output.seek(0)
    
    return send_file(
        output, 
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
        as_attachment=True, 
        download_name="Despesas_Cadastradas.xlsx"
    )


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
