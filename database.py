import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'extratos.db')

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS categorias_aprendidas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            padrao_descricao TEXT UNIQUE NOT NULL,
            categoria TEXT NOT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS cad_despesas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            despesa TEXT NOT NULL,
            tipo_despesa TEXT,
            fator_divisao INTEGER,
            prioridade TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS cad_contas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            descricao TEXT NOT NULL,
            agencia TEXT,
            conta TEXT,
            dados_acesso TEXT,
            senha TEXT,
            comentarios TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS cad_receitas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            descricao TEXT NOT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS cad_investimentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            descricao TEXT NOT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS cad_usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chave_usr1 TEXT,
            chave_usr2 TEXT,
            nome TEXT NOT NULL,
            fator_pagamento INTEGER DEFAULT 1
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS despesas_mensais (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT,
            data TEXT,
            descricao TEXT,
            valor_original REAL,
            moeda TEXT,
            cambio_eur REAL,
            valor_eur REAL,
            usr1 TEXT,
            usr2 TEXT,
            diferenca_original REAL,
            status_pago TEXT DEFAULT 'Pendente',
            categoria_final TEXT,
            receita INTEGER DEFAULT 0,
            comentarios TEXT,
            conta_bancaria TEXT,
            mes_referencia TEXT,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS despesas_anuais (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT,
            ano INTEGER,
            categoria_final TEXT,
            total_usr1 REAL DEFAULT 0,
            total_usr2 REAL DEFAULT 0,
            total_geral REAL DEFAULT 0,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS receitas_mensais (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT,
            data TEXT,
            tipo_receita TEXT,
            valor_original REAL,
            moeda_original TEXT,
            cotacao REAL DEFAULT 1,
            valor_eur REAL,
            valor_brl REAL,
            conta_bancaria TEXT,
            mes_referencia TEXT,
            despesa_mensal_id INTEGER,
            comentarios TEXT,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS tb_tipo_imposto (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tp_imposto TEXT NOT NULL,
            alq_imposto REAL,
            pagamento TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS lcto_impostos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT,
            mes_ano TEXT NOT NULL,
            tp_imposto TEXT,
            moeda_faturado TEXT DEFAULT 'EUR',
            valor_faturado REAL DEFAULT 0,
            valor_imposto REAL DEFAULT 0,
            moeda_pagamento TEXT DEFAULT 'EUR',
            pagamento TEXT,
            pagamento_mes_ano TEXT,
            desconto_iva REAL DEFAULT 0,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    
    # Verificar e adicionar coluna pagamento_mes_ano se não existir
    try:
        c.execute("SELECT pagamento_mes_ano FROM lcto_impostos LIMIT 1")
    except:
        c.execute("ALTER TABLE lcto_impostos ADD COLUMN pagamento_mes_ano TEXT")
        conn.commit()
    
    conn.close()

def save_category_rule(description: str, category: str):
    """Salva uma regra de negócio baseado na string literal exata (ou lowercase)"""
    conn = get_connection()
    c = conn.cursor()
    # Usa REPLACE para atualizar se o padrão já existir
    c.execute('''
        INSERT OR REPLACE INTO categorias_aprendidas (padrao_descricao, categoria)
        VALUES (?, ?)
    ''', (description.lower().strip(), category))
    conn.commit()
    conn.close()

def guess_category(description: str) -> str:
    """Tenta descobrir a categoria baseada na base de dados"""
    conn = get_connection()
    c = conn.cursor()
    
    desc_lower = description.lower().strip()
    # Match exato primeiro
    c.execute('SELECT categoria FROM categorias_aprendidas WHERE padrao_descricao = ?', (desc_lower,))
    row = c.fetchone()
    if row:
        conn.close()
        return row['categoria']
        
    # Match parcial "LIKE" se não achar exato (poderia ser perigoso com descrições curtas, mas vamos tentar)
    c.execute('SELECT padrao_descricao, categoria FROM categorias_aprendidas')
    all_rules = c.fetchall()
    conn.close()
    
    for rule in all_rules:
        # Se a regra estiver dentro da descrição atual (ex: PGTO UBER -> regra 'uber')
        if rule['padrao_descricao'] in desc_lower:
            return rule['categoria']

    return "Não Categorizado"

from werkzeug.security import generate_password_hash, check_password_hash

def register_user(email: str, password: str) -> bool:
    conn = get_connection()
    c = conn.cursor()
    email_lower = email.lower().strip()
    try:
        c.execute('DELETE FROM despesas_mensais WHERE user_email = ?', (email_lower,))
        c.execute('DELETE FROM despesas_anuais WHERE user_email = ?', (email_lower,))
        c.execute('DELETE FROM receitas_mensais WHERE user_email = ?', (email_lower,))
        c.execute('DELETE FROM lcto_impostos WHERE user_email = ?', (email_lower,))
        c.execute('INSERT INTO users (email, password_hash) VALUES (?, ?)', 
                  (email_lower, generate_password_hash(password, method='pbkdf2:sha256')))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def verify_user(email: str, password: str) -> bool:
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT password_hash FROM users WHERE email = ?', (email.lower().strip(),))
    row = c.fetchone()
    conn.close()
    if row and check_password_hash(row['password_hash'], password):
        return True
    return False

def get_user_by_email(email: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT id, email FROM users WHERE email = ?', (email.lower().strip(),))
    row = c.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def get_all_despesas():
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM cad_despesas ORDER BY id DESC')
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def add_despesa(despesa, tipo_despesa, fator_divisao, prioridade):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO cad_despesas (despesa, tipo_despesa, fator_divisao, prioridade)
        VALUES (?, ?, ?, ?)
    ''', (despesa, tipo_despesa, fator_divisao, prioridade))
    conn.commit()
    conn.close()

def update_despesa(d_id, despesa, tipo_despesa, fator_divisao, prioridade):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        UPDATE cad_despesas 
        SET despesa=?, tipo_despesa=?, fator_divisao=?, prioridade=?
        WHERE id=?
    ''', (despesa, tipo_despesa, fator_divisao, prioridade, d_id))
    conn.commit()
    conn.close()

def overwrite_despesas(despesas_list):
    conn = get_connection()
    c = conn.cursor()
    c.execute('DELETE FROM cad_despesas')
    for d in despesas_list:
        c.execute('''
            INSERT INTO cad_despesas (despesa, tipo_despesa, fator_divisao, prioridade)
            VALUES (?, ?, ?, ?)
        ''', (d.get('despesa'), d.get('tipo_despesa'), d.get('fator_divisao'), d.get('prioridade')))
    conn.commit()
    conn.close()

def init_lcto_emprestimos():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS lcto_emprestimos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT,
            tipo TEXT NOT NULL,
            beneficiario TEXT,
            valor_operacao REAL NOT NULL,
            moeda_emp TEXT DEFAULT 'BRL',
            data_emprestimo TEXT,
            data_operacao TEXT,
            obs TEXT,
            status TEXT DEFAULT 'Ativo',
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def migrate_lcto_emprestimos_moeda():
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT moeda_emp FROM lcto_emprestimos LIMIT 1")
    except:
        c.execute("ALTER TABLE lcto_emprestimos ADD COLUMN moeda_emp TEXT DEFAULT 'BRL'")
        conn.commit()
    conn.close()

# Inicializa o banco ao importar
init_db()
init_lcto_emprestimos()
migrate_lcto_emprestimos_moeda()

# ── Contas Bancárias ───────────────────────────────────────────────────────────
def get_all_contas():
    conn = get_connection()
    rows = conn.execute('SELECT * FROM cad_contas ORDER BY id DESC').fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_conta(descricao, agencia, conta, dados_acesso, senha, comentarios):
    conn = get_connection()
    conn.execute('INSERT INTO cad_contas (descricao, agencia, conta, dados_acesso, senha, comentarios) VALUES (?,?,?,?,?,?)',
                 (descricao, agencia, conta, dados_acesso, senha, comentarios))
    conn.commit(); conn.close()

def update_conta(c_id, descricao, agencia, conta, dados_acesso, senha, comentarios):
    conn = get_connection()
    conn.execute('UPDATE cad_contas SET descricao=?, agencia=?, conta=?, dados_acesso=?, senha=?, comentarios=? WHERE id=?',
                 (descricao, agencia, conta, dados_acesso, senha, comentarios, c_id))
    conn.commit(); conn.close()

def delete_conta(c_id):
    conn = get_connection()
    conn.execute('DELETE FROM cad_contas WHERE id=?', (c_id,))
    conn.commit(); conn.close()

def clear_contas():
    conn = get_connection()
    conn.execute('DELETE FROM cad_contas')
    conn.commit(); conn.close()

def get_senha_conta(c_id):
    conn = get_connection()
    row = conn.execute('SELECT senha FROM cad_contas WHERE id=?', (c_id,)).fetchone()
    conn.close()
    return row['senha'] if row else ''

# ── Despesas (delete) ─────────────────────────────────────────────────────────
def delete_despesa(d_id):
    conn = get_connection()
    conn.execute('DELETE FROM cad_despesas WHERE id=?', (d_id,))
    conn.commit(); conn.close()

# ── Usuários ──────────────────────────────────────────────────────────────────
def get_all_usuarios():
    conn = get_connection()
    rows = conn.execute('SELECT * FROM cad_usuarios ORDER BY id DESC').fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_usuario(chave_usr1, chave_usr2, nome, fator_pagamento):
    conn = get_connection()
    conn.execute('INSERT INTO cad_usuarios (chave_usr1, chave_usr2, nome, fator_pagamento) VALUES (?,?,?,?)',
                 (chave_usr1, chave_usr2, nome, fator_pagamento))
    conn.commit(); conn.close()

def update_usuario(u_id, chave_usr1, chave_usr2, nome, fator_pagamento):
    conn = get_connection()
    conn.execute('UPDATE cad_usuarios SET chave_usr1=?, chave_usr2=?, nome=?, fator_pagamento=? WHERE id=?',
                 (chave_usr1, chave_usr2, nome, fator_pagamento, u_id))
    conn.commit(); conn.close()

def delete_usuario(u_id):
    conn = get_connection()
    conn.execute('DELETE FROM cad_usuarios WHERE id=?', (u_id,))
    conn.commit(); conn.close()

def clear_usuarios():
    conn = get_connection()
    conn.execute('DELETE FROM cad_usuarios')
    conn.commit(); conn.close()

# ── Despesas Mensais ───────────────────────────────────────────────────────────────
def get_despesas_mensais(user_email, mes=None):
    conn = get_connection()
    if mes:
        rows = conn.execute(
            'SELECT * FROM despesas_mensais WHERE user_email=? AND mes_referencia=? ORDER BY data, id',
            (user_email, mes)).fetchall()
    else:
        rows = conn.execute(
            'SELECT * FROM despesas_mensais WHERE user_email=? ORDER BY mes_referencia DESC, data, id',
            (user_email,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def save_despesas_mensais_batch(user_email, rows_list):
    """Salva um lote de transações do extrato como despesas mensais.
    Sobrescreve apenas o mês_referencia fornecido."""
    if not rows_list: return 0
    mes = rows_list[0].get('mes_referencia', '')
    conn = get_connection()
    # Remove apenas as do mês
    conn.execute('DELETE FROM despesas_mensais WHERE user_email=? AND mes_referencia=?', (user_email, mes))
    for r in rows_list:
        conn.execute('''
            INSERT INTO despesas_mensais 
            (user_email, data, descricao, valor_original, moeda, cambio_eur, valor_eur,
             usr1, usr2, diferenca_original, status_pago, categoria_final, receita, 
             comentarios, conta_bancaria, mes_referencia)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            user_email,
            r.get('data'), r.get('descricao'), r.get('valor_original'),
            r.get('moeda'), r.get('cambio_eur'), r.get('valor_eur'),
            r.get('usr1', 0), r.get('usr2', 0), r.get('diferenca_original'),
            r.get('status_pago', 'Pendente'), r.get('categoria_final'),
            1 if r.get('receita') else 0,
            r.get('comentarios'), r.get('conta_bancaria'), mes
        ))
    conn.commit()
    conn.close()
    return len(rows_list)

def add_despesa_mensal(user_email, row):
    conn = get_connection()
    conn.execute('''
        INSERT INTO despesas_mensais 
        (user_email, data, descricao, valor_original, moeda, cambio_eur, valor_eur,
         usr1, usr2, diferenca_original, status_pago, categoria_final, receita, 
         comentarios, conta_bancaria, mes_referencia)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ''', (
        user_email,
        row.get('data'), row.get('descricao'), row.get('valor_original'),
        row.get('moeda'), row.get('cambio_eur'), row.get('valor_eur'),
        row.get('usr1', 0), row.get('usr2', 0), row.get('diferenca_original'),
        row.get('status_pago', 'Pendente'), row.get('categoria_final'),
        1 if row.get('receita') else 0,
        row.get('comentarios'), row.get('conta_bancaria'), row.get('mes_referencia')
    ))
    conn.commit()
    conn.close()

def update_despesa_mensal(d_id, row):
    conn = get_connection()
    conn.execute('''
        UPDATE despesas_mensais SET
        data=?, descricao=?, valor_original=?, moeda=?, cambio_eur=?, valor_eur=?,
        usr1=?, usr2=?, diferenca_original=?, status_pago=?, categoria_final=?,
        receita=?, comentarios=?, conta_bancaria=?, mes_referencia=?
        WHERE id=?
    ''', (
        row.get('data'), row.get('descricao'), row.get('valor_original'),
        row.get('moeda'), row.get('cambio_eur'), row.get('valor_eur'),
        row.get('usr1', 0), row.get('usr2', 0), row.get('diferenca_original'),
        row.get('status_pago', 'Pendente'), row.get('categoria_final'),
        1 if row.get('receita') else 0,
        row.get('comentarios'), row.get('conta_bancaria'), row.get('mes_referencia'),
        d_id
    ))
    conn.commit()
    conn.close()

def delete_despesa_mensal(d_id):
    conn = get_connection()
    conn.execute('DELETE FROM despesas_mensais WHERE id=?', (d_id,))
    conn.commit()
    conn.close()

def consolidar_despesas_anuais(user_email, ano):
    """Consolida despesas mensais do ano em despesas_anuais (substitui se já existir)."""
    conn = get_connection()
    # Busca agrupado por categoria
    rows = conn.execute('''
        SELECT categoria_final, SUM(usr1) as total_usr1, SUM(usr2) as total_usr2,
               SUM(usr1)+SUM(usr2) as total_geral
        FROM despesas_mensais
        WHERE user_email=? AND substr(mes_referencia,1,4)=?
        GROUP BY categoria_final
    ''', (user_email, str(ano))).fetchall()
    # Deleta ano existente
    conn.execute('DELETE FROM despesas_anuais WHERE user_email=? AND ano=?', (user_email, ano))
    for r in rows:
        conn.execute('''
            INSERT INTO despesas_anuais (user_email, ano, categoria_final, total_usr1, total_usr2, total_geral)
            VALUES (?,?,?,?,?,?)
        ''', (user_email, ano, r['categoria_final'], r['total_usr1'], r['total_usr2'], r['total_geral']))
    conn.commit()
    conn.close()
    return len(rows)

# ── Receitas Mensais ───────────────────────────────────────────────────────────────
def get_receitas_mensais(user_email, mes=None):
    conn = get_connection()
    if mes:
        rows = conn.execute(
            'SELECT * FROM receitas_mensais WHERE user_email=? AND mes_referencia=? ORDER BY data, id',
            (user_email, mes)).fetchall()
    else:
        rows = conn.execute(
            'SELECT * FROM receitas_mensais WHERE user_email=? ORDER BY mes_referencia DESC, data, id',
            (user_email,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_receita_mensal(user_email, row):
    conn = get_connection()
    conn.execute('''
        INSERT INTO receitas_mensais 
        (user_email, data, tipo_receita, valor_original, moeda_original, cotacao, valor_eur, valor_brl,
         conta_bancaria, mes_referencia, despesa_mensal_id, comentarios)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    ''', (
        user_email,
        row.get('data'), row.get('tipo_receita'), row.get('valor_original'),
        row.get('moeda_original'), row.get('cotacao', 1), row.get('valor_eur'),
        row.get('valor_brl'), row.get('conta_bancaria'), row.get('mes_referencia'),
        row.get('despesa_mensal_id'), row.get('comentarios')
    ))
    conn.commit()
    conn.close()

def update_receita_mensal(r_id, row):
    conn = get_connection()
    conn.execute('''
        UPDATE receitas_mensais SET
        data=?, tipo_receita=?, valor_original=?, moeda_original=?, cotacao=?, valor_eur=?, valor_brl=?,
        conta_bancaria=?, mes_referencia=?, comentarios=?
        WHERE id=?
    ''', (
        row.get('data'), row.get('tipo_receita'), row.get('valor_original'),
        row.get('moeda_original'), row.get('cotacao', 1), row.get('valor_eur'),
        row.get('valor_brl'), row.get('conta_bancaria'), row.get('mes_referencia'),
        row.get('comentarios'), r_id
    ))
    conn.commit()
    conn.close()

def delete_receita_mensal(r_id):
    conn = get_connection()
    conn.execute('DELETE FROM receitas_mensais WHERE id=?', (r_id,))
    conn.commit()
    conn.close()

def sync_receitas_from_despesas_mensais(user_email, mes):
    conn = get_connection()
    conn.execute(
        'DELETE FROM receitas_mensais WHERE user_email=? AND mes_referencia=? AND despesa_mensal_id IS NOT NULL',
        (user_email, mes)
    )
    rows = conn.execute('''
        SELECT * FROM despesas_mensais WHERE user_email=? AND mes_referencia=? AND receita=1
    ''', (user_email, mes)).fetchall()
    
    for r in rows:
        conn.execute('''
            INSERT INTO receitas_mensais 
            (user_email, data, tipo_receita, valor_original, moeda_original, cotacao, valor_eur, valor_brl,
             conta_bancaria, mes_referencia, despesa_mensal_id, comentarios)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            user_email, r['data'], r['categoria_final'], r['valor_original'],
            r['moeda'], r['cambio_eur'], r['valor_eur'],
            r['valor_original'], r['conta_bancaria'], r['mes_referencia'],
            r['id'], r['comentarios']
        ))
    conn.commit()
    conn.close()
    return len(rows)

def get_totais_receitas(user_email, mes):
    conn = get_connection()
    row = conn.execute('''
        SELECT SUM(valor_eur) as total_eur, SUM(valor_brl) as total_brl
        FROM receitas_mensais WHERE user_email=? AND mes_referencia=?
    ''', (user_email, mes)).fetchone()
    conn.close()
    return {'total_eur': row['total_eur'] or 0, 'total_brl': row['total_brl'] or 0}

# ── Receitas (cadastro) ────────────────────────────────────────────────────────────
def get_all_receitas():
    conn = get_connection()
    rows = conn.execute('SELECT * FROM cad_receitas ORDER BY id DESC').fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_receita(descricao):
    conn = get_connection()
    conn.execute('INSERT INTO cad_receitas (descricao) VALUES (?)', (descricao,))
    conn.commit(); conn.close()

def update_receita(r_id, descricao):
    conn = get_connection()
    conn.execute('UPDATE cad_receitas SET descricao=? WHERE id=?', (descricao, r_id))
    conn.commit(); conn.close()

def delete_receita(r_id):
    conn = get_connection()
    conn.execute('DELETE FROM cad_receitas WHERE id=?', (r_id,))
    conn.commit(); conn.close()

def clear_receitas():
    conn = get_connection()
    conn.execute('DELETE FROM cad_receitas')
    conn.commit(); conn.close()

# ── Investimentos ───────────────────────────────────────────────────────────────
def get_all_investimentos():
    conn = get_connection()
    rows = conn.execute('SELECT * FROM cad_investimentos ORDER BY id DESC').fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_investimento(descricao):
    conn = get_connection()
    conn.execute('INSERT INTO cad_investimentos (descricao) VALUES (?)', (descricao,))
    conn.commit(); conn.close()

def update_investimento(i_id, descricao):
    conn = get_connection()
    conn.execute('UPDATE cad_investimentos SET descricao=? WHERE id=?', (descricao, i_id))
    conn.commit(); conn.close()

def delete_investimento(i_id):
    conn = get_connection()
    conn.execute('DELETE FROM cad_investimentos WHERE id=?', (i_id,))
    conn.commit(); conn.close()

def clear_investimentos():
    conn = get_connection()
    conn.execute('DELETE FROM cad_investimentos')
    conn.commit(); conn.close()

def get_dashboard_data(user_email: str, mes_referencia: str):
    """Retorna dados agregados para o Dashboard (Categorias, Receitas, Patrimônio)"""
    conn = get_connection()
    c = conn.cursor()
    
    # 1. Somatório por Categorias Mensais (Despesas)
    c.execute('''
        SELECT categoria_final, SUM(valor_eur) as total
        FROM despesas_mensais
        WHERE user_email = ? AND mes_referencia = ? AND receita = 0
        GROUP BY categoria_final
    ''', (user_email, mes_referencia))
    exp_by_cat = [dict(row) for row in c.fetchall()]
    
    # 2. Somatório de Receitas Mensais
    c.execute('''
        SELECT categoria_final, SUM(valor_eur) as total
        FROM despesas_mensais
        WHERE user_email = ? AND mes_referencia = ? AND receita = 1
        GROUP BY categoria_final
    ''', (user_email, mes_referencia))
    rec_by_cat = [dict(row) for row in c.fetchall()]
    
    # 3. Patrimônio Anual (Saldo Acumulado no Ano)
    ano = mes_referencia.split('-')[0]
    c.execute('''
        SELECT 
            SUM(CASE WHEN receita = 1 THEN valor_eur ELSE 0 END) as total_rec,
            SUM(CASE WHEN receita = 0 THEN valor_eur ELSE 0 END) as total_exp
        FROM despesas_mensais
        WHERE user_email = ? AND mes_referencia LIKE ?
    ''', (user_email, f"{ano}-%"))
    row = c.fetchone()
    annual_net = (row['total_rec'] or 0) - (row['total_exp'] or 0)
    
    conn.close()
    return {
        'expenses_by_category': exp_by_cat,
        'revenues_by_category': rec_by_cat,
        'annual_net': annual_net,
        'ano': ano,
        'mes': mes_referencia
    }

def get_annual_report(user_email: str, ano: int):
    """Retorna dados consolidados da tabela despesas_anuais"""
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        SELECT categoria_final, total_usr1, total_usr2, total_geral
        FROM despesas_anuais
        WHERE user_email = ? AND ano = ?
        ORDER BY total_geral DESC
    ''', (user_email, ano))
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return rows

def get_all_tipo_imposto():
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM tb_tipo_imposto ORDER BY tp_imposto')
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return rows

def add_tipo_imposto(tp_imposto: str, alq_imposto: float, pagamento: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute('INSERT INTO tb_tipo_imposto (tp_imposto, alq_imposto, pagamento) VALUES (?, ?, ?)',
              (tp_imposto, alq_imposto, pagamento))
    conn.commit()
    conn.close()

def update_tipo_imposto(id: int, tp_imposto: str, alq_imposto: float, pagamento: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute('UPDATE tb_tipo_imposto SET tp_imposto=?, alq_imposto=?, pagamento=? WHERE id=?',
              (tp_imposto, alq_imposto, pagamento, id))
    conn.commit()
    conn.close()

def delete_tipo_imposto(id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute('DELETE FROM tb_tipo_imposto WHERE id=?', (id,))
    conn.commit()
    conn.close()

def clear_tipo_imposto():
    conn = get_connection()
    c = conn.cursor()
    c.execute('DELETE FROM tb_tipo_imposto')
    conn.commit()
    conn.close()

def get_all_lcto_impostos(user_email: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM lcto_impostos WHERE user_email=? ORDER BY mes_ano DESC, tp_imposto', (user_email,))
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return rows

def add_lcto_imposto(user_email: str, mes_ano: str, tp_imposto: str, moeda_faturado: str, valor_faturado: float, valor_imposto: float, moeda_pagamento: str, pagamento: str, pagamento_mes_ano: str, desconto_iva: float):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''INSERT INTO lcto_impostos (user_email, mes_ano, tp_imposto, moeda_faturado, valor_faturado, valor_imposto, moeda_pagamento, pagamento, pagamento_mes_ano, desconto_iva)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (user_email, mes_ano, tp_imposto, moeda_faturado, valor_faturado, valor_imposto, moeda_pagamento, pagamento, pagamento_mes_ano, desconto_iva))
    conn.commit()
    conn.close()

def update_lcto_imposto(id: int, mes_ano: str, tp_imposto: str, moeda_faturado: str, valor_faturado: float, valor_imposto: float, moeda_pagamento: str, pagamento: str, pagamento_mes_ano: str, desconto_iva: float):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''UPDATE lcto_impostos SET mes_ano=?, tp_imposto=?, moeda_faturado=?, valor_faturado=?, valor_imposto=?, moeda_pagamento=?, pagamento=?, pagamento_mes_ano=?, desconto_iva=? WHERE id=?''',
              (mes_ano, tp_imposto, moeda_faturado, valor_faturado, valor_imposto, moeda_pagamento, pagamento, pagamento_mes_ano, desconto_iva, id))
    conn.commit()
    conn.close()

def delete_lcto_imposto(id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute('DELETE FROM lcto_impostos WHERE id=?', (id,))
    conn.commit()
    conn.close()

def init_lcto_emprestimos():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS lcto_emprestimos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT,
            tipo TEXT NOT NULL,
            beneficiario TEXT,
            valor_operacao REAL NOT NULL,
            data_emprestimo TEXT,
            data_operacao TEXT,
            obs TEXT,
            status TEXT DEFAULT 'Ativo',
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def get_all_lcto_emprestimos(user_email: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM lcto_emprestimos WHERE user_email=? ORDER BY data_operacao DESC, id DESC', (user_email,))
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return rows

def add_lcto_emprestimo(user_email: str, tipo: str, beneficiario: str, valor_operacao: float, moeda_emp: str, data_emprestimo: str, data_operacao: str, obs: str, status: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''INSERT INTO lcto_emprestimos (user_email, tipo, beneficiario, valor_operacao, moeda_emp, data_emprestimo, data_operacao, obs, status)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (user_email, tipo, beneficiario, valor_operacao, moeda_emp, data_emprestimo, data_operacao, obs, status))
    conn.commit()
    conn.close()

def update_lcto_emprestimo(id: int, tipo: str, beneficiario: str, valor_operacao: float, moeda_emp: str, data_emprestimo: str, data_operacao: str, obs: str, status: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''UPDATE lcto_emprestimos SET tipo=?, beneficiario=?, valor_operacao=?, moeda_emp=?, data_emprestimo=?, data_operacao=?, obs=?, status=? WHERE id=?''',
              (tipo, beneficiario, valor_operacao, moeda_emp, data_emprestimo, data_operacao, obs, status, id))
    conn.commit()
    conn.close()

def delete_lcto_emprestimo(id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute('DELETE FROM lcto_emprestimos WHERE id=?', (id,))
    conn.commit()
    conn.close()

def get_saldo_emprestimos(user_email: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        SELECT 
            SUM(CASE WHEN tipo = 'Empréstimo' THEN valor_operacao ELSE 0 END) as total_emprestado,
            SUM(CASE WHEN tipo IN ('Pagamento', 'Abatimento') THEN valor_operacao ELSE 0 END) as total_pago
        FROM lcto_emprestimos
        WHERE user_email = ?
    ''', (user_email,))
    row = c.fetchone()
    conn.close()
    total_emprestado = row['total_emprestado'] or 0
    total_pago = row['total_pago'] or 0
    saldo = total_emprestado - total_pago
    return {'total_emprestado': total_emprestado, 'total_pago': total_pago, 'saldo': saldo}

def limpar_dados_usuario(email: str):
    conn = get_connection()
    c = conn.cursor()
    email_lower = email.lower().strip()
    c.execute('DELETE FROM despesas_mensais WHERE user_email = ?', (email_lower,))
    c.execute('DELETE FROM despesas_anuais WHERE user_email = ?', (email_lower,))
    c.execute('DELETE FROM receitas_mensais WHERE user_email = ?', (email_lower,))
    c.execute('DELETE FROM lcto_impostos WHERE user_email = ?', (email_lower,))
    c.execute('DELETE FROM lcto_emprestimos WHERE user_email = ?', (email_lower,))
    c.execute('DELETE FROM categorias_aprendidas')
    conn.commit()
    conn.close()

def get_dashboard_impostos(user_email: str):
    """Retorna dados para o Dashboard de Impostos agrupados por tipo e pagamento"""
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        SELECT 
            tp_imposto,
            pagamento,
            SUM(valor_imposto) as total_imposto,
            SUM(desconto_iva) as total_desconto,
            SUM(valor_imposto - COALESCE(desconto_iva, 0)) as valor_liquido,
            pagamento_mes_ano
        FROM lcto_impostos
        WHERE user_email = ?
        GROUP BY tp_imposto, pagamento, pagamento_mes_ano
        ORDER BY tp_imposto, pagamento_mes_ano DESC
    ''', (user_email,))
    rows = [dict(row) for row in c.fetchall()]
    
    tipo_imposto_map = {}
    for r in rows:
        tp = r['tp_imposto'] or 'Não especificado'
        pag = r['pagamento'] or 'Não especificado'
        key = f"{tp}|{pag}"
        if key not in tipo_imposto_map:
            tipo_imposto_map[key] = {'tp_imposto': tp, 'pagamento': pag, 'total_imposto': 0, 'total_desconto': 0, 'valor_liquido': 0, 'periodos': []}
        tipo_imposto_map[key]['total_imposto'] += r['total_imposto'] or 0
        tipo_imposto_map[key]['total_desconto'] += r['total_desconto'] or 0
        tipo_imposto_map[key]['valor_liquido'] += r['valor_liquido'] or 0
        if r['pagamento_mes_ano']:
            tipo_imposto_map[key]['periodos'].append(r['pagamento_mes_ano'])
    
    conn.close()
    return list(tipo_imposto_map.values())

# ── Lançamento de Investimentos ─────────────────────────────────────────────────────
def init_lcto_investimentos():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS lcto_investimentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT,
            banco TEXT,
            tp_investimento TEXT,
            data_inv TEXT,
            valor_inv REAL,
            moeda TEXT DEFAULT 'BRL',
            qtd REAL,
            taxa REAL,
            valor_atual REAL,
            val_mes_ant REAL,
            aporte REAL,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_lcto_investimentos()

def get_all_lcto_investimentos(user_email: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM lcto_investimentos WHERE user_email=? ORDER BY data_inv DESC, id DESC', (user_email,))
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    for r in rows:
        r['valor_tot_inv'] = (r.get('valor_inv') or 0) * (r.get('qtd') or 0)
        taxa = r.get('taxa') or 0
        r['valor_liq_mes'] = (r.get('valor_atual') or 0) - (r['valor_tot_inv'] + taxa)
        val_mes_ant = r.get('val_mes_ant') or 0
        r['lucro_mes'] = (r.get('valor_atual') or 0) - val_mes_ant
        r['lucro_op'] = (r.get('valor_atual') or 0) - r['valor_tot_inv']
        r['pct_rent'] = (r['lucro_op'] / r['valor_tot_inv'] * 100) if r['valor_tot_inv'] > 0 else 0
    return rows

def add_lcto_investimento(user_email: str, banco: str, tp_investimento: str, data_inv: str, valor_inv: float, moeda: str, qtd: float, taxa: float, valor_atual: float, val_mes_ant: float, aporte: float):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''INSERT INTO lcto_investimentos 
        (user_email, banco, tp_investimento, data_inv, valor_inv, moeda, qtd, taxa, valor_atual, val_mes_ant, aporte)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (user_email, banco, tp_investimento, data_inv, valor_inv, moeda, qtd, taxa, valor_atual, val_mes_ant, aporte))
    conn.commit()
    conn.close()

def update_lcto_investimento(id: int, banco: str, tp_investimento: str, data_inv: str, valor_inv: float, moeda: str, qtd: float, taxa: float, valor_atual: float, val_mes_ant: float, aporte: float):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''UPDATE lcto_investimentos SET 
        banco=?, tp_investimento=?, data_inv=?, valor_inv=?, moeda=?, qtd=?, taxa=?, valor_atual=?, val_mes_ant=?, aporte=?
        WHERE id=?''',
        (banco, tp_investimento, data_inv, valor_inv, moeda, qtd, taxa, valor_atual, val_mes_ant, aporte, id))
    conn.commit()
    conn.close()

def delete_lcto_investimento(id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute('DELETE FROM lcto_investimentos WHERE id=?', (id,))
    conn.commit()
    conn.close()

def clear_lcto_investimentos():
    conn = get_connection()
    c = conn.cursor()
    c.execute('DELETE FROM lcto_investimentos')
    conn.commit()
    conn.close()
