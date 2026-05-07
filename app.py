import os
import io
import pandas as pd
from flask import Flask, render_template, request, jsonify, send_file, session
from werkzeug.utils import secure_filename
from parser_utils import process_file, process_despesas_file
from database import (
    save_category_rule, register_user, verify_user, get_user_by_email,
    get_all_despesas, add_despesa, overwrite_despesas, update_despesa, delete_despesa, clear_despesas,
    get_all_contas, add_conta, update_conta, delete_conta, get_senha_conta, clear_contas,
    get_all_receitas, add_receita, update_receita, delete_receita, clear_receitas,
    get_all_investimentos, add_investimento, update_investimento, delete_investimento, clear_investimentos,
    get_all_usuarios, add_usuario, update_usuario, delete_usuario, clear_usuarios,
    get_despesas_mensais, save_despesas_mensais_batch, add_despesa_mensal,
    update_despesa_mensal, delete_despesa_mensal, delete_despesas_mensais_batch, clear_despesas_mensais, consolidar_despesas_anuais,
    get_consolidacao_tipo_despesa, get_dashboard_data, get_annual_report,
    get_receitas_mensais, add_receita_mensal, update_receita_mensal, delete_receita_mensal,
    sync_receitas_from_despesas_mensais, get_totais_receitas,
    get_all_tipo_imposto, add_tipo_imposto, update_tipo_imposto, delete_tipo_imposto, clear_tipo_imposto,
    get_all_lcto_impostos, add_lcto_imposto, update_lcto_imposto, delete_lcto_imposto,
    get_dashboard_impostos,
    get_all_lcto_emprestimos, add_lcto_emprestimo, update_lcto_emprestimo, delete_lcto_emprestimo,
    get_saldo_emprestimos, limpar_dados_usuario,
    get_all_lcto_investimentos, add_lcto_investimento, update_lcto_investimento, delete_lcto_investimento, clear_lcto_investimentos,
    save_relatorio_dinamico, get_all_relatorios_dinamicos, delete_relatorio_dinamico, get_dados_relatorio_dinamico, get_tabelas_campos,
    get_all_trader_positions, add_trader_position, update_trader_position, delete_trader_position, clear_trader_positions,
    get_trader_periodos, get_trader_contas
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
    return jsonify(get_all_despesas())

@app.route('/api/cad_despesas', methods=['POST'])
def api_post_despesa():
    data = request.json
    add_despesa(data.get('despesa'), data.get('tipo_despesa'), data.get('fator_divisao'), data.get('prioridade'))
    return jsonify({'status': 'ok'})

@app.route('/api/cad_despesas/<int:d_id>', methods=['PUT'])
def api_put_despesa(d_id):
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
    return jsonify(get_all_contas())

@app.route('/api/cad_contas', methods=['POST'])
def api_post_conta():
    d = request.json
    add_conta(d.get('descricao'), d.get('agencia'), d.get('conta'),
              d.get('dados_acesso'), d.get('senha'), d.get('comentarios'))
    return jsonify({'status': 'ok'})

@app.route('/api/cad_contas/<int:c_id>', methods=['PUT'])
def api_put_conta(c_id):
    d = request.json
    update_conta(c_id, d.get('descricao'), d.get('agencia'), d.get('conta'),
                 d.get('dados_acesso'), d.get('senha'), d.get('comentarios'))
    return jsonify({'status': 'ok'})

@app.route('/api/cad_contas/<int:c_id>', methods=['DELETE'])
def api_delete_conta(c_id):
    delete_conta(c_id)
    return jsonify({'status': 'ok'})

@app.route('/api/cad_contas/<int:c_id>/senha', methods=['POST'])
def api_reveal_senha(c_id):
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    app_password = (request.json or {}).get('app_password', '')
    if not verify_user(session['user_email'], app_password):
        return jsonify({'error': 'Senha do App incorreta'}), 403
    senha = get_senha_conta(c_id)
    return jsonify({'senha': senha})

# ── Receitas ───────────────────────────────────────────────────────────────────
@app.route('/api/cad_receitas', methods=['GET'])
def api_get_receitas():
    return jsonify(get_all_receitas())

@app.route('/api/cad_receitas', methods=['POST'])
def api_post_receita():
    d = request.json
    add_receita(d.get('descricao'))
    return jsonify({'status': 'ok'})

@app.route('/api/cad_receitas/<int:r_id>', methods=['PUT'])
def api_put_receita(r_id):
    d = request.json
    update_receita(r_id, d.get('descricao'))
    return jsonify({'status': 'ok'})

@app.route('/api/cad_receitas/<int:r_id>', methods=['DELETE'])
def api_delete_receita(r_id):
    delete_receita(r_id)
    return jsonify({'status': 'ok'})

# ── Investimentos ───────────────────────────────────────────────────────────────
@app.route('/api/cad_investimentos', methods=['GET'])
def api_get_investimentos():
    return jsonify(get_all_investimentos())

@app.route('/api/cad_investimentos', methods=['POST'])
def api_post_investimento():
    d = request.json
    add_investimento(d.get('descricao'))
    return jsonify({'status': 'ok'})

@app.route('/api/cad_investimentos/<int:i_id>', methods=['PUT'])
def api_put_investimento(i_id):
    d = request.json
    update_investimento(i_id, d.get('descricao'))
    return jsonify({'status': 'ok'})

@app.route('/api/cad_investimentos/<int:i_id>', methods=['DELETE'])
def api_delete_investimento(i_id):
    delete_investimento(i_id)
    return jsonify({'status': 'ok'})

@app.route('/api/cad_despesas/<int:d_id>', methods=['DELETE'])
def api_delete_despesa(d_id):
    delete_despesa(d_id)
    return jsonify({'status': 'ok'})

# ── Usuários ───────────────────────────────────────────────────────────────
@app.route('/api/cad_usuarios', methods=['GET'])
def api_get_usuarios():
    return jsonify(get_all_usuarios())

@app.route('/api/cad_usuarios', methods=['POST'])
def api_post_usuario():
    d = request.json
    add_usuario(d.get('chave_usr1'), d.get('chave_usr2'), d.get('nome'), d.get('fator_pagamento',1))
    return jsonify({'status': 'ok'})

@app.route('/api/cad_usuarios/<int:u_id>', methods=['PUT'])
def api_put_usuario(u_id):
    d = request.json
    update_usuario(u_id, d.get('chave_usr1'), d.get('chave_usr2'), d.get('nome'), d.get('fator_pagamento',1))
    return jsonify({'status': 'ok'})

@app.route('/api/cad_usuarios/<int:u_id>', methods=['DELETE'])
def api_delete_usuario(u_id):
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

@app.route('/api/despesas_mensais/batch_delete', methods=['POST'])
def api_batch_delete_despesas_mensais():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    data = request.json or {}
    ids = data.get('ids', [])
    if ids:
        delete_despesas_mensais_batch(ids)
    return jsonify({'status': 'ok'})

@app.route('/api/despesas_mensais/clear', methods=['POST'])
def api_clear_despesas_mensais():
    """Limpa todas as despesas mensais do usuário, ou apenas um mês específico."""
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    mes = (request.json or {}).get('mes')  # Opcional: YYYY-MM
    clear_despesas_mensais(session['user_email'], mes)
    return jsonify({'status': 'ok', 'message': f'Registros {"do mês " + mes if mes else ""} removidos com sucesso!'})

@app.route('/api/despesas_mensais/upload', methods=['POST'])
def api_upload_despesas_mensais():
    """Upload de despesas mensais via planilha Excel/CSV - modo preview."""
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    if 'file' not in request.files: return jsonify({'error': 'Nenhum arquivo'}), 400
    file = request.files['file']
    if not file.filename.endswith(('.csv', '.xls', '.xlsx')): return jsonify({'error': 'Arquivo inválido'}), 400
    
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
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
                
                if desc.lower() in ['nan', 'none', ''] or not desc: continue
                if val_orig == 0: continue
                
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
                        'mes_referencia': mes_ref
                    })
                    idx += 1
            except Exception as e:
                continue
        os.remove(filepath)
        return jsonify({'preview': True, 'data': preview_data, 'mes': mes_ref})
    except Exception as e:
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({'error': str(e)}), 400

