from db.connection import get_connection


def init_tables():
    conn = get_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS lcto_investimentos (
            id SERIAL PRIMARY KEY,
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


def get_all_lcto_investimentos(user_email: str):
    conn = get_connection()
    rows = conn.execute(
        'SELECT * FROM lcto_investimentos WHERE user_email=%s ORDER BY data_inv DESC, id DESC',
        (user_email,),
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        row = dict(r)
        row['valor_tot_inv'] = (row.get('valor_inv') or 0) * (row.get('qtd') or 0)
        taxa = row.get('taxa') or 0
        row['valor_liq_mes'] = (row.get('valor_atual') or 0) - (row['valor_tot_inv'] + taxa)
        val_mes_ant = row.get('val_mes_ant') or 0
        row['lucro_mes'] = (row.get('valor_atual') or 0) - val_mes_ant
        row['lucro_op'] = (row.get('valor_atual') or 0) - row['valor_tot_inv']
        row['pct_rent'] = (row['lucro_op'] / row['valor_tot_inv'] * 100) if row['valor_tot_inv'] > 0 else 0
        result.append(row)
    return result


def add_lcto_investimento(user_email, banco, tp_investimento, data_inv, valor_inv,
                          moeda, qtd, taxa, valor_atual, val_mes_ant, aporte):
    conn = get_connection()
    conn.execute('''
        INSERT INTO lcto_investimentos
        (user_email, banco, tp_investimento, data_inv, valor_inv, moeda, qtd, taxa, valor_atual, val_mes_ant, aporte)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ''', (user_email, banco, tp_investimento, data_inv, valor_inv, moeda, qtd, taxa, valor_atual, val_mes_ant, aporte))
    conn.commit()
    conn.close()


def update_lcto_investimento(li_id, banco, tp_investimento, data_inv, valor_inv,
                             moeda, qtd, taxa, valor_atual, val_mes_ant, aporte):
    conn = get_connection()
    conn.execute('''
        UPDATE lcto_investimentos SET
        banco=%s, tp_investimento=%s, data_inv=%s, valor_inv=%s, moeda=%s, qtd=%s, taxa=%s, valor_atual=%s, val_mes_ant=%s, aporte=%s
        WHERE id=%s
    ''', (banco, tp_investimento, data_inv, valor_inv, moeda, qtd, taxa, valor_atual, val_mes_ant, aporte, li_id))
    conn.commit()
    conn.close()


def delete_lcto_investimento(li_id):
    conn = get_connection()
    conn.execute('DELETE FROM lcto_investimentos WHERE id=%s', (li_id,))
    conn.commit()
    conn.close()


def clear_lcto_investimentos():
    conn = get_connection()
    conn.execute('DELETE FROM lcto_investimentos')
    conn.commit()
    conn.close()
