# MyFinance 2.0 - Especificacao Funcional e Tecnica

Documento de referencia para detalhar correcoes, validar comportamento esperado e localizar rapidamente telas, rotas, tabelas, funcoes e calculos.

## 1. Visao Geral

O MyFinance 2.0 e uma aplicacao Flask com frontend SPA em `templates/index.html`. A aplicacao organiza financas pessoais por usuario logado, processa extratos, registra despesas e receitas mensais, controla cadastros auxiliares, impostos, emprestimos, budget, investimentos, operacoes de trader e relatorios.

Estado tecnico atual observado no codigo:

- Entrada da aplicacao: `app.py`.
- Configuracao Flask: `config.py`.
- Acesso a dados: `db/connection.py`.
- Inicializacao idempotente: `db/__init__.py`.
- Modulos funcionais: `modules/*`.
- Banco em uso no codigo atual: PostgreSQL/Supabase via `psycopg2`, com wrapper que imita parte da API SQLite.
- Arquivo legado: `database.py` ainda existe, mas a aplicacao modular usa `modules/*/db.py`.
- Schema base Supabase: `supabase_schema.sql`.

Observacao importante: o AGENTS.md descreve origem SQLite, mas o codigo atual ja esta migrado para conexao PostgreSQL. O arquivo `extratos.db` pode existir como legado, mas `db/connection.py` usa `DATABASE_URL` ou variaveis `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`.

## 2. Arquitetura Tecnica

### 2.1 Inicializacao

`app.py` executa:

1. `create_app()`.
2. `Flask(__name__)`.
3. `configure_app(app)`.
4. `init_all()`.
5. Registro dos Blueprints.
6. Cria endpoints auxiliares `/health` e `/debug/db`.
7. Inicia keep-alive no Render se `RENDER_EXTERNAL_URL` estiver definido.

Blueprints registrados:

- `auth`
- `extratos`
- `cadastros`
- `despesas_mensais`
- `receitas_mensais`
- `impostos`
- `emprestimos`
- `investimentos`
- `trader`
- `dashboard`
- `relatorios`
- `budget`

### 2.2 Configuracoes

Arquivo: `config.py`

- `SECRET_KEY`: vem de variavel de ambiente ou usa fallback.
- `UPLOAD_FOLDER`: `uploads`.
- `MAX_CONTENT_LENGTH`: 16 MB.
- `ALLOWED_EXTENSIONS`: `pdf`, `csv`, `xls`, `xlsx`, `xml`.
- `allowed_file(filename)`: valida extensao de uploads.
- JSON provider customizado serializa `datetime` e `date` em ISO string.

### 2.3 Conexao com Banco

Arquivo: `db/connection.py`

- `get_connection()`: retorna `PGConnection`.
- `PGConnection`: wrapper de conexao `psycopg2`.
- `PGCursor`: wrapper de cursor `RealDictCursor`.

Variaveis aceitas:

- Preferencial: `DATABASE_URL`.
- Alternativa: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`.
- `sslmode=require` e aplicado automaticamente quando necessario.

### 2.4 Inicializacao de Tabelas

Arquivo: `db/__init__.py`

`init_all()` importa e chama `init_tables()` dos modulos:

- `modules.auth.db`
- `modules.extratos.db`
- `modules.cadastros.db.*`
- `modules.despesas_mensais.db`
- `modules.receitas_mensais.db`
- `modules.impostos.db`
- `modules.emprestimos.db`
- `modules.investimentos.db`
- `modules.trader.db`
- `modules.relatorios.db`
- `modules.budget.db`

O processo e idempotente e protegido por `try/except` para nao derrubar o cold start se o banco estiver indisponivel.

## 3. Tabelas

### 3.1 `users`

Modulo: autenticacao.

Campos:

- `id`
- `email`
- `password_hash`

Uso:

- Cadastro de login.
- Validacao de senha.
- Recuperacao de senha.

### 3.2 `password_reset_tokens`

Modulo: autenticacao.

Campos:

- `id`
- `email`
- `token`
- `expires_at`
- `used`

Uso:

- Fluxo de esqueci minha senha.
- Token dura 1 hora.

### 3.3 `categorias_aprendidas`

Modulo: extratos.

Campos:

- `id`
- `padrao_descricao`
- `categoria`

Uso:

- Aprendizado de categoria por descricao de extrato.
- `guess_category()` tenta match exato e depois match por substring.

### 3.4 `cad_despesas`

Modulo: cadastros / despesas.

Campos:

- `id`
- `user_email`
- `despesa`
- `tipo_despesa`
- `fator_divisao`
- `prioridade`

Uso:

- Cadastro de categorias de despesa.
- Combo de categoria em despesas mensais.
- Relatorios mensais e anuais de despesas.
- Budget de despesas.
- Consolidacao por tipo de despesa.

### 3.5 `cad_contas`

Modulo: cadastros / contas.

Campos:

- `id`
- `user_email`
- `descricao`
- `agencia`
- `conta`
- `dados_acesso`
- `senha`
- `comentarios`

Uso:

- Cadastro de contas bancarias.
- Combo de conta em extratos, despesas, receitas, investimentos e trader.
- Visualizacao de senha exige senha do app.

### 3.6 `cad_receitas`

Modulo: cadastros / receitas.

Campos:

- `id`
- `user_email`
- `descricao`

Uso:

- Cadastro de categorias/tipos de receita.
- Combo de tipo de receita.
- Relatorio de receitas.
- Budget de receitas.

### 3.7 `cad_investimentos`

Modulo: cadastros / investimentos.

Campos:

- `id`
- `user_email`
- `descricao`

Uso:

- Cadastro de tipos/ativos de investimento.
- Combo em lancamentos de investimentos.

### 3.8 `cad_usuarios`

Modulo: cadastros / usuarios.

Campos:

- `id`
- `user_email`
- `chave_usr1`
- `chave_usr2`
- `nome`
- `fator_pagamento`

Uso:

- Nomeacao dos responsaveis USR1 e USR2 em relatorios.
- Parametro auxiliar para divisao ou identificacao de pagamento.

### 3.9 `tb_tipo_imposto`

Modulo: cadastros / tipo de imposto.

Campos:

- `id`
- `user_email`
- `tp_imposto`
- `alq_imposto`
- `pagamento`

Uso:

- Combo de tipo de imposto.
- Calculo automatico do valor do imposto a partir de aliquota.
- Preenchimento automatico do tipo de pagamento.

### 3.10 `despesas_mensais`

Modulo: despesas mensais.

Campos:

- `id`
- `user_email`
- `data`
- `descricao`
- `valor_original`
- `moeda`
- `cambio_eur`
- `valor_eur`
- `usr1`
- `usr2`
- `diferenca_original`
- `status_pago`
- `categoria_final`
- `receita`
- `comentarios`
- `conta_bancaria`
- `mes_referencia`
- `criado_em`

Uso:

- Lancamentos mensais de despesas.
- Tambem armazena itens marcados como receita quando importados/processados via extratos.
- Base principal de dashboards de despesas, fluxo de caixa, relatorios mensais/anuais e consolidacoes.

### 3.11 `despesas_anuais`

Modulo: despesas mensais / dashboard anual.

Campos:

- `id`
- `user_email`
- `ano`
- `categoria_final`
- `total_usr1`
- `total_usr2`
- `total_geral`
- `criado_em`

Uso:

- Resultado consolidado por ano e categoria.
- Alimenta `/api/relatorio_anual`.

### 3.12 `receitas_mensais`

Modulo: receitas mensais.

Campos:

- `id`
- `user_email`
- `data`
- `tipo_receita`
- `valor_original`
- `moeda_original`
- `cotacao`
- `valor_eur`
- `valor_brl`
- `conta_bancaria`
- `mes_referencia`
- `despesa_mensal_id`
- `comentarios`
- `criado_em`

Uso:

- Lancamentos mensais de receitas.
- Pode ser sincronizada a partir de despesas mensais marcadas como receita.
- Base de dashboards de receitas, fluxo de caixa, budget e relatorios.

### 3.13 `lcto_impostos`

Modulo: impostos.

Campos:

- `id`
- `user_email`
- `mes_ano`
- `tp_imposto`
- `moeda_faturado`
- `valor_faturado`
- `valor_imposto`
- `moeda_pagamento`
- `pagamento`
- `pagamento_mes_ano`
- `desconto_iva`
- `criado_em`

Uso:

- Lancamentos de impostos.
- Dashboard de impostos.
- Relatorio dinamico.
- Exportacao Excel.

### 3.14 `lcto_emprestimos`

Modulo: emprestimos.

Campos:

- `id`
- `user_email`
- `tipo`
- `beneficiario`
- `valor_operacao`
- `moeda_emp`
- `data_emprestimo`
- `data_operacao`
- `obs`
- `status`
- `criado_em`

Uso:

- Controle de emprestimos, pagamentos e abatimentos.
- Calculo de saldo de emprestimos.
- Composicao do patrimonio liquido em dashboards.

### 3.15 `lcto_investimentos`

Modulo: lancamentos de investimentos.

Campos:

- `id`
- `user_email`
- `banco`
- `tp_investimento`
- `data_inv`
- `valor_inv`
- `moeda`
- `qtd`
- `taxa`
- `valor_atual`
- `val_mes_ant`
- `aporte`
- `criado_em`

Uso:

- Controle de posicoes de investimento.
- Calculos de valor total, lucro, rentabilidade e P&L.
- Dashboards de investimentos, P&L e patrimonio.

### 3.16 `trader_positions`

Modulo: trader.

Campos:

- `id`
- `user_email`
- `periodo`
- `conta_bancaria`
- `symbol`
- `type`
- `volume`
- `open_time`
- `open_price`
- `close_time`
- `close_price`
- `sl`
- `tp`
- `margin`
- `commission`
- `swap`
- `rollover`
- `gross_pl`
- `criado_em`

Uso:

- Registro/importacao de operacoes de trading.
- Dashboard de P&L trader.
- Filtros por periodo e conta.

### 3.17 `relatorios_configurados`

Modulo: relatorios dinamicos.

Campos:

- `id`
- `user_email`
- `nome_relatorio`
- `tabelas`
- `campos`
- `agrupador`
- `mes_inicio`
- `mes_fim`
- `moedas`
- `criado_em`

Uso:

- Salvar configuracoes de relatorios dinamicos.
- Reabrir e executar configuracoes depois.

### 3.18 `budget_items`

Modulo: budget.

Campos:

- `id`
- `user_email`
- `ano`
- `tipo`
- `categoria_id`
- `categoria_nome`
- `tipo_categoria`
- `moeda`
- `valor_jan` ... `valor_dez`
- `variacao_mensal_pct`
- `variacao_anual_pct`
- `criado_em`

Uso:

- Orçamento anual por categoria e mes.
- Comparativo budget x realizado.
- Dashboard de budget.

Observacao: esta tabela e criada por `modules/budget/db.py`, mas nao aparece no `supabase_schema.sql` atual.

## 4. Modulos Funcionais

### 4.1 Autenticacao

Arquivos:

- `modules/auth/routes.py`
- `modules/auth/db.py`
- `modules/auth/email_utils.py`

Telas:

- Login: `authEmail`, `authPassword`.
- Esqueci senha: `forgotEmail`.
- Reset de senha: `templates/reset_password.html`.
- Avancado/Limpeza: checkboxes `cfg_despesas`, `cfg_contas`, `cfg_receitas`, `cfg_investimentos`, `cfg_usuarios`, `cfg_tipo_imposto`.

Rotas:

- `GET /`: renderiza `index.html`.
- `GET /api/me`: retorna usuario logado.
- `POST /register`: cadastra usuario.
- `POST /login`: autentica usuario.
- `POST /forgot-password`: cria token e envia e-mail.
- `GET /reset-password`: abre pagina de redefinicao.
- `POST /reset-password`: altera senha.
- `POST /logout`: encerra sessao.
- `POST /api/limpar_dados`: apaga dados transacionais do usuario.
- `POST /api/limpar_configuracoes`: apaga cadastros selecionados.

Funcoes principais:

- `register_user(email, password)`: cria usuario com hash PBKDF2. Antes de inserir, remove alguns dados transacionais associados ao e-mail.
- `verify_user(email, password)`: valida senha.
- `get_user_by_email(email)`: busca usuario.
- `create_reset_token(email)`: cria token de reset valido por 1 hora.
- `verify_reset_token(token)`: valida token nao usado e nao expirado.
- `consume_reset_token(token, new_password)`: atualiza senha e marca token como usado.
- `limpar_dados_usuario(email)`: apaga despesas, receitas, impostos, emprestimos e categorias aprendidas.

### 4.2 Extratos

Arquivos:

- `modules/extratos/routes.py`
- `modules/extratos/parser.py`
- `modules/extratos/db.py`
- `exchange_api.py`

Tela:

- Modulo `extratosModule`.
- Upload: `fileInput`.
- Conta bancaria: `uploadContaBancaria`, carregada de `cad_contas`.
- Na tabela processada: valores editaveis `p1_<id>`, `p2_<id>`, categoria `cat_<id>`, conta `cta_<id>`, receita `rec_<id>`, comentarios `com_<id>`.

Rotas:

- `POST /upload`: recebe `files[]`, processa arquivos e retorna transacoes.
- `POST /save_category`: salva categoria aprendida.
- `POST /export`: exporta transacoes processadas para Excel.

Tabelas:

- `categorias_aprendidas`.
- Pode gerar dados para posterior gravacao em `despesas_mensais` pela tela.

Funcoes principais:

- `process_file(filepath)`: identifica extensao e chama parser de CSV, Excel/XML ou PDF.
- `_df_to_transactions(df, filepath)`: transforma dataframe em lista de transacoes.
- `_find_column(df, possible_names)`: encontra colunas por nomes aproximados.
- `_parse_date(date_string)`: normaliza datas para `YYYY-MM-DD`.
- `_parse_value(val_str)`: converte valores com formatos BR/EU/US para float.
- `_read_xml_xls(filepath)`: le Excel XML com `lxml` ou BeautifulSoup.
- `process_despesas_file(filepath)`: usado para importar cadastro de despesas.
- `save_category_rule(description, category)`: grava ou atualiza categoria aprendida.
- `guess_category(description)`: retorna categoria aprendida ou `Outros`.
- `get_exchange_rate(date_str, from_currency, to_currency='EUR')`: busca cambio na Frankfurter API; retorna `1.0` se moedas iguais ou se falhar.

Calculos:

- `valor_eur = round(valor_original * cambio, 2)`.
- `pag1 = round(valor_original / 2, 2)`.
- `pag2 = round(valor_original / 2, 2)`.
- `receita = not is_debit`.
- No export: `diferenca = abs((pag1 + pag2) - valor_original)`.
- `status = OK` se `diferenca < 0.01`, senao `NOK`.

### 4.3 Cadastros

Arquivo:

- `modules/cadastros/routes.py`
- `modules/cadastros/db/*.py`

#### 4.3.1 Cadastro de Despesas

Tela:

- Modulo `cadDespesasModule`.
- Campos: `cd_nome`, `cd_tipo`, `cd_fator`, `cd_prio`.
- Upload: `cd_file`.

Rotas:

- `GET/POST /api/cad_despesas`
- `PUT/DELETE /api/cad_despesas/<id>`
- `POST /api/cad_despesas/upload`
- `GET|POST /api/cad_despesas/export`

Tabela:

- `cad_despesas`.

Funcoes:

- `get_all_despesas(user_email)`: lista categorias.
- `add_despesa(...)`: insere categoria.
- `update_despesa(...)`: atualiza categoria.
- `delete_despesa(...)`: exclui categoria.
- `overwrite_despesas(...)`: substitui lista importada.
- `clear_despesas(user_email)`: limpa cadastro.

#### 4.3.2 Cadastro de Contas

Tela:

- Modulo `cadContasModule`.
- Campos: `cc_desc`, `cc_agencia`, `cc_conta`, `cc_acesso`, `cc_senha`, `cc_obs`.
- Modal de senha: `modalAppPassword`.
- Upload: `cc_file`.

Rotas:

- `GET/POST /api/cad_contas`
- `PUT/DELETE /api/cad_contas/<id>`
- `POST /api/cad_contas/<id>/senha`
- `POST /api/upload_contas`
- `GET /api/export_contas`

Tabela:

- `cad_contas`.

Funcoes:

- `get_all_contas(user_email)`.
- `add_conta(...)`.
- `update_conta(...)`.
- `delete_conta(...)`.
- `clear_contas(user_email)`.
- `get_senha_conta(user_email, id)`.

Regra:

- Para revelar senha de conta, a rota valida a senha do app antes de retornar `senha`.

#### 4.3.3 Cadastro de Receitas

Tela:

- Modulo `cadReceitasModule`.
- Campo: `cr_desc`.
- Upload: `cr_file`.

Rotas:

- `GET/POST /api/cad_receitas`
- `PUT/DELETE /api/cad_receitas/<id>`
- `POST /api/upload_receitas`
- `GET /api/export_receitas`

Tabela:

- `cad_receitas`.

Funcoes:

- `get_all_receitas(user_email)`.
- `add_receita(user_email, descricao)`.
- `update_receita(user_email, id, descricao)`.
- `delete_receita(user_email, id)`.
- `clear_receitas(user_email)`.

#### 4.3.4 Cadastro de Investimentos

Tela:

- Modulo `cadInvestimentosModule`.
- Campo: `ci_desc`.
- Upload: `ci_file`.

Rotas:

- `GET/POST /api/cad_investimentos`
- `PUT/DELETE /api/cad_investimentos/<id>`
- `POST /api/upload_investimentos`
- `GET /api/export_investimentos`

Tabela:

- `cad_investimentos`.

Funcoes:

- `get_all_investimentos(user_email)`.
- `add_investimento(user_email, descricao)`.
- `update_investimento(user_email, id, descricao)`.
- `delete_investimento(user_email, id)`.
- `clear_investimentos(user_email)`.

#### 4.3.5 Cadastro de Usuarios

Tela:

- Modulo `cadUsuariosModule`.
- Campos: `cu_nome`, `cu_fator`, `cu_usr1`, `cu_usr2`.
- Upload: `cu_file`.

Rotas:

- `GET/POST /api/cad_usuarios`
- `PUT/DELETE /api/cad_usuarios/<id>`
- `POST /api/upload_usuarios`
- `GET /api/export_usuarios`

Tabela:

- `cad_usuarios`.

Funcoes:

- `get_all_usuarios(user_email)`.
- `add_usuario(...)`.
- `update_usuario(...)`.
- `delete_usuario(...)`.
- `clear_usuarios(user_email)`.

#### 4.3.6 Cadastro de Tipo de Imposto

Tela:

- Modulo `cadTipoImpostoModule`.
- Campos: `cti_tp_imposto`, `cti_alq_imposto`, `cti_pagamento`.
- Upload: `cti_file`.

Rotas:

- `GET/POST /api/cad_tipo_imposto`
- `PUT/DELETE /api/cad_tipo_imposto/<id>`
- `POST /api/upload_tipo_imposto`
- `GET /api/export_tipo_imposto`

Tabela:

- `tb_tipo_imposto`.

Funcoes:

- `get_all_tipo_imposto(user_email)`.
- `add_tipo_imposto(...)`.
- `update_tipo_imposto(...)`.
- `delete_tipo_imposto(...)`.
- `clear_tipo_imposto(user_email)`.

### 4.4 Despesas Mensais

Arquivos:

- `modules/despesas_mensais/routes.py`
- `modules/despesas_mensais/db.py`

Tela:

- Modulo `despesasMensaisModule`.
- Periodo: `dmMesRef`.
- Moeda de conversao visual/cards: `dmMoedaConversao`.
- Formulario: `dm_data`, `dm_desc`, `dm_valor_orig`, `dm_moeda`, `dm_cambio`, `dm_valor_eur`, `dm_usr1`, `dm_usr2`, `dm_status`, `dm_cat`, `dm_conta`, `dm_receita`, `dm_comments`.
- Filtros de tabela: `dmFilter0`, `dmFilter1`, `dmFilter2`, `dmFilter3`, `dmFilter8`, `dmFilter9`, `dmFilter10`, `dmFilter11`, `dmFilter12`, `dmFilter13`.
- Upload: `dm_file`.
- Modal de importacao: `dmMoedaSelect` e checkboxes de selecao.

Rotas:

- `POST /api/despesas_mensais/check_duplicates`
- `GET /api/despesas_mensais`
- `POST /api/despesas_mensais/batch`
- `POST /api/despesas_mensais`
- `PUT /api/despesas_mensais/<id>`
- `DELETE /api/despesas_mensais/<id>`
- `POST /api/despesas_mensais/batch_delete`
- `POST /api/despesas_mensais/clear`
- `GET /api/despesas_mensais/meses`
- `POST /api/despesas_mensais/upload`
- `POST /api/despesas_mensais/upload_confirm`
- `GET /api/despesas_mensais/consolidacao`
- `POST /api/despesas_anuais/consolidar`
- `POST /export/despesas_mensais`
- `POST /export/consolidacao`
- `GET /api/relatorio_mensal`
- `GET /api/relatorio_mensal/exportar`

Tabelas:

- `despesas_mensais`.
- `despesas_anuais`.
- Consulta `cad_despesas`, `cad_usuarios` e `cad_contas`.

Funcoes:

- `get_despesas_mensais(user_email, mes=None)`: lista lancamentos.
- `save_despesas_mensais_batch(user_email, rows_list)`: grava lote e pula duplicados.
- `check_duplicates_with_data(user_email, candidates)`: retorna dados salvos de duplicados.
- `add_despesa_mensal(user_email, row)`: insere lancamento.
- `update_despesa_mensal(user_email, id, row)`: atualiza lancamento.
- `delete_despesa_mensal(user_email, id)`: exclui lancamento.
- `delete_despesas_mensais_batch(user_email, ids)`: exclui lote.
- `clear_despesas_mensais(user_email, mes=None)`: limpa mes ou tudo.
- `consolidar_despesas_anuais(user_email, ano)`: gera `despesas_anuais`.
- `get_consolidacao_tipo_despesa(user_email, mes_referencia)`: consolida por tipo de despesa e moeda.
- `get_meses_disponiveis(user_email)`: lista meses existentes.
- `get_relatorio_mensal_v2(user_email, mes_referencia)`: monta relatorio mensal por categoria e moeda.

Calculos:

- Conversao: `valor_eur = valor_original * cambio_eur`.
- Diferenca: `diferenca_original = valor_original - (usr1 + usr2)` ou logica equivalente na tela.
- Duplicidade: chave por `user_email`, `conta_bancaria`, `data`, `descricao` normalizada, `valor_original` arredondado e `moeda`.
- Consolidacao anual: `total_usr1 = SUM(usr1)`, `total_usr2 = SUM(usr2)`, `total_geral = SUM(usr1) + SUM(usr2)` por `categoria_final`.
- Consolidacao por tipo: junta `despesas_mensais.categoria_final` com `cad_despesas.despesa` e soma `usr1`, `usr2`, `total_geral` por `tipo_despesa` e `moeda`.
- Relatorio mensal: para cada categoria cadastrada, agrupa despesas reais por `categoria_final` e `moeda`; cards somam `total_usr1`, `total_usr2`, `valor_original`.

### 4.5 Receitas Mensais

Arquivos:

- `modules/receitas_mensais/routes.py`
- `modules/receitas_mensais/db.py`

Tela:

- Modulo `receitasMensaisModule`.
- Periodo: `rmMesRef`.
- Formulario: `rm_data`, `rm_tipo`, `rm_valor_orig`, `rm_moeda`, `rm_cotacao`, `rm_valor_eur`, `rm_valor_brl`, `rm_conta`, `rm_comments`.

Rotas:

- `GET /api/receitas_mensais`
- `POST /api/receitas_mensais/sync`
- `GET /api/receitas_mensais/totais`
- `GET /api/cotacao`
- `POST /api/receitas_mensais`
- `PUT /api/receitas_mensais/<id>`
- `DELETE /api/receitas_mensais/<id>`
- `POST /export/receitas_mensais`
- `GET /api/relatorio_receitas`
- `GET /api/relatorio_receitas/exportar`

Tabelas:

- `receitas_mensais`.
- Consulta `cad_receitas` e `cad_contas`.
- Pode receber origem de `despesas_mensais`.

Funcoes:

- `get_receitas_mensais(user_email, mes=None)`.
- `add_receita_mensal(user_email, row)`.
- `update_receita_mensal(user_email, id, row)`.
- `delete_receita_mensal(user_email, id)`.
- `sync_receitas_from_despesas_mensais(user_email, mes)`.
- `get_totais_receitas(user_email, mes)`.
- `get_relatorio_receitas_v2(user_email, mes_referencia)`.

Calculos:

- `valor_eur = valor_original * cotacao`.
- `valor_brl` vem do campo da tela ou da sincronizacao.
- Sincronizacao apaga receitas do mes com `despesa_mensal_id IS NOT NULL`, busca despesas marcadas `receita=1` e insere em `receitas_mensais`.
- Totais: `SUM(valor_eur)` e `SUM(valor_brl)` por mes.
- Relatorio de receitas: agrupa por `tipo_receita` e `moeda_original`, somando `valor_original`, `valor_eur` e `valor_brl`.

### 4.6 Impostos

Arquivos:

- `modules/impostos/routes.py`
- `modules/impostos/db.py`

Tela:

- Modulo `impostosModule`.
- Campos: `imp_mes_ano`, `imp_tp_imposto`, `imp_aliquota`, `imp_pagamento`, `imp_moeda_faturado`, `imp_valor_faturado`, `imp_valor_imposto`, `imp_desconto_iva`, `imp_moeda_pagamento`, `imp_pagamento_mes_ano`.

Rotas:

- `GET/POST /api/lcto_impostos`
- `PUT/DELETE /api/lcto_impostos/<id>`
- `GET /api/dashboard_impostos`
- `GET /api/export_lcto_impostos`

Tabelas:

- `lcto_impostos`.
- Consulta `tb_tipo_imposto`.

Funcoes:

- `get_all_lcto_impostos(user_email)`.
- `add_lcto_imposto(...)`.
- `update_lcto_imposto(...)`.
- `delete_lcto_imposto(...)`.
- `get_dashboard_impostos(user_email)`.

Calculos:

- Tela calcula `valor_imposto = valor_faturado * aliquota / 100`.
- Export adiciona `Valor_Liquido = valor_imposto - desconto_iva`.
- Dashboard impostos agrupa por `tp_imposto`, `pagamento`, `pagamento_mes_ano` e acumula:
  - `total_imposto = SUM(valor_imposto)`.
  - `total_desconto = SUM(desconto_iva)`.
  - `valor_liquido = SUM(valor_imposto - COALESCE(desconto_iva, 0))`.

### 4.7 Emprestimos

Arquivos:

- `modules/emprestimos/routes.py`
- `modules/emprestimos/db.py`

Tela:

- Modulo `emprestimosModule`.
- Campos: `emp_tipo`, `emp_beneficiario`, `emp_valor_operacao`, `emp_moeda_emp`, `emp_data_emprestimo`, `emp_data_operacao`, `emp_status`, `emp_obs`.

Rotas:

- `GET/POST /api/lcto_emprestimos`
- `PUT/DELETE /api/lcto_emprestimos/<id>`
- `GET /api/lcto_emprestimos/saldo`

Tabela:

- `lcto_emprestimos`.

Funcoes:

- `get_all_lcto_emprestimos(user_email)`.
- `add_lcto_emprestimo(...)`.
- `update_lcto_emprestimo(...)`.
- `delete_lcto_emprestimo(id)`.
- `get_saldo_emprestimos(user_email)`.

Calculos:

- `total_emprestado = SUM(valor_operacao WHERE tipo = 'Empréstimo')`.
- `total_pago = SUM(valor_operacao WHERE tipo IN ('Pagamento', 'Abatimento'))`.
- `saldo = total_emprestado - total_pago`.

### 4.8 Budget

Arquivos:

- `modules/budget/routes.py`
- `modules/budget/db.py`

Tela:

- Modulo `budgetModule`.
- Ano selecionado por controles do modulo.
- Tipo ativo: `despesa` ou `receita`.
- Comparativo: `budgetCompMes`.
- Formulario: `bCategoria`, `bCustomNome`, `bMoeda`, `bVarMensal`, `bVarAnual`, `bValorReplicate`, `bJan`, `bFev`, `bMar`, `bAbr`, `bMai`, `bJun`, `bJul`, `bAgo`, `bSet`, `bOut`, `bNov`, `bDez`.
- Upload: `budgetUploadInput`.

Rotas:

- `GET/POST /api/budget`
- `GET /api/budget/summary`
- `PUT/DELETE /api/budget/<id>`
- `GET /api/budget/comparativo`
- `DELETE /api/budget/clear`
- `POST /api/budget/upload`
- `GET /api/budget/export`
- `GET /api/budget/template`

Tabela:

- `budget_items`.

Funcoes:

- `get_budget_items(user_email, ano, tipo)`.
- `get_budget_summary(user_email, ano)`.
- `get_budget_import_audit(user_email, ano, tipo)`.
- `upsert_budget_item(...)`.
- `update_budget_item(...)`.
- `delete_budget_item(...)`.
- `delete_budget_year(user_email, ano, tipo=None)`.
- `get_comparativo(user_email, mes_ano)`.
- `bulk_upsert_budget(...)`.
- `bulk_replace_budget(...)`.

Calculos:

- Total anual por item: soma dos 12 campos mensais.
- Resumo anual: soma dos 12 meses agrupada por `tipo`.
- Comparativo:
  - Seleciona coluna mensal conforme `mes_ano`: `valor_jan` ... `valor_dez`.
  - Real de despesa: `SUM(despesas_mensais.valor_eur)` por `categoria_final`.
  - Real de receita: `SUM(receitas_mensais.valor_eur)` por `tipo_receita`.
  - Match por texto normalizado lower/trim entre categoria do budget e categoria real.
  - Na tela, `desvio = real - budget`.
  - `desvioPct = budget != 0 ? desvio / budget * 100 : null`.
  - Para despesas, acima do budget e alerta quando `desvio > 0`; para receitas, alerta quando `desvio < 0`.

### 4.9 Lancamentos de Investimentos

Arquivos:

- `modules/investimentos/routes.py`
- `modules/investimentos/db.py`

Tela:

- Modulo `lctoInvestimentosModule`.
- Campos: `li_banco`, `li_tp_investimento`, `li_data_inv`, `li_moeda`, `li_valor_inv`, `li_qtd`, `li_taxa`, `li_aporte`, `li_valor_atual`, `li_val_mes_ant`, `li_valor_tot_inv`, `li_valor_liq_mes`.
- Upload: `li_file`.

Rotas:

- `GET/POST /api/lcto_investimentos`
- `PUT/DELETE /api/lcto_investimentos/<id>`
- `POST /api/upload_lcto_investimentos`
- `GET /api/export_lcto_investimentos`

Tabela:

- `lcto_investimentos`.

Funcoes:

- `get_all_lcto_investimentos(user_email)`.
- `add_lcto_investimento(...)`.
- `update_lcto_investimento(...)`.
- `delete_lcto_investimento(id)`.
- `clear_lcto_investimentos(user_email)`.

Calculos:

- `valor_tot_inv = valor_inv * qtd`.
- `valor_liq_mes = valor_atual - (valor_tot_inv + taxa)`.
- `lucro_mes = valor_atual - val_mes_ant`.
- `lucro_op = valor_atual - valor_tot_inv`.
- `pct_rent = lucro_op / valor_tot_inv * 100`, se `valor_tot_inv > 0`.

### 4.10 Trader

Arquivos:

- `modules/trader/routes.py`
- `modules/trader/db.py`

Tela:

- Modulo `traderModule`.
- Filtros: `traderPeriodoFilter`, `traderContaFilter`.
- Formulario: `trader_periodo`, `trader_conta`, `trader_symbol`, `trader_type`, `trader_volume`, `trader_open_time`, `trader_open_price`, `trader_close_time`, `trader_close_price`, `trader_sl`, `trader_tp`, `trader_margin`, `trader_commission`, `trader_swap`, `trader_rollover`, `trader_gross_pl`.
- Upload: `trader_upload_conta`, `trader_upload_periodo`, `trader_file`.

Rotas:

- `GET/POST /api/trader_positions`
- `PUT/DELETE /api/trader_positions/<id>`
- `POST /api/trader_positions/clear`
- `GET /api/trader_periodos`
- `GET /api/trader_contas`
- `POST /api/upload_trader_positions`
- `GET /api/export_trader_positions`

Tabela:

- `trader_positions`.

Funcoes:

- `get_all_trader_positions(user_email, periodo=None)`.
- `add_trader_position(...)`.
- `update_trader_position(...)`.
- `delete_trader_position(id)`.
- `clear_trader_positions(user_email=None, periodo=None)`.
- `get_trader_periodos(user_email)`.
- `get_trader_contas(user_email)`.

Regras de importacao:

- Exige `conta_bancaria` e `periodo`.
- Detecta header quando `symbol`, `type`, `volume` nao aparecem nas colunas originais.
- Normaliza colunas para lowercase e underscore.
- Normaliza tipo: `buy`, `long`, `b` para `Buy`; `sell`, `short`, `s` para `Sell`.
- Converte numericos com `safe_float`.

Calculos:

- O modulo armazena `gross_pl` informado/importado.
- Dashboard P&L soma `gross_pl` por `symbol`.

### 4.11 Dashboard

Arquivos:

- `modules/dashboard/routes.py`
- `modules/dashboard/db.py`

Tela:

- Modulo `dashboardModule`.
- Periodo: `dashMesRef`.

Rotas:

- `GET /api/dashboard_data`
- `GET /api/dashboard/overview`
- `GET /api/dashboard/despesas`
- `GET /api/dashboard/receitas`
- `GET /api/dashboard/budget`
- `GET /api/dashboard/investimentos`
- `GET /api/dashboard/pnl`
- `GET /api/dashboard/fluxo-caixa`
- `GET /api/dashboard/patrimonio`
- `GET /api/relatorio_anual`
- `GET /api/relatorio_anual_despesas`
- `GET /api/relatorio_anual_receitas`
- `GET /api/relatorio_anual_despesas/exportar`
- `GET /api/relatorio_anual_receitas/exportar`

Tabelas:

- `despesas_mensais`
- `receitas_mensais`
- `budget_items`
- `lcto_investimentos`
- `lcto_emprestimos`
- `trader_positions`
- `despesas_anuais`
- `cad_despesas`
- `cad_usuarios`

Funcoes e calculos:

#### `get_dashboard_data(user_email, mes_referencia)`

Uso: dashboard antigo/simples.

- `expenses_by_category`: despesas do mes por `categoria_final`, usando `receita=0`.
- `revenues_by_category`: receitas do mes armazenadas em `despesas_mensais`, usando `receita=1`.
- `annual_net`: no ano do mes selecionado, `SUM(receita=1 valor_eur) - SUM(receita=0 valor_eur)`.

#### `_monthly_expenses(conn, user_email, mes)`

- Total de despesas do mes: `SUM(valor_eur)` em `despesas_mensais` onde `receita IS NULL OR receita=0`.

#### `_monthly_revenues(conn, user_email, mes)`

Total de receitas do mes:

- `SUM(receitas_mensais.valor_eur)` do mes.
- Mais receitas em `despesas_mensais` com `receita=1` que ainda nao existem em `receitas_mensais` via `despesa_mensal_id`.

Esta regra evita dupla contagem quando uma receita foi sincronizada da despesa mensal para `receitas_mensais`.

#### `_investment_summary(conn, user_email)`

- `valor_atual = SUM(valor_atual)`.
- `valor_investido = SUM(valor_inv * qtd)`.
- `taxas = SUM(taxa)`.
- `aportes = SUM(aporte)`.
- `pnl = valor_atual - valor_investido - taxas`.
- `pnl_pct = pnl / valor_investido * 100`, se houver valor investido.

#### `_debt_summary(conn, user_email)`

- `total_emprestado = SUM(valor_operacao WHERE tipo='Empréstimo')`.
- `total_pago = SUM(valor_operacao WHERE tipo IN ('Pagamento', 'Abatimento'))`.
- `saldo = total_emprestado - total_pago`.

#### `_cash_balance_until(conn, user_email, mes)`

Caixa estimado ate o mes:

- `receitas acumuladas ate mes - despesas acumuladas ate mes`.
- Receitas seguem a mesma regra de `_monthly_revenues`, incluindo receitas em `despesas_mensais` ainda nao sincronizadas.

#### `get_dashboard_expenses(user_email, mes, ano)`

Retorna:

- `total`: soma por categoria.
- `by_category`: `SUM(valor_eur)` por `categoria_final`.
- `by_account`: `SUM(valor_eur)` por `conta_bancaria`.
- `monthly`: totais mensais do ano.
- `top_transactions`: 8 maiores despesas do mes por `valor_eur`.

Filtro:

- `receita IS NULL OR receita=0`.

#### `get_dashboard_revenues(user_email, mes, ano)`

Retorna:

- `total`: soma por tipo.
- `media_mensal`: media somente dos meses com valor maior que zero.
- `by_type`: `SUM(valor_eur)` por `tipo_receita`.
- `monthly`: totais mensais do ano.
- `top_transactions`: 8 maiores receitas do mes.

#### `get_dashboard_budget(user_email, mes, ano)`

Retorna:

- Linhas por item de budget com `budget`, `real`, `diff`, `used_pct`.
- Summary:
  - `despesas_budget`
  - `despesas_real`
  - `receitas_budget`
  - `receitas_real`
  - `saldo_budget = receitas_budget - despesas_budget`
  - `saldo_real = receitas_real - despesas_real`
  - `despesas_used_pct = despesas_real / despesas_budget * 100`

Match:

- Despesas reais por `categoria_final`.
- Receitas reais por `tipo_receita`.
- Chave normalizada por lower/trim.

#### `get_dashboard_investments(user_email, mes, ano)`

Retorna:

- `summary`: resultado de `_investment_summary`.
- `by_type`: `SUM(valor_atual)` e `SUM(valor_inv*qtd)` por `tp_investimento`.
- `by_bank`: `SUM(valor_atual)` por banco.
- `positions`: top 10 por `valor_atual`, com `pnl = valor_atual - valor_inv*qtd - taxa`.

#### `get_dashboard_pnl(user_email, mes, ano)`

Retorna:

- Investimentos: P&L por `tp_investimento`.
- Trader: `SUM(gross_pl)` por `symbol`, filtrado por `periodo = mes` ou datas `open_time`/`close_time` iniciando pelo mes.
- Summary:
  - `pnl_investimentos`
  - `pnl_trader`
  - `pnl_total`
- `top_gains`: 5 maiores P&Ls.
- `top_losses`: 5 menores P&Ls.

#### `get_dashboard_cashflow(user_email, ano)`

Para cada mes do ano:

- `receitas = _monthly_revenues(...)`.
- `despesas = _monthly_expenses(...)`.
- `saldo_mes = receitas - despesas`.
- `saldo_acumulado`: soma acumulada dos saldos mensais.

Summary:

- `receitas`: soma anual.
- `despesas`: soma anual.
- `saldo`: soma de todos os `saldo_mes`.
- `menor_saldo`: menor `saldo_acumulado`.

#### `get_dashboard_net_worth(user_email, mes, ano)`

Patrimonio liquido estimado:

- `investimentos = valor_atual dos investimentos`.
- `caixa_estimado = _cash_balance_until(...)`.
- `dividas = saldo de emprestimos`.
- `patrimonio_liquido = investimentos + caixa_estimado - dividas`.

Serie mensal:

- Para cada mes do ano, acumula fluxo de caixa desde janeiro e calcula:
- `patrimonio_estimado = investimentos.valor_atual + saldo_acumulado - dividas.saldo`.

#### `get_dashboard_overview(user_email, mes, ano)`

KPIs:

- `receitas = _monthly_revenues(...)`.
- `despesas = _monthly_expenses(...)`.
- `saldo = receitas - despesas`.
- `budget_usado_pct = despesas / budget_despesas * 100`.
- `budget_despesas` e `budget_receitas` vem da coluna mensal do budget.
- `investimentos = valor_atual`.
- `pnl = investimentos.pnl`.
- `patrimonio_liquido = investimentos.valor_atual + caixa - dividas.saldo`.
- `dividas = saldo de emprestimos`.

Insights:

- Despesas acima/dentro do budget.
- P&L de investimentos negativo/positivo.
- Saldo do mes negativo.
- Sem dados suficientes se nenhuma regra disparar.

#### Relatorios anuais

`get_annual_report(user_email, ano)`:

- Le `despesas_anuais`.
- Ordena por `total_geral DESC`.

`get_relatorio_anual_despesas(user_email, ano)`:

- Usa categorias cadastradas em `cad_despesas`.
- Usa nomes de `cad_usuarios` para USR1/USR2.
- Agrupa `despesas_mensais` por `categoria_final`, `mes_referencia`, `moeda`, somente `receita=0`.
- Soma `usr1`, `usr2` e `valor_original`.
- Media anual por categoria/moeda: `total / 12`.

`get_relatorio_anual_receitas(user_email, ano)`:

- Agrupa `receitas_mensais` por `tipo_receita`, `mes_referencia`, `moeda_original`.
- Soma `valor_original`.
- Media anual por tipo/moeda: `total / 12`.

### 4.12 Relatorios Dinamicos

Arquivos:

- `modules/relatorios/routes.py`
- `modules/relatorios/db.py`

Tela:

- Modulo `relatorioDinamicoModule`.
- Campos: `relDinNome`, `relDinMesInicio`, `relDinMesFim`, moedas `rel-din-moeda`, `relDinAgrupador`.
- Tabelas/campos selecionados por cards e checkboxes gerados dinamicamente.

Rotas:

- `GET /api/relatorio_dinamico/tabelas`
- `GET /api/relatorio_dinamico`
- `POST /api/relatorio_dinamico`
- `DELETE /api/relatorio_dinamico/<id>`
- `POST /api/relatorio_dinamico/gerar`
- `GET /api/relatorio_dinamico/meses`
- `POST /api/relatorio_dinamico/exportar`

Tabelas:

- `relatorios_configurados`.
- Consulta dinamica:
  - `despesas_mensais`
  - `receitas_mensais`
  - `lcto_impostos`
  - `lcto_emprestimos`
  - `lcto_investimentos`
  - `cad_despesas`
  - `cad_contas`
  - `cad_receitas`
  - `cad_investimentos`
  - `cad_usuarios`
  - `tb_tipo_imposto`

Funcoes:

- `save_relatorio_dinamico(...)`: salva config em JSON text.
- `get_all_relatorios_dinamicos(user_email)`: lista configs e desserializa JSON.
- `delete_relatorio_dinamico(user_email, id)`: remove config.
- `get_tabelas_campos()`: retorna campos permitidos por tabela.
- `get_dados_relatorio_dinamico(...)`: monta dados agregados por periodo, agrupador e moeda.

Calculos:

- Periodo: gera lista mensal de `mes_inicio` ate `mes_fim`.
- Despesas: agrupa por `categoria_final`, `mes_referencia`, `moeda`; soma `valor_original` e `valor_eur`.
- Receitas: agrupa por `tipo_receita`, `mes_referencia`, `moeda_original`; soma `valor_original`, `valor_eur`, `valor_brl`.
- Impostos: agrupa por `tp_imposto`, `pagamento_mes_ano`, moedas; soma `valor_imposto` e `valor_faturado`.
- Emprestimos: agrupa por `beneficiario` e mes de `data_operacao`.
- Investimentos: agrupa por `banco - tp_investimento` e mes de `data_inv`, usando `valor_atual` ou `valor_inv`.
- Totais:
  - `total_por_agrupador[agr][moeda] = soma de todos os meses`.
  - `total_geral[mes][moeda] = soma de todos os agrupadores no mes`.

## 5. Fluxo dos Campos das Telas

Esta secao ajuda a localizar de onde vem o valor de cada campo importante.

### 5.1 Campos vindos de cadastros

- `dm_cat`: vem de `GET /api/cad_despesas`, tabela `cad_despesas`.
- `dm_conta`: vem de `GET /api/cad_contas`, tabela `cad_contas`.
- `rm_tipo`: vem de `GET /api/cad_receitas`, tabela `cad_receitas`.
- `rm_conta`: vem de `GET /api/cad_contas`, tabela `cad_contas`.
- `imp_tp_imposto`: vem de `GET /api/cad_tipo_imposto`, tabela `tb_tipo_imposto`.
- `li_banco`: vem de `GET /api/cad_contas`, tabela `cad_contas`.
- `li_tp_investimento`: vem de `GET /api/cad_investimentos`, tabela `cad_investimentos`.
- `trader_conta` e `trader_upload_conta`: vem de `GET /api/cad_contas`, tabela `cad_contas`.
- `bCategoria`: vem de `GET /api/cad_despesas` ou `GET /api/cad_receitas`, conforme aba budget.

### 5.2 Campos calculados na tela

- `dm_valor_eur`: calculado de `dm_valor_orig * dm_cambio`.
- Diferenca de despesas: comparacao entre `dm_valor_orig` e soma `dm_usr1 + dm_usr2`.
- `rm_valor_eur`: calculado de `rm_valor_orig * rm_cotacao`.
- `imp_valor_imposto`: calculado de `imp_valor_faturado * aliquota / 100`.
- `li_valor_tot_inv`: calculado de `li_valor_inv * li_qtd`.
- `li_valor_liq_mes`: calculado de `li_valor_atual - (li_valor_tot_inv + li_taxa)`.
- Budget total anual: soma `bJan` a `bDez`.
- Budget replicar: `bValorReplicate` preenche os 12 meses.

### 5.3 Campos importados de arquivo

- Extratos: `fileInput`, arquivos PDF/CSV/XLS/XLSX/XML, parser detecta colunas de data, descricao, valor e moeda.
- Cadastro despesas: `cd_file`, parser `process_despesas_file()`.
- Cadastros simples: `cc_file`, `cr_file`, `ci_file`, `cu_file`, `cti_file`, tratados em `modules/cadastros/routes.py`.
- Despesas mensais: `dm_file`, usa parser de extratos/despesas mensais e confirmacao.
- Budget: `budgetUploadInput`, interpreta colunas de categoria, meses, variacoes e moeda.
- Investimentos: `li_file`, importa banco, tipo, data, valores, quantidade, taxa, valor atual, mes anterior e aporte.
- Trader: `trader_file`, importa posicoes com symbol, type, volume, open/close, SL, TP, margin, commission, swap, rollover e gross P/L.

## 6. Mapa de Rotas por Modulo

### Autenticacao

- `/`
- `/api/me`
- `/register`
- `/login`
- `/forgot-password`
- `/reset-password`
- `/logout`
- `/api/limpar_dados`
- `/api/limpar_configuracoes`

### Extratos

- `/upload`
- `/save_category`
- `/export`

### Cadastros

- `/api/cad_despesas`
- `/api/cad_despesas/<id>`
- `/api/cad_despesas/upload`
- `/api/cad_despesas/export`
- `/api/cad_contas`
- `/api/cad_contas/<id>`
- `/api/cad_contas/<id>/senha`
- `/api/upload_contas`
- `/api/export_contas`
- `/api/cad_receitas`
- `/api/cad_receitas/<id>`
- `/api/upload_receitas`
- `/api/export_receitas`
- `/api/cad_investimentos`
- `/api/cad_investimentos/<id>`
- `/api/upload_investimentos`
- `/api/export_investimentos`
- `/api/cad_usuarios`
- `/api/cad_usuarios/<id>`
- `/api/upload_usuarios`
- `/api/export_usuarios`
- `/api/cad_tipo_imposto`
- `/api/cad_tipo_imposto/<id>`
- `/api/upload_tipo_imposto`
- `/api/export_tipo_imposto`

### Despesas Mensais

- `/api/despesas_mensais/check_duplicates`
- `/api/despesas_mensais`
- `/api/despesas_mensais/batch`
- `/api/despesas_mensais/<id>`
- `/api/despesas_mensais/batch_delete`
- `/api/despesas_mensais/clear`
- `/api/despesas_mensais/meses`
- `/api/despesas_mensais/upload`
- `/api/despesas_mensais/upload_confirm`
- `/api/despesas_mensais/consolidacao`
- `/api/despesas_anuais/consolidar`
- `/export/despesas_mensais`
- `/export/consolidacao`
- `/api/relatorio_mensal`
- `/api/relatorio_mensal/exportar`

### Receitas Mensais

- `/api/receitas_mensais`
- `/api/receitas_mensais/sync`
- `/api/receitas_mensais/totais`
- `/api/cotacao`
- `/api/receitas_mensais/<id>`
- `/export/receitas_mensais`
- `/api/relatorio_receitas`
- `/api/relatorio_receitas/exportar`

### Impostos

- `/api/lcto_impostos`
- `/api/lcto_impostos/<id>`
- `/api/dashboard_impostos`
- `/api/export_lcto_impostos`

### Emprestimos

- `/api/lcto_emprestimos`
- `/api/lcto_emprestimos/<id>`
- `/api/lcto_emprestimos/saldo`

### Budget

- `/api/budget`
- `/api/budget/summary`
- `/api/budget/<id>`
- `/api/budget/comparativo`
- `/api/budget/clear`
- `/api/budget/upload`
- `/api/budget/export`
- `/api/budget/template`

### Investimentos

- `/api/lcto_investimentos`
- `/api/lcto_investimentos/<id>`
- `/api/upload_lcto_investimentos`
- `/api/export_lcto_investimentos`

### Trader

- `/api/trader_positions`
- `/api/trader_positions/<id>`
- `/api/trader_positions/clear`
- `/api/trader_periodos`
- `/api/trader_contas`
- `/api/upload_trader_positions`
- `/api/export_trader_positions`

### Dashboard

- `/api/dashboard_data`
- `/api/dashboard/overview`
- `/api/dashboard/despesas`
- `/api/dashboard/receitas`
- `/api/dashboard/budget`
- `/api/dashboard/investimentos`
- `/api/dashboard/pnl`
- `/api/dashboard/fluxo-caixa`
- `/api/dashboard/patrimonio`
- `/api/relatorio_anual`
- `/api/relatorio_anual_despesas`
- `/api/relatorio_anual_receitas`
- `/api/relatorio_anual_despesas/exportar`
- `/api/relatorio_anual_receitas/exportar`

### Relatorios Dinamicos

- `/api/relatorio_dinamico/tabelas`
- `/api/relatorio_dinamico`
- `/api/relatorio_dinamico/<id>`
- `/api/relatorio_dinamico/gerar`
- `/api/relatorio_dinamico/meses`
- `/api/relatorio_dinamico/exportar`

## 7. Checklist para Especificar uma Correcao

Ao pedir uma correcao, idealmente informe:

1. Tela/modulo: exemplo `Despesas Mensais`.
2. Campo visual: exemplo `dm_valor_eur`.
3. Rota envolvida: exemplo `POST /api/despesas_mensais`.
4. Tabela/campo salvo: exemplo `despesas_mensais.valor_eur`.
5. Funcao envolvida: exemplo `add_despesa_mensal()`.
6. Calculo esperado: exemplo `valor_eur = valor_original * cambio_eur`.
7. Exemplo real: valores de entrada e resultado esperado.

Modelo curto:

```text
Modulo: Despesas Mensais
Tela/campo: dm_valor_eur
Rota: POST /api/despesas_mensais
Tabela/campo: despesas_mensais.valor_eur
Funcao: add_despesa_mensal
Problema: ao usar valor_original=100 e cambio_eur=0.18, salva 100 em vez de 18.
Esperado: salvar 18.00.
```

## 8. Pontos de Atencao Tecnica

- `database.py` e `parser_utils.py` ainda existem como legado; a aplicacao atual usa os modulos em `modules/`.
- `supabase_schema.sql` nao contem `budget_items`, embora o modulo crie a tabela.
- Alguns deletes/updates em `investimentos` e `trader` usam apenas `id` no DB, enquanto as rotas verificam sessao. Se houver usuarios diferentes, pode ser interessante restringir tambem por `user_email`.
- Relatorios dinamicos consultam alguns cadastros sem filtro `user_email` em `get_dados_relatorio_dinamico()` para tabelas `cad_*` e `tb_tipo_imposto`. Se isso for indesejado, corrigir filtrando por usuario.
- `categorias_aprendidas` e global; limpar dados do usuario apaga todas as categorias aprendidas.
- Receitas podem existir em dois lugares: `receitas_mensais` e `despesas_mensais` com `receita=1`. Dashboards novos evitam dupla contagem usando `despesa_mensal_id`.
- Campos `usr1` e `usr2` em `despesas_mensais` sao texto no schema original, mas usados como numericos em somatorios com cast em alguns relatorios.