@app.route('/api/despesas_mensais/upload_confirm', methods=['POST'])
def api_upload_despesas_mensais_confirm():
    """Confirma a importação das linhas selecionadas."""
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
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
                    'mes_referencia': row.get('mes_referencia', '')
                })
                count += 1
            except Exception as e:
                print(f"Erro ao salvar linha: {e}")
                continue
    return jsonify({'status': 'ok', 'count': count, 'message': f'{count} despesas importadas!'})

@app.route('/api/despesas_anuais/consolidar', methods=['POST'])
def api_consolidar_anuais():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    import datetime
    ano = (request.json or {}).get('ano', datetime.date.today().year)
    count = consolidar_despesas_anuais(session['user_email'], ano)
    return jsonify({'status': 'ok', 'categorias': count})

@app.route('/api/despesas_mensais/consolidacao', methods=['GET'])
def api_consolidacao_tipo_despesa():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    mes = request.args.get('mes')
    if not mes: return jsonify({'error': 'Mês não informado'}), 400
    data = get_consolidacao_tipo_despesa(session['user_email'], mes)
    return jsonify(data)

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
        
        num_cols = ['Valor Original', 'Câmbio EUR', 'Valor Final (EUR)', 'USR1', 'USR2', 'Diferença Original']
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '.'), errors='coerce')
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Detalhes Lancamentos')
        workbook = writer.book
        worksheet = writer.sheets['Detalhes Lancamentos']
        
        from openpyxl.styles import numbers
        for col in num_cols:
            if col in df.columns:
                col_idx = df.columns.get_loc(col) + 1
                for row in range(2, len(df) + 2):
                    cell = worksheet.cell(row=row, column=col_idx)
                    cell.number_format = '#,##0.00'
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
    num_cols = ['Total Usr1', 'Total Usr2', 'Total Geral']
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Consolidacao')
        workbook = writer.book
        worksheet = writer.sheets['Consolidacao']
        
        from openpyxl.styles import numbers
        for col in num_cols:
            if col in df.columns:
                col_idx = df.columns.get_loc(col) + 1
                for row in range(2, len(df) + 2):
                    cell = worksheet.cell(row=row, column=col_idx)
                    cell.number_format = '#,##0.00'
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
    date = request.args.get('date') or 'latest'
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

