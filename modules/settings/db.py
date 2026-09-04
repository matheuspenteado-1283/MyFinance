from db.connection import get_connection

# Moedas cobertas pela Frankfurter API (conjunto usado para popular selects no frontend).
MOEDAS_SUPORTADAS = sorted({
    'EUR', 'USD', 'BRL', 'GBP', 'JPY', 'CHF', 'CAD', 'AUD', 'CNY', 'ARS',
    'MXN', 'SEK', 'NOK', 'DKK', 'PLN', 'CZK', 'HUF', 'ZAR', 'SGD',
})


def init_tables():
    conn = get_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS user_settings (
            user_email TEXT PRIMARY KEY,
            moeda_base TEXT NOT NULL DEFAULT 'EUR',
            atualizado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()


def get_moeda_base(user_email: str) -> str:
    conn = get_connection()
    row = conn.execute(
        'SELECT moeda_base FROM user_settings WHERE user_email=%s', (user_email,)
    ).fetchone()
    conn.close()
    return row['moeda_base'] if row else 'EUR'


def set_moeda_base(user_email: str, moeda: str):
    conn = get_connection()
    conn.execute('''
        INSERT INTO user_settings (user_email, moeda_base, atualizado_em)
        VALUES (%s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (user_email) DO UPDATE SET
            moeda_base = EXCLUDED.moeda_base, atualizado_em = EXCLUDED.atualizado_em
    ''', (user_email, moeda))
    conn.commit()
    conn.close()
