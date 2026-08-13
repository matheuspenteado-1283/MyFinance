import json

from db.connection import get_connection


def init_tables():
    conn = get_connection()
    c = conn.cursor()

    # ── Fase 0: multi-tenancy da tabela existente ──────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS categorias_aprendidas (
            id SERIAL PRIMARY KEY,
            padrao_descricao TEXT NOT NULL,
            categoria TEXT NOT NULL,
            user_email TEXT
        )
    ''')
    c.execute('ALTER TABLE categorias_aprendidas ADD COLUMN IF NOT EXISTS user_email TEXT')
    # A tabela antiga tinha UNIQUE em padrao_descricao (nome default gerado pelo PG).
    # Remover para permitir a mesma regra em usuários diferentes.
    c.execute('ALTER TABLE categorias_aprendidas '
              'DROP CONSTRAINT IF EXISTS categorias_aprendidas_padrao_descricao_key')
    c.execute('''
        CREATE UNIQUE INDEX IF NOT EXISTS ux_cat_aprend_user_padrao
            ON categorias_aprendidas (user_email, padrao_descricao)
    ''')
    # Backfill: atribuir as regras pré-existentes ao usuário mais antigo (fundador).
    c.execute('''
        UPDATE categorias_aprendidas
           SET user_email = (SELECT email FROM users ORDER BY id LIMIT 1)
         WHERE user_email IS NULL
    ''')

    # ── Fase 3: biblioteca de receitas (compartilhada entre usuários) ──────
    c.execute('''
        CREATE TABLE IF NOT EXISTS extrato_receitas (
            id            SERIAL PRIMARY KEY,
            fingerprint   TEXT NOT NULL UNIQUE,
            banco_label   TEXT NOT NULL DEFAULT 'Desconhecido',
            pais          TEXT,
            formato       TEXT NOT NULL,
            spec          JSONB NOT NULL,
            status        TEXT NOT NULL DEFAULT 'proposed',
            origem        TEXT NOT NULL DEFAULT 'manual',
            confirmacoes  INTEGER NOT NULL DEFAULT 0,
            execucoes     INTEGER NOT NULL DEFAULT 0,
            falhas        INTEGER NOT NULL DEFAULT 0,
            criada_por    TEXT,
            criada_em     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            atualizada_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    ''')
    c.execute('CREATE INDEX IF NOT EXISTS ix_receitas_status ON extrato_receitas (status)')

    # ── Fase 1: sessão de importação ───────────────────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS extrato_importacoes (
            id             SERIAL PRIMARY KEY,
            user_email     TEXT NOT NULL,
            arquivo_nome   TEXT NOT NULL,
            arquivo_sha256 TEXT,
            fingerprint    TEXT,
            receita_id     INTEGER REFERENCES extrato_receitas(id),
            conta_bancaria TEXT,
            score          INTEGER NOT NULL DEFAULT 0,
            checks         JSONB NOT NULL DEFAULT '[]'::jsonb,
            status         TEXT NOT NULL DEFAULT 'pendente',
            total_linhas   INTEGER NOT NULL DEFAULT 0,
            criada_em      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            confirmada_em  TIMESTAMPTZ
        )
    ''')
    c.execute('CREATE INDEX IF NOT EXISTS ix_import_user '
              'ON extrato_importacoes (user_email, criada_em DESC)')

    # ── Fase 1: linhas em staging ──────────────────────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS extrato_linhas_staging (
            id             SERIAL PRIMARY KEY,
            importacao_id  INTEGER NOT NULL REFERENCES extrato_importacoes(id) ON DELETE CASCADE,
            linha_idx      INTEGER NOT NULL,
            data           DATE,
            descricao      TEXT,
            valor_original NUMERIC(14,2),
            moeda          TEXT,
            saldo          NUMERIC(14,2),
            is_debit       BOOLEAN,
            categoria      TEXT,
            suspeita       BOOLEAN NOT NULL DEFAULT FALSE,
            motivos        JSONB NOT NULL DEFAULT '[]'::jsonb,
            raw            JSONB
        )
    ''')
    c.execute('CREATE INDEX IF NOT EXISTS ix_staging_import '
              'ON extrato_linhas_staging (importacao_id, linha_idx)')

    conn.commit()
    conn.close()


def save_category_rule(description: str, category: str, user_email: str = None):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO categorias_aprendidas (padrao_descricao, categoria, user_email)
        VALUES (%s, %s, %s)
        ON CONFLICT (user_email, padrao_descricao)
        DO UPDATE SET categoria = EXCLUDED.categoria
    ''', (description.lower().strip(), category, user_email))
    conn.commit()
    conn.close()