@app.route('/api/cad_tipo_imposto', methods=['GET'])
def api_get_tipo_imposto():
    return jsonify(get_all_tipo_imposto())

@app.route('/api/cad_tipo_imposto', methods=['POST'])
def api_post_tipo_imposto():
    d = request.json
    add_tipo_imposto(d.get('tp_imposto'), d.get('alq_imposto'), d.get('pagamento'))
    return jsonify({'status': 'ok'})

@app.route('/api/cad_tipo_imposto/<int:ti_id>', methods=['PUT'])
def api_put_tipo_imposto(ti_id):
    d = request.json
    update_tipo_imposto(ti_id, d.get('tp_imposto'), d.get('alq_imposto'), d.get('pagamento'))
    return jsonify({'status': 'ok'})

@app.route('/api/cad_tipo_imposto/<int:ti_id>', methods=['DELETE'])
def api_delete_tipo_imposto(ti_id):
    delete_tipo_imposto(ti_id)
    return jsonify({'status': 'ok'})

@app.route('/api/lcto_impostos', methods=['GET'])
def api_get_lcto_impostos():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    return jsonify(get_all_lcto_impostos(session['user_email']))

@app.route('/api/lcto_impostos', methods=['POST'])
def api_post_lcto_imposto():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    d = request.json
    add_lcto_imposto(session['user_email'], d.get('mes_ano'), d.get('tp_imposto'),
                    d.get('moeda_faturado'), d.get('valor_faturado'), d.get('valor_imposto'),
                    d.get('moeda_pagamento'), d.get('pagamento'), d.get('pagamento_mes_ano'), d.get('desconto_iva'))
    return jsonify({'status': 'ok'})

@app.route('/api/lcto_impostos/<int:li_id>', methods=['PUT'])
def api_put_lcto_imposto(li_id):
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    d = request.json
    update_lcto_imposto(li_id, d.get('mes_ano'), d.get('tp_imposto'),
                       d.get('moeda_faturado'), d.get('valor_faturado'), d.get('valor_imposto'),
                       d.get('moeda_pagamento'), d.get('pagamento'), d.get('pagamento_mes_ano'), d.get('desconto_iva'))
    return jsonify({'status': 'ok'})

@app.route('/api/dashboard_impostos', methods=['GET'])
def api_get_dashboard_impostos():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    data = get_dashboard_impostos(session['user_email'])
    return jsonify(data)

@app.route('/api/lcto_impostos/<int:li_id>', methods=['DELETE'])
def api_delete_lcto_imposto(li_id):
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    delete_lcto_imposto(li_id)
    return jsonify({'status': 'ok'})

@app.route('/api/lcto_emprestimos', methods=['GET'])
def api_get_lcto_emprestimos():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    return jsonify(get_all_lcto_emprestimos(session['user_email']))

@app.route('/api/lcto_emprestimos', methods=['POST'])
def api_post_lcto_emprestimo():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    d = request.json
    add_lcto_emprestimo(session['user_email'], d.get('tipo'), d.get('beneficiario'),
                      d.get('valor_operacao'), d.get('moeda_emp', 'BRL'),
                      d.get('data_emprestimo'), d.get('data_operacao'),
                      d.get('obs'), d.get('status', 'Ativo'))
    return jsonify({'status': 'ok'})

@app.route('/api/lcto_emprestimos/<int:le_id>', methods=['PUT'])
def api_put_lcto_emprestimo(le_id):
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    d = request.json
    update_lcto_emprestimo(le_id, d.get('tipo'), d.get('beneficiario'),
                         d.get('valor_operacao'), d.get('moeda_emp', 'BRL'),
                         d.get('data_emprestimo'), d.get('data_operacao'),
                         d.get('obs'), d.get('status', 'Ativo'))
    return jsonify({'status': 'ok'})

@app.route('/api/lcto_emprestimos/<int:le_id>', methods=['DELETE'])
def api_delete_lcto_emprestimo(le_id):
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    delete_lcto_emprestimo(le_id)
    return jsonify({'status': 'ok'})

@app.route('/api/lcto_emprestimos/saldo', methods=['GET'])
def api_get_saldo_emprestimos():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    return jsonify(get_saldo_emprestimos(session['user_email']))

