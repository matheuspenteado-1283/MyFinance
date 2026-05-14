"""
Script de migração: SQLite (extratos.db) → Supabase (PostgreSQL)

Como usar:
  1. Garanta que .env tem DATABASE_URL apontando para o Supabase
  2. Execute o supabase_schema.sql no SQL Editor do Supabase primeiro
  3. Rode: python migrate_to_supabase.py
"""

import sqlite3
import psycopg2
import psycopg2.extras
import os
from dotenv import load_dotenv

load_dotenv()

SQLITE_PATH = os.path.join(os.path.dirname(__file__), 'extratos.db')
DATABASE_URL = os.getenv('DATABASE_URL')

TABLES = [
    'users',
    'categorias_aprendidas',
    'cad_despesas',
    'cad_contas',
    'cad_receitas',
    'cad_investimentos',
    'cad_usuarios',
    'tb_tipo_imposto',
    'despesas_mensais',
    'despesas_anuais',
    'receitas_mensais',
    'lcto_impostos',
    'lcto_emprestimos',
    'lcto_investimentos',
    'trader_positions',
    'relatorios_configurados',
]


def migrate():
    if not DATABASE_URL:
        print("ERRO: DATABASE_URL não definida no .env")
        return

    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row
    pg_conn = psycopg2.connect(DATABASE_URL)
    pg_cur = pg_conn.cursor()

    print(f"Conectado ao SQLite: {SQLITE_PATH}")
    print(f"Conectado ao Supabase PostgreSQL\n")

    for table in TABLES:
        sqlite_cur = sqlite_conn.cursor()
        try:
            sqlite_cur.execute(f'SELECT * FROM {table}')
        except sqlite3.OperationalError:
            print(f"  [{table}] não encontrada no SQLite — pulando")
            continue

        rows = sqlite_cur.fetchall()
        if not rows:
            print(f"  [{table}] 0 registros — pulando")
            continue

        columns = [d[0] for d in sqlite_cur.description]
        placeholders = ','.join(['%s'] * len(columns))
        cols_str = ','.join(columns)
        insert_sql = f'INSERT INTO {table} ({cols_str}) VALUES ({placeholders}) ON CONFLICT DO NOTHING'

        values = [tuple(row) for row in rows]
        try:
            psycopg2.extras.execute_batch(pg_cur, insert_sql, values)
            pg_conn.commit()
            print(f"  [{table}] {len(values)} registros migrados ✓")
        except Exception as e:
            pg_conn.rollback()
            print(f"  [{table}] ERRO: {e}")

    # Resetar sequências SERIAL para continuar após os dados migrados
    print("\nResetando sequências...")
    for table in TABLES:
        try:
            pg_cur.execute(f"""
                SELECT setval(pg_get_serial_sequence('{table}', 'id'),
                              COALESCE((SELECT MAX(id) FROM {table}), 1))
            """)
            pg_conn.commit()
            print(f"  [{table}] sequência resetada ✓")
        except Exception as e:
            pg_conn.rollback()
            print(f"  [{table}] sequência: {e}")

    pg_cur.close()
    pg_conn.close()
    sqlite_conn.close()
    print("\nMigração concluída.")


if __name__ == '__main__':
    migrate()