def guess_category(description: str, user_email: str = None) -> str:
    conn = get_connection()
    c = conn.cursor()

    desc_lower = description.lower().strip()

    if user_email:
        c.execute('SELECT categoria FROM categorias_aprendidas '
                  'WHERE user_email = %s AND padrao_descricao = %s',
                  (user_email, desc_lower))
    else:
        c.execute('SELECT categoria FROM categorias_aprendidas '
                  'WHERE padrao_descricao = %s', (desc_lower,))
    row = c.fetchone()
    if row:
        conn.close()
        return row['categoria']

    if user_email:
        c.execute('SELECT padrao_descricao, categoria FROM categorias_aprendidas '
                  'WHERE user_email = %s', (user_email,))
    else:
        c.execute('SELECT padrao_descricao, categoria FROM categorias_aprendidas')
    all_rules = c.fetchall()
    conn.close()

    for rule in all_rules:
        if rule['padrao_descricao'] in desc_lower:
            return rule['categoria']

    return 'Não Categorizado'


# ─────────────────────────────────────────────────────────────────────────────
# Receitas (biblioteca global — contém apenas estrutura, nunca dado)
# ─────────────────────────────────────────────────────────────────────────────

def buscar_receita_por_fingerprint(fingerprint: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM extrato_receitas WHERE fingerprint = %s', (fingerprint,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def criar_receita(fingerprint: str, spec: dict, *, banco_label='Desconhecido',
                  pais=None, formato=None, origem='manual', criada_por=None):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO extrato_receitas
            (fingerprint, banco_label, pais, formato, spec, status, origem, criada_por)
        VALUES (%s, %s, %s, %s, %s, 'proposed', %s, %s)
        ON CONFLICT (fingerprint) DO NOTHING
    ''', (fingerprint, banco_label, pais,
          formato or spec.get('estrategia', 'desconhecido'),
          json.dumps(spec, ensure_ascii=False), origem, criada_por))
    conn.commit()
    c.execute('SELECT * FROM extrato_receitas WHERE fingerprint = %s', (fingerprint,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def promover_receita(receita_id: int, *, executou=True):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        UPDATE extrato_receitas
           SET status = CASE WHEN status = 'proposed' THEN 'verified' ELSE status END,
               confirmacoes = confirmacoes + 1,
               execucoes = execucoes + %s,
               atualizada_em = NOW()
         WHERE id = %s
    ''', (1 if executou else 0, receita_id))
    conn.commit()
    conn.close()


def registrar_falha_receita(receita_id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute('UPDATE extrato_receitas SET falhas = falhas + 1, atualizada_em = NOW() '
              'WHERE id = %s', (receita_id,))
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# Sessão de importação
# ─────────────────────────────────────────────────────────────────────────────

def criar_importacao(user_email, arquivo_nome, *, arquivo_sha256=None,
                     fingerprint=None, receita_id=None, conta_bancaria=None,
                     score=0, checks=None, total_linhas=0, status='pendente'):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO extrato_importacoes
            (user_email, arquivo_nome, arquivo_sha256, fingerprint, receita_id,
             conta_bancaria, score, checks, status, total_linhas)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    ''', (user_email, arquivo_nome, arquivo_sha256, fingerprint, receita_id,
          conta_bancaria, score,
          json.dumps(checks or [], ensure_ascii=False), status, total_linhas))
    importacao_id = c.fetchone()['id']
    conn.commit()
    conn.close()
    return importacao_id


def salvar_linhas_staging(importacao_id: int, linhas: list):
    if not linhas:
        return
    conn = get_connection()
    c = conn.cursor()
    for linha in linhas:
        c.execute('''
            INSERT INTO extrato_linhas_staging
                (importacao_id, linha_idx, data, descricao, valor_original, moeda,
                 saldo, is_debit, categoria, suspeita, motivos, raw)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            importacao_id,
            linha.get('linha_idx'),
            linha.get('data'),
            linha.get('descricao'),
            linha.get('valor_original'),
            linha.get('moeda'),
            linha.get('saldo'),
            linha.get('is_debit'),
            linha.get('categoria'),
            bool(linha.get('suspeita')),
            json.dumps(linha.get('motivos') or [], ensure_ascii=False),
            json.dumps(linha.get('raw'), ensure_ascii=False) if linha.get('raw') is not None else None,
        ))
    conn.commit()
    conn.close()


def confirmar_importacao(importacao_id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute('UPDATE extrato_importacoes '
              "SET status = 'confirmada', confirmada_em = NOW() WHERE id = %s",
              (importacao_id,))
    conn.commit()
    conn.close()


def descartar_importacao(importacao_id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE extrato_importacoes SET status = 'descartada' WHERE id = %s",
              (importacao_id,))
    conn.commit()
    conn.close()