# ── Lançamento Investimentos ─────────────────────────────────────────────────────────
@app.route('/api/lcto_investimentos', methods=['GET'])
def api_get_lcto_investimentos():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    return jsonify(get_all_lcto_investimentos(session['user_email']))

@app.route('/api/lcto_investimentos', methods=['POST'])
def api_post_lcto_investimento():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    d = request.json
    add_lcto_investimento(session['user_email'], d.get('banco'), d.get('tp_investimento'),
                          d.get('data_inv'), d.get('valor_inv'), d.get('moeda', 'BRL'),
                          d.get('qtd'), d.get('taxa'), d.get('valor_atual'),
                          d.get('val_mes_ant'), d.get('aporte'))
    return jsonify({'status': 'ok'})

@app.route('/api/lcto_investimentos/<int:li_id>', methods=['PUT'])
def api_put_lcto_investimento(li_id):
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    d = request.json
    update_lcto_investimento(li_id, d.get('banco'), d.get('tp_investimento'),
                             d.get('data_inv'), d.get('valor_inv'), d.get('moeda', 'BRL'),
                             d.get('qtd'), d.get('taxa'), d.get('valor_atual'),
                             d.get('val_mes_ant'), d.get('aporte'))
    return jsonify({'status': 'ok'})

@app.route('/api/lcto_investimentos/<int:li_id>', methods=['DELETE'])
def api_delete_lcto_investimento(li_id):
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    delete_lcto_investimento(li_id)
    return jsonify({'status': 'ok'})

@app.route('/api/upload_lcto_investimentos', methods=['POST'])
def api_upload_lcto_investimentos():
    if 'file' not in request.files: return jsonify({'error': 'Nenhum arquivo'}), 400
    file = request.files['file']
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
    file.save(filepath)
    try:
        filename = file.filename.lower()
        df = pd.read_excel(filepath) if filename.endswith(('.xls','.xlsx')) else pd.read_csv(filepath)
        clear_lcto_investimentos()
        for _, row in df.iterrows():
            add_lcto_investimento(
                session['user_email'],
                str(row.get('banco', row.get('Banco', ''))),
                str(row.get('tp_investimento', row.get('Tipo Investimento', ''))),
                str(row.get('data_inv', row.get('Data Investimento', ''))),
                float(row.get('valor_inv', row.get('Valor Investimento', 0)) or 0),
                str(row.get('moeda', row.get('Moeda', 'BRL'))),
                float(row.get('qtd', row.get('Quantidade', 0)) or 0),
                float(row.get('taxa', row.get('Taxa', 0)) or 0),
                float(row.get('valor_atual', row.get('Valor Atual', 0)) or 0),
                float(row.get('val_mes_ant', row.get('Valor Mês Anterior', 0)) or 0),
                float(row.get('aporte', row.get('Aporte', 0)) or 0)
            )
        os.remove(filepath)
        return jsonify({'status': 'ok'})
    except Exception as e:
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({'error': str(e)}), 400

