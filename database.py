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
    try:
        c.execute('INSERT INTO users (email, password_hash) VALUES (?, ?)', 
                  (email.lower().strip(), generate_password_hash(password, method='pbkdf2:sha256')))
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

# Inicializa o banco ao importar
init_db()
