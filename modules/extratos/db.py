from db.connection import get_connection


def init_tables():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS categorias_aprendidas (
            id SERIAL PRIMARY KEY,
            padrao_descricao TEXT UNIQUE NOT NULL,
            categoria TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()


def save_category_rule(description: str, category: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO categorias_aprendidas (padrao_descricao, categoria)
        VALUES (%s, %s)
        ON CONFLICT (padrao_descricao) DO UPDATE SET categoria = EXCLUDED.categoria
    ''', (description.lower().strip(), category))
    conn.commit()
    conn.close()


def guess_category(description: str) -> str:
    conn = get_connection()
    c = conn.cursor()

    desc_lower = description.lower().strip()
    c.execute('SELECT categoria FROM categorias_aprendidas WHERE padrao_descricao = %s', (desc_lower,))
    row = c.fetchone()
    if row:
        conn.close()
        return row['categoria']

    c.execute('SELECT padrao_descricao, categoria FROM categorias_aprendidas')
    all_rules = c.fetchall()
    conn.close()

    for rule in all_rules:
        if rule['padrao_descricao'] in desc_lower:
            return rule['categoria']

    return 'Não Categorizado'