@app.route('/api/export_lcto_investimentos', methods=['GET'])
def api_export_lcto_investimentos():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    data = get_all_lcto_investimentos(session['user_email'])
    df = pd.DataFrame(data)
    if not df.empty:
        df = df.drop(columns=['id', 'user_email', 'criado_em'], errors='ignore')
        df.rename(columns={
            'banco': 'Banco', 'tp_investimento': 'Tipo Investimento', 'data_inv': 'Data Investimento',
            'valor_inv': 'Valor Investimento', 'moeda': 'Moeda', 'qtd': 'Quantidade', 'taxa': 'Taxa',
            'valor_tot_inv': 'Valor Total Investimento', 'valor_atual': 'Valor Atual',
            'valor_liq_mes': 'Valor Líquido Mês', 'val_mes_ant': 'Valor Mês Anterior',
            'aporte': 'Aporte', 'lucro_op': 'Lucro Operacional', 'lucro_mes': 'Lucro Mês', 'pct_rent': '% Rentabilidade'
        }, inplace=True)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Investimentos')
    output.seek(0)
    return send_file(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", as_attachment=True, download_name="Lancamentos_Investimentos.xlsx")

@app.route('/api/limpar_dados', methods=['POST'])
def api_limpar_dados():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    from database import limpar_dados_usuario
    limpar_dados_usuario(session['user_email'])
    return jsonify({'status': 'ok'})

@app.route('/api/limpar_configuracoes', methods=['POST'])
def api_limpar_configuracoes():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    data = request.json or {}
    if data.get('despesas'): clear_despesas()
    if data.get('contas'): clear_contas()
    if data.get('receitas'): clear_receitas()
    if data.get('investimentos'): clear_investimentos()
    if data.get('usuarios'): clear_usuarios()
    if data.get('tipo_imposto'): clear_tipo_imposto()
    return jsonify({'status': 'ok'})

@app.route('/api/upload_receitas', methods=['POST'])
def api_upload_receitas():
    if 'file' not in request.files: return jsonify({'error': 'Nenhum arquivo'}), 400
    file = request.files['file']
    if not file.filename.endswith(('.csv','.xls','.xlsx')): return jsonify({'error': 'Arquivo inválido'}), 400
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
    file.save(filepath)
    try:
        filename = file.filename.lower()
        df = pd.read_excel(filepath) if filename.endswith(('.xls','.xlsx')) else pd.read_csv(filepath)
        count = 0
        clear_receitas()
        df.columns = df.columns.str.strip().str.lower()
        col_desc = next((c for c in df.columns if 'descri' in c), 'descricao')
        for _, row in df.iterrows():
            val = row.get(col_desc)
            if pd.notna(val) and str(val).strip():
                add_receita(str(val).strip())
                count += 1
        os.remove(filepath)
        return jsonify({'status': 'ok', 'count': count})
    except Exception as e:
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({'error': str(e)}), 400

@app.route('/api/upload_investimentos', methods=['POST'])
def api_upload_investimentos():
    if 'file' not in request.files: return jsonify({'error': 'Nenhum arquivo'}), 400
    file = request.files['file']
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
    file.save(filepath)
    try:
        filename = file.filename.lower()
        df = pd.read_excel(filepath) if filename.endswith(('.xls','.xlsx')) else pd.read_csv(filepath)
        count = 0
        clear_investimentos()
        df.columns = df.columns.str.strip().str.lower()
        col_desc = next((c for c in df.columns if 'descri' in c), 'descricao')
        for _, row in df.iterrows():
            val = row.get(col_desc)
            if pd.notna(val) and str(val).strip():
                add_investimento(str(val).strip())
                count += 1
        os.remove(filepath)
        return jsonify({'status': 'ok', 'count': count})
    except Exception as e:
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({'error': str(e)}), 400

@app.route('/api/upload_contas', methods=['POST'])
def api_upload_contas():
    if 'file' not in request.files: return jsonify({'error': 'Nenhum arquivo'}), 400
    file = request.files['file']
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
    file.save(filepath)
    try:
        filename = file.filename.lower()
        df = pd.read_excel(filepath) if filename.endswith(('.xls','.xlsx')) else pd.read_csv(filepath)
        count = 0
        clear_contas()
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
            add_conta(g(col_desc), g(col_age), g(col_conta), g(col_acesso), g(col_senha), g(col_obs))
            count += 1
        os.remove(filepath)
        return jsonify({'status': 'ok', 'count': count})
    except Exception as e:
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({'error': str(e)}), 400

@app.route('/api/upload_usuarios', methods=['POST'])
def api_upload_usuarios():
    if 'file' not in request.files: return jsonify({'error': 'Nenhum arquivo'}), 400
    file = request.files['file']
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
    file.save(filepath)
    try:
        filename = file.filename.lower()
        df = pd.read_excel(filepath) if filename.endswith(('.xls','.xlsx')) else pd.read_csv(filepath)
        count = 0
        clear_usuarios()
        for _, row in df.iterrows():
            add_usuario(
                str(row.get('chave_usr1', row.get('Chave Usr1', ''))),
                str(row.get('chave_usr2', row.get('Chave Usr2', ''))),
                str(row.get('nome', row.get('Nome', ''))),
                int(row.get('fator_pagamento', row.get('Fator Pagamento', 1)))
            )
            count += 1
        os.remove(filepath)
        return jsonify({'status': 'ok', 'count': count})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/upload_tipo_imposto', methods=['POST'])
def api_upload_tipo_imposto():
    if 'file' not in request.files: return jsonify({'error': 'Nenhum arquivo'}), 400
    file = request.files['file']
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
    file.save(filepath)
    try:
        df = pd.read_excel(filepath) if filepath.endswith(('.xls','.xlsx')) else pd.read_csv(filepath)
        count = 0
        clear_tipo_imposto()
        for _, row in df.iterrows():
            tp = row.get('tp_imposto') if pd.notna(row.get('tp_imposto')) else row.get('Tipo Imposto')
            alq = row.get('alq_imposto') if pd.notna(row.get('alq_imposto')) else row.get('Alíquota (%)')
            pag = row.get('pagamento') if pd.notna(row.get('pagamento')) else row.get('Pagamento')
            if pd.notna(tp):
                add_tipo_imposto(str(tp), float(alq) if pd.notna(alq) else None, str(pag if pd.notna(pag) else ''))
                count += 1
        os.remove(filepath)
        return jsonify({'status': 'ok', 'count': count})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/export_receitas', methods=['GET'])
def api_export_receitas():
    receitas = get_all_receitas()
    df = pd.DataFrame(receitas)
    if not df.empty: df.drop(columns=['id'], inplace=True)
    df.rename(columns={'descricao': 'Descrição'}, inplace=True)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Receitas')
    output.seek(0)
    return send_file(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", as_attachment=True, download_name="Cadastro_Receitas.xlsx")

@app.route('/api/export_investimentos', methods=['GET'])
def api_export_investimentos():
    investimentos = get_all_investimentos()
    df = pd.DataFrame(investimentos)
    if not df.empty: df.drop(columns=['id'], inplace=True)
    df.rename(columns={'descricao': 'Descrição'}, inplace=True)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Investimentos')
    output.seek(0)
    return send_file(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", as_attachment=True, download_name="Cadastro_Investimentos.xlsx")

@app.route('/api/export_usuarios', methods=['GET'])
def api_export_usuarios():
    usuarios = get_all_usuarios()
    df = pd.DataFrame(usuarios)
    if not df.empty: df.drop(columns=['id'], inplace=True)
    df.rename(columns={'nome': 'Nome', 'chave_usr1': 'Chave Usr1', 'chave_usr2': 'Chave Usr2', 'fator_pagamento': 'Fator Pagamento'}, inplace=True)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Usuarios')
    output.seek(0)
    return send_file(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", as_attachment=True, download_name="Cadastro_Usuarios.xlsx")

@app.route('/api/export_tipo_imposto', methods=['GET'])
def api_export_tipo_imposto():
    tipos = get_all_tipo_imposto()
    df = pd.DataFrame(tipos)
    if not df.empty: df.drop(columns=['id'], inplace=True)
    df.rename(columns={'tp_imposto': 'Tipo Imposto', 'alq_imposto': 'Alíquota (%)', 'pagamento': 'Pagamento'}, inplace=True)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Tipo Imposto')
    output.seek(0)
    return send_file(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", as_attachment=True, download_name="Cadastro_Tipo_Imposto.xlsx")

@app.route('/api/export_contas', methods=['GET'])
def api_export_contas():
    contas = get_all_contas()
    df = pd.DataFrame(contas)
    if not df.empty:
        df.drop(columns=['id'], errors='ignore', inplace=True)
        df.rename(columns={
            'descricao': 'Descrição', 'agencia': 'Agência', 'conta': 'Conta',
            'dados_acesso': 'Dados Acesso', 'senha': 'Senha', 'comentarios': 'Comentários'
        }, inplace=True)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Contas')
    output.seek(0)
    return send_file(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", as_attachment=True, download_name="Cadastro_Contas.xlsx")

@app.route('/api/export_lcto_impostos', methods=['GET'])
def api_export_lcto_impostos():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    data = get_all_lcto_impostos(session['user_email'])
    df = pd.DataFrame(data)
    if not df.empty:
        df = df.drop(columns=['id', 'user_email', 'criado_em'], errors='ignore')
        df['Valor_Liquido'] = df['valor_imposto'] - df['desconto_iva']
        df.rename(columns={
            'mes_ano': 'Mês/Ano', 'tp_imposto': 'Tipo Imposto',
            'moeda_faturado': 'Moeda Faturado', 'valor_faturado': 'Valor Faturado',
            'valor_imposto': 'Valor Imposto', 'moeda_pagamento': 'Moeda Pagamento',
            'pagamento': 'Pagamento', 'pagamento_mes_ano': 'Pagamento Mês/Ano',
            'desconto_iva': 'Desconto IVA'
        }, inplace=True)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Impostos')
    output.seek(0)
    return send_file(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", as_attachment=True, download_name="Lancamentos_Impostos.xlsx")

# ── Relatórios Dinâmicos ───────────────────────────────────────────────────────
@app.route('/api/relatorio_dinamico/tabelas', methods=['GET'])
def api_relatorio_dinamico_tabelas():
    return jsonify(get_tabelas_campos())

@app.route('/api/relatorio_dinamico', methods=['GET'])
def api_get_relatorios_dinamicos():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    return jsonify(get_all_relatorios_dinamicos(session['user_email']))

@app.route('/api/relatorio_dinamico', methods=['POST'])
def api_create_relatorio_dinamico():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    data = request.json or {}
    save_relatorio_dinamico(
        session['user_email'],
        data.get('nome', 'Relatório Sem Nome'),
        data.get('tabelas', []),
        data.get('campos', []),
        data.get('agrupador', ''),
        data.get('mes_inicio', ''),
        data.get('mes_fim', ''),
        data.get('moedas', [])
    )
    return jsonify({'status': 'ok'})

@app.route('/api/relatorio_dinamico/<int:r_id>', methods=['DELETE'])
def api_delete_relatorio_dinamico(r_id):
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    delete_relatorio_dinamico(r_id)
    return jsonify({'status': 'ok'})

@app.route('/api/relatorio_dinamico/gerar', methods=['POST'])
def api_gerar_relatorio_dinamico():
    if 'user_email' not in session: 
        return jsonify({'error': 'Não logado'}), 401
    try:
        data = request.json or {}
        tabelas = data.get('tabelas', [])
        if not tabelas:
            return jsonify({'agrupadores': [], 'meses': []})
        
        resultado = get_dados_relatorio_dinamico(
            session['user_email'],
            tabelas,
            data.get('campos', []),
            data.get('agrupador', ''),
            data.get('mes_inicio', ''),
            data.get('mes_fim', ''),
            data.get('moedas', [])
        )
        return jsonify(resultado)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

@app.route('/api/relatorio_dinamico/meses', methods=['GET'])
def api_meses_disponiveis_relatorio():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    try:
        from database import get_connection
        conn = get_connection()
        rows = conn.execute(
            "SELECT DISTINCT mes_referencia FROM despesas_mensais WHERE user_email=? ORDER BY mes_referencia DESC",
            (session['user_email'],)).fetchall()
        conn.close()
        meses = [r['mes_referencia'] for r in rows]
        return jsonify(meses)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify([])

@app.route('/api/relatorio_dinamico/exportar', methods=['POST'])
def api_export_relatorio_dinamico():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    data = request.json or {}
    resultado = get_dados_relatorio_dinamico(
        session['user_email'],
        data.get('tabelas', []),
        data.get('campos', []),
        data.get('agrupador', ''),
        data.get('mes_inicio', ''),
        data.get('mes_fim', ''),
        data.get('moedas', [])
    )
    
    linhas = []
    meses = resultado.get('meses', [])
    moedas = data.get('moedas', ['EUR'])
    
    for agr in resultado.get('agrupadores', []):
        nome = agr.get('nome', '')
        dados = agr.get('dados', {})
        valores = agr.get('valores', {})
        
        for mes in meses:
            vals_mes = valores.get(mes, {})
            linha = {'Agrupador': nome, 'Mês': mes}
            linha.update(dados)
            for moeda in moedas:
                linha[f'{moeda}'] = vals_mes.get(moeda, 0)
            linhas.append(linha)
    
    df = pd.DataFrame(linhas)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Relatorio')
    output.seek(0)
    
    nomeArquivo = data.get('nome', 'Relatorio_Dinamico').replace(' ', '_') + '.xlsx'
    return send_file(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", as_attachment=True, download_name=nomeArquivo)

@app.route('/api/trader_positions', methods=['GET'])
def api_get_trader_positions():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    periodo = request.args.get('periodo')
    return jsonify(get_all_trader_positions(session['user_email'], periodo))

@app.route('/api/trader_positions', methods=['POST'])
def api_post_trader_position():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    d = request.json
    add_trader_position(session['user_email'], d.get('periodo'), d.get('conta_bancaria'), d.get('symbol'), d.get('type'), float(d.get('volume', 0) or 0), d.get('open_time'), float(d.get('open_price', 0) or 0), d.get('close_time'), float(d.get('close_price', 0) or 0), float(d.get('sl', 0) or 0), float(d.get('tp', 0) or 0), float(d.get('margin', 0) or 0), float(d.get('commission', 0) or 0), float(d.get('swap', 0) or 0), float(d.get('rollover', 0) or 0), float(d.get('gross_pl', 0) or 0))
    return jsonify({'status': 'ok'})

@app.route('/api/trader_positions/<int:t_id>', methods=['PUT'])
def api_put_trader_position(t_id):
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    d = request.json
    update_trader_position(t_id, d.get('periodo'), d.get('conta_bancaria'), d.get('symbol'), d.get('type'), float(d.get('volume', 0) or 0), d.get('open_time'), float(d.get('open_price', 0) or 0), d.get('close_time'), float(d.get('close_price', 0) or 0), float(d.get('sl', 0) or 0), float(d.get('tp', 0) or 0), float(d.get('margin', 0) or 0), float(d.get('commission', 0) or 0), float(d.get('swap', 0) or 0), float(d.get('rollover', 0) or 0), float(d.get('gross_pl', 0) or 0))
    return jsonify({'status': 'ok'})

@app.route('/api/trader_positions/<int:t_id>', methods=['DELETE'])
def api_delete_trader_position(t_id):
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    delete_trader_position(t_id)
    return jsonify({'status': 'ok'})

@app.route('/api/trader_periodos', methods=['GET'])
def api_get_trader_periodos():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    return jsonify(get_trader_periodos(session['user_email']))

@app.route('/api/trader_contas', methods=['GET'])
def api_get_trader_contas():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    return jsonify(get_trader_contas(session['user_email']))

@app.route('/api/trader_positions/clear', methods=['POST'])
def api_clear_trader_positions():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    periodo = (request.json or {}).get('periodo')
    if periodo:
        from database import get_connection
        conn = get_connection()
        conn.execute('DELETE FROM trader_positions WHERE user_email=? AND periodo=?', (session['user_email'], periodo))
        conn.commit()
        conn.close()
    else:
        clear_trader_positions()
    return jsonify({'status': 'ok'})

@app.route('/api/upload_trader_positions', methods=['POST'])
def api_upload_trader_positions():
    if 'file' not in request.files: return jsonify({'error': 'Nenhum arquivo'}), 400
    file = request.files['file']
    conta_bancaria_input = request.form.get('conta_bancaria', '')
    periodo_input = request.form.get('periodo', '')
    if not conta_bancaria_input or not periodo_input:
        return jsonify({'error': 'Conta Bancária e Período são obrigatórios'}), 400
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
    file.save(filepath)
    try:
        filename = file.filename.lower()
        df = pd.read_excel(filepath) if filename.endswith(('.xls','.xlsx')) else pd.read_csv(filepath)
        
        header_row_index = -1
        col_str = ' '.join(str(c).lower() for c in df.columns)
        if 'symbol' not in col_str or 'type' not in col_str:
            for i, row in df.iterrows():
                row_str = ' '.join(str(val).lower() for val in row.values)
                if 'symbol' in row_str and 'type' in row_str and 'volume' in row_str:
                    header_row_index = i
                    break
                    
            if header_row_index != -1:
                new_header = df.iloc[header_row_index]
                df = df[header_row_index + 1:]
                df.columns = new_header
                df.reset_index(drop=True, inplace=True)

        count = 0
        
        # Normalizar nomes das colunas para lowercase e sem espaços
        df.columns = df.columns.astype(str).str.strip().str.lower().str.replace(' ', '_').str.replace('/', '_')
        
        # Debug: mostrar as colunas encontradas
        print("Colunas encontradas:", df.columns.tolist())
        
        for _, row in df.iterrows():
            symbol = str(row.get('symbol', '')).strip() if pd.notna(row.get('symbol')) else ''
            type_ = str(row.get('type', '')).strip().title() if pd.notna(row.get('type')) else 'Buy'
            
            # Normalizar type
            if type_.lower() in ['buy', 'long', 'b']:
                type_ = 'Buy'
            elif type_.lower() in ['sell', 'short', 's']:
                type_ = 'Sell'
            
            def safe_float(val, default=0):
                if pd.isna(val) or val == '' or val is None:
                    return default
                try:
                    # Converter para string primeiro, depois para float
                    s = str(val).strip().replace(',', '').replace(' ', '').replace('\xa0', '')
                    if s == '' or s.lower() == 'nan' or s.lower() == 'none':
                        return default
                    return float(s)
                except:
                    return default
            
            def safe_str(val):
                if pd.isna(val) or val is None:
                    return ''
                return str(val).strip()
            
            def get_any(keys, default=None):
                for k in keys:
                    if k in row and pd.notna(row[k]):
                        return row[k]
                return default
            
            add_trader_position(
                session['user_email'],
                periodo_input,
                conta_bancaria_input,
                symbol,
                type_,
                safe_float(get_any(['volume'])),
                safe_str(get_any(['open_time', 'time'])),
                safe_float(get_any(['open_price', 'price'])),
                safe_str(get_any(['close_time'])),
                safe_float(get_any(['close_price'])),
                safe_float(get_any(['sl', 's___l', 's__l', 's_l'])),
                safe_float(get_any(['tp', 't___p', 't__p', 't_p'])),
                safe_float(get_any(['margin'])),
                safe_float(get_any(['commission', 'comm.', 'comm'])),
                safe_float(get_any(['swap'])),
                safe_float(get_any(['rollover'])),
                safe_float(get_any(['gross_pl', 'gross_p_l']))
            )
            count += 1
        os.remove(filepath)
        return jsonify({'status': 'ok', 'count': count})
    except Exception as e:
        if os.path.exists(filepath):
            os.remove(filepath)
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 400
        return jsonify({'error': str(e)}), 400

@app.route('/api/export_trader_positions', methods=['GET'])
def api_export_trader_positions():
    if 'user_email' not in session: return jsonify({'error': 'Não logado'}), 401
    periodo = request.args.get('periodo')
    data = get_all_trader_positions(session['user_email'], periodo)
    df = pd.DataFrame(data)
    if not df.empty:
        df = df.drop(columns=['id', 'user_email', 'criado_em'], errors='ignore')
        df.rename(columns={
            'periodo': 'Período', 'conta_bancaria': 'Conta Bancária', 'symbol': 'Symbol',
            'type': 'Type', 'volume': 'Volume', 'open_time': 'Open Time', 'open_price': 'Open Price',
            'close_time': 'Close Time', 'close_price': 'Close Price', 'sl': 'SL', 'tp': 'TP',
            'margin': 'Margin', 'commission': 'Commission', 'swap': 'Swap', 'rollover': 'Rollover',
            'gross_pl': 'Gross P/L'
        }, inplace=True)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Trader Positions')
    output.seek(0)
    return send_file(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", as_attachment=True, download_name="Trader_Positions.xlsx")

if __name__ == '__main__':
    app.run(debug=True, port=5001)
