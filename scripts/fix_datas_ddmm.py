"""
Backfill: normaliza datas DD/MM/AAAA -> AAAA-MM-DD em despesas_mensais e
receitas_mensais. NAO altera mes_referencia. Idempotente.

Uso: python3 scripts/fix_datas_ddmm.py
"""
import os
import re
import csv
import sys
from datetime import datetime

import psycopg2
import psycopg2.extras

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DDMM = re.compile(r'^(\d{2})/(\d{2})/(\d{4})$')


def _db_url():
    env = open(os.path.join(ROOT, '.env')).read()
    m = re.search(r'DATABASE_URL=(\S+)', env)
    if not m:
        sys.exit('DATABASE_URL nao encontrado no .env')
    return m.group(1)


def to_iso(d):
    m = DDMM.match(d.strip())
    if not m:
        return None
    dd, mm, yyyy = m.groups()
    return f'{yyyy}-{mm}-{dd}'


def main():
    conn = psycopg2.connect(_db_url())
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = os.path.join(ROOT, 'scripts', f'backup_datas_{ts}.csv')

    affected = []
    for tabela in ('despesas_mensais', 'receitas_mensais'):
        c.execute(
            f"SELECT id, data, mes_referencia FROM {tabela} "
            f"WHERE data ~ '^[0-9]{{2}}/[0-9]{{2}}/[0-9]{{4}}$'"
        )
        for r in c.fetchall():
            affected.append((tabela, r['id'], r['data'], r['mes_referencia'], to_iso(r['data'])))

    if not affected:
        print('Nada a fazer: nenhuma data DD/MM/AAAA encontrada.')
        conn.close()
        return

    # backup
    with open(backup_path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['tabela', 'id', 'data_antiga', 'mes_referencia', 'data_nova'])
        w.writerows(affected)
    print(f'Backup: {backup_path} ({len(affected)} linhas)')

    # update
    updated = 0
    for tabela, _id, _old, _mes, novo in affected:
        if novo is None:
            continue
        c.execute(f"UPDATE {tabela} SET data=%s WHERE id=%s", (novo, _id))
        updated += 1
    conn.commit()
    print(f'Atualizadas: {updated}')

    # validacao
    for tabela in ('despesas_mensais', 'receitas_mensais'):
        c.execute(
            f"SELECT count(*) n FROM {tabela} "
            f"WHERE data ~ '^[0-9]{{2}}/[0-9]{{2}}/[0-9]{{4}}$'"
        )
        print(f'  {tabela}: restantes DD/MM = {c.fetchone()["n"]}')
    conn.close()


if __name__ == '__main__':
    main()
