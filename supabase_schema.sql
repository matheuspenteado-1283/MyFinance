-- =============================================================
-- MyFinance 2.0 — Schema PostgreSQL para Supabase
-- Executar no SQL Editor do Supabase (dashboard.supabase.com)
-- =============================================================

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS categorias_aprendidas (
    id SERIAL PRIMARY KEY,
    padrao_descricao TEXT UNIQUE NOT NULL,
    categoria TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cad_despesas (
    id SERIAL PRIMARY KEY,
    despesa TEXT,
    tipo_despesa TEXT,
    fator_divisao REAL,
    prioridade TEXT
);

CREATE TABLE IF NOT EXISTS cad_contas (
    id SERIAL PRIMARY KEY,
    descricao TEXT,
    agencia TEXT,
    conta TEXT,
    dados_acesso TEXT,
    senha TEXT,
    comentarios TEXT
);

CREATE TABLE IF NOT EXISTS cad_receitas (
    id SERIAL PRIMARY KEY,
    descricao TEXT
);

CREATE TABLE IF NOT EXISTS cad_investimentos (
    id SERIAL PRIMARY KEY,
    descricao TEXT
);

CREATE TABLE IF NOT EXISTS cad_usuarios (
    id SERIAL PRIMARY KEY,
    chave_usr1 TEXT,
    chave_usr2 TEXT,
    nome TEXT,
    fator_pagamento REAL
);

CREATE TABLE IF NOT EXISTS tb_tipo_imposto (
    id SERIAL PRIMARY KEY,
    tp_imposto TEXT,
    alq_imposto REAL,
    pagamento TEXT
);

CREATE TABLE IF NOT EXISTS despesas_mensais (
    id SERIAL PRIMARY KEY,
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
    criado_em TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')
);

CREATE TABLE IF NOT EXISTS despesas_anuais (
    id SERIAL PRIMARY KEY,
    user_email TEXT,
    ano INTEGER,
    categoria_final TEXT,
    total_usr1 REAL DEFAULT 0,
    total_usr2 REAL DEFAULT 0,
    total_geral REAL DEFAULT 0,
    criado_em TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')
);

CREATE TABLE IF NOT EXISTS receitas_mensais (
    id SERIAL PRIMARY KEY,
    user_email TEXT,
    data TEXT,
    tipo_receita TEXT,
    valor_original REAL,
    moeda_original TEXT,
    cotacao REAL,
    valor_eur REAL,
    valor_brl REAL,
    conta_bancaria TEXT,
    mes_referencia TEXT,
    despesa_mensal_id INTEGER,
    comentarios TEXT,
    criado_em TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')
);

CREATE TABLE IF NOT EXISTS lcto_impostos (
    id SERIAL PRIMARY KEY,
    user_email TEXT,
    mes_ano TEXT,
    tp_imposto TEXT,
    moeda_faturado TEXT,
    valor_faturado REAL,
    valor_imposto REAL,
    moeda_pagamento TEXT,
    pagamento REAL,
    desconto_iva REAL,
    criado_em TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'),
    pagamento_mes_ano TEXT
);

CREATE TABLE IF NOT EXISTS lcto_emprestimos (
    id SERIAL PRIMARY KEY,
    user_email TEXT,
    tipo TEXT,
    beneficiario TEXT,
    valor_operacao REAL,
    data_emprestimo TEXT,
    data_operacao TEXT,
    obs TEXT,
    status TEXT,
    criado_em TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS'),
    moeda_emp TEXT
);

CREATE TABLE IF NOT EXISTS lcto_investimentos (
    id SERIAL PRIMARY KEY,
    user_email TEXT,
    banco TEXT,
    tp_investimento TEXT,
    data_inv TEXT,
    valor_inv REAL,
    moeda TEXT,
    qtd REAL,
    taxa REAL,
    valor_atual REAL,
    val_mes_ant REAL,
    aporte REAL,
    criado_em TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')
);

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
    criado_em TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')
);

CREATE TABLE IF NOT EXISTS relatorios_configurados (
    id SERIAL PRIMARY KEY,
    user_email TEXT,
    nome_relatorio TEXT,
    tabelas TEXT,
    campos TEXT,
    agrupador TEXT,
    mes_inicio TEXT,
    mes_fim TEXT,
    moedas TEXT,
    criado_em TEXT DEFAULT to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS')
);
