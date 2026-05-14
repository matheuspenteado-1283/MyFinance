from db.connection import get_connection


def init_tables():
    conn = get_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS trader_positions (
            id SERIAL PRIMARY KEY,
            user_email TEXT,
            periodo TEXT,
            conta_bancaria TEXT,
            symbol TEXT,
            type TEXT,
            volume REAL,
            open_time TEXT,
            open_price REAL,
            close_time TEXT,
            close_price REAL,
            sl REAL,
            tp REAL,
            margin REAL,
            commission REAL,
            swap REAL,
            rollover REAL,
            gross_pl REAL,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()


def get_all_trader_positions(user_email: str, periodo: str = None):
    conn = get_connection()
    if periodo:
        rows = conn.execute(
            'SELECT * FROM trader_positions WHERE user_email=%s AND periodo=%s ORDER BY open_time DESC, id DESC',
            (user_email, periodo),
        ).fetchall()
    else:
        rows = conn.execute(
            'SELECT * FROM trader_positions WHERE user_email=%s ORDER BY periodo DESC, open_time DESC, id DESC',
            (user_email,),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_trader_position(user_email, periodo, conta_bancaria, symbol, type_, volume,
                        open_time, open_price, close_time, close_price,
                        sl, tp, margin, commission, swap, rollover, gross_pl):
    conn = get_connection()
    conn.execute('''
        INSERT INTO trader_positions
        (user_email, periodo, conta_bancaria, symbol, type, volume, open_time, open_price,
         close_time, close_price, sl, tp, margin, commission, swap, rollover, gross_pl)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ''', (user_email, periodo, conta_bancaria, symbol, type_, volume, open_time, open_price,
          close_time, close_price, sl, tp, margin, commission, swap, rollover, gross_pl))
    conn.commit()
    conn.close()


def update_trader_position(t_id, periodo, conta_bancaria, symbol, type_, volume,
                           open_time, open_price, close_time, close_price,
                           sl, tp, margin, commission, swap, rollover, gross_pl):
    conn = get_connection()
    conn.execute('''
        UPDATE trader_positions SET
        periodo=%s, conta_bancaria=%s, symbol=%s, type=%s, volume=%s, open_time=%s, open_price=%s,
        close_time=%s, close_price=%s, sl=%s, tp=%s, margin=%s, commission=%s, swap=%s, rollover=%s, gross_pl=%s
        WHERE id=%s
    ''', (periodo, conta_bancaria, symbol, type_, volume, open_time, open_price,
          close_time, close_price, sl, tp, margin, commission, swap, rollover, gross_pl, t_id))
    conn.commit()
    conn.close()


def delete_trader_position(t_id):
    conn = get_connection()
    conn.execute('DELETE FROM trader_positions WHERE id=%s', (t_id,))
    conn.commit()
    conn.close()


def clear_trader_positions(user_email: str = None, periodo: str = None):
    conn = get_connection()
    if user_email and periodo:
        conn.execute('DELETE FROM trader_positions WHERE user_email=%s AND periodo=%s', (user_email, periodo))
    elif user_email:
        conn.execute('DELETE FROM trader_positions WHERE user_email=%s', (user_email,))
    else:
        conn.execute('DELETE FROM trader_positions')
    conn.commit()
    conn.close()


def get_trader_periodos(user_email: str):
    conn = get_connection()
    rows = conn.execute(
        'SELECT DISTINCT periodo FROM trader_positions WHERE user_email=%s ORDER BY periodo DESC',
        (user_email,),
    ).fetchall()
    conn.close()
    return [r['periodo'] for r in rows]


def get_trader_contas(user_email: str):
    conn = get_connection()
    rows = conn.execute(
        'SELECT DISTINCT conta_bancaria FROM trader_positions WHERE user_email=%s ORDER BY conta_bancaria',
        (user_email,),
    ).fetchall()
    conn.close()
    return [r['conta_bancaria'] for r in rows]
