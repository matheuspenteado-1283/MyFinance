-- Performance indexes — executar uma vez no Supabase SQL Editor
-- Todas as queries críticas filtram por user_email e/ou mes_referencia

CREATE INDEX IF NOT EXISTS idx_despesas_user_mes
    ON despesas_mensais(user_email, mes_referencia);

CREATE INDEX IF NOT EXISTS idx_despesas_user_receita
    ON despesas_mensais(user_email, receita);

CREATE INDEX IF NOT EXISTS idx_receitas_user_mes
    ON receitas_mensais(user_email, mes_referencia);

CREATE INDEX IF NOT EXISTS idx_receitas_despesa_id
    ON receitas_mensais(despesa_mensal_id)
    WHERE despesa_mensal_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_investimentos_user
    ON lcto_investimentos(user_email);

CREATE INDEX IF NOT EXISTS idx_emprestimos_user
    ON lcto_emprestimos(user_email);

CREATE INDEX IF NOT EXISTS idx_impostos_user
    ON lcto_impostos(user_email);

CREATE INDEX IF NOT EXISTS idx_trader_user
    ON trader_positions(user_email);

CREATE INDEX IF NOT EXISTS idx_budget_user_ano
    ON budget_items(user_email, ano);

-- Cache de cotações (criado pela aplicação se não existir)
CREATE TABLE IF NOT EXISTS exchange_rate_cache (
    date_str      TEXT NOT NULL,
    from_currency TEXT NOT NULL,
    to_currency   TEXT NOT NULL,
    rate          REAL NOT NULL,
    fetched_at    TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (date_str, from_currency, to_currency)
);
