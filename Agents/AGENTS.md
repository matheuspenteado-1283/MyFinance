# MyFinance 2.0 — Guia de Reestruturação Modular

## Visão Geral do Projeto

**MyFinance** é um gerenciador pessoal de finanças construído com Flask + SQLite + Pandas. Ele processa extratos bancários de múltiplos países/formatos, categoriza transações, consolida lançamentos mensais por usuário e gera relatórios financeiros.

**Stack atual:** Python 3, Flask, SQLite (`extratos.db`), Pandas, openpyxl, pdfplumber, BeautifulSoup, Frankfurter API (câmbio).

---

## Estado Atual — Estrutura Monolítica

```
MyFinance 2.0/
├── app.py              # 1.443 linhas — todas as rotas Flask em um único arquivo
├── database.py         # 1.336 linhas — todas as funções de DB em um único arquivo
├── parser_utils.py     # 320 linhas  — parsers de extratos bancários
├── exchange_api.py     # 45 linhas   — cotações de câmbio (Frankfurter API)
├── requirements.txt
├── templates/
│   └── index.html      # SPA única (não mexer)
├── static/
│   └── css/style.css   # Estilos (não mexer)
├── uploads/            # Pasta de arquivos temporários (runtime)
├── MyFinance/          # Arquivos de dados de amostra (não mexer)
├── Skills/             # Skills de apoio ao Codex (não mexer)
└── extratos.db         # Banco de dados SQLite (não mexer — migrar dados, não recriar)
```

**Problemas da estrutura atual:**
- `app.py` e `database.py` crescem sem limites — qualquer nova feature aumenta arquivos já enormes
- Impossível trabalhar em isolamento em um módulo sem abrir arquivos com >1000 linhas
- Sem separação de responsabilidades entre rotas, lógica de negócio e acesso a dados
- Dependências circulares ocultas (database.py chama werkzeug, json, etc. diretamente)

---

## Arquitetura Alvo — Modular por Domínio

### Regra principal: **nenhuma funcionalidade é alterada**, apenas reorganização de código.

```
MyFinance 2.0/
├── app.py                  # Ponto de entrada — apenas cria o Flask app e registra Blueprints
├── config.py               # Configurações centralizadas (secret_key, upload folder, extensões)
├── exchange_api.py         # Inalterado
├── requirements.txt        # Inalterado
│
├── db/
│   ├── __init__.py         # Expõe get_connection() e init_all()
│   ├── connection.py       # get_connection() — única fonte de conexão SQLite
│   └── init.py             # Chama init de cada módulo para criar tabelas
│
├── modules/
│   ├── auth/
│   │   ├── __init__.py     # Blueprint registration
│   │   ├── routes.py       # POST /login, POST /register, POST /logout, GET /api/me
│   │   └── db.py           # register_user, verify_user, get_user_by_email, limpar_dados_usuario
│   │
│   ├── extratos/
│   │   ├── __init__.py
│   │   ├── routes.py       # POST /upload, POST /export, POST /save_category
│   │   ├── parser.py       # process_file, _df_to_transactions (todo o conteúdo de parser_utils.py)
│   │   └── db.py           # save_category_rule, guess_category
│   │
│   ├── cadastros/
│   │   ├── __init__.py
│   │   ├── routes.py       # Rotas /api/cad_* para todos os cadastros
│   │   └── db/
│   │       ├── despesas.py         # get_all_despesas, add_despesa, update_despesa, delete_despesa, overwrite_despesas, clear_despesas
│   │       ├── contas.py           # get_all_contas, add_conta, update_conta, delete_conta, clear_contas, get_senha_conta
│   │       ├── receitas.py         # get_all_receitas, add_receita, update_receita, delete_receita, clear_receitas
│   │       ├── investimentos.py    # get_all_investimentos, add_investimento, update_investimento, delete_investimento, clear_investimentos
│   │       ├── usuarios.py         # get_all_usuarios, add_usuario, update_usuario, delete_usuario, clear_usuarios
│   │       └── tipo_imposto.py     # get_all_tipo_imposto, add_tipo_imposto, update_tipo_imposto, delete_tipo_imposto, clear_tipo_imposto
│   │
│   ├── despesas_mensais/
│   │   ├── __init__.py
│   │   ├── routes.py       # Rotas /api/despesas_mensais/*, /export/despesas_mensais, /export/consolidacao
│   │   └── db.py           # get_despesas_mensais, save_despesas_mensais_batch, add_despesa_mensal,
│   │                       # update_despesa_mensal, delete_despesa_mensal, delete_despesas_mensais_batch,
│   │                       # clear_despesas_mensais, consolidar_despesas_anuais, get_consolidacao_tipo_despesa
│   │
│   ├── receitas_mensais/
│   │   ├── __init__.py
│   │   ├── routes.py       # Rotas /api/receitas_mensais/*, /export/receitas_mensais
│   │   └── db.py           # get_receitas_mensais, add_receita_mensal, update_receita_mensal,
│   │                       # delete_receita_mensal, sync_receitas_from_despesas_mensais, get_totais_receitas
│   │
│   ├── impostos/
│   │   ├── __init__.py
│   │   ├── routes.py       # Rotas /api/lcto_impostos/*, /api/dashboard_impostos, /api/export_lcto_impostos
│   │   └── db.py           # get_all_lcto_impostos, add_lcto_imposto, update_lcto_imposto,
│   │                       # delete_lcto_imposto, get_dashboard_impostos
│   │
│   ├── emprestimos/
│   │   ├── __init__.py
│   │   ├── routes.py       # Rotas /api/lcto_emprestimos/*
│   │   └── db.py           # get_all_lcto_emprestimos, add_lcto_emprestimo, update_lcto_emprestimo,
│   │                       # delete_lcto_emprestimo, get_saldo_emprestimos
│   │
│   ├── investimentos/
│   │   ├── __init__.py
│   │   ├── routes.py       # Rotas /api/lcto_investimentos/*, /api/upload_lcto_investimentos, /api/export_lcto_investimentos
│   │   └── db.py           # get_all_lcto_investimentos, add_lcto_investimento, update_lcto_investimento,
│   │                       # delete_lcto_investimento, clear_lcto_investimentos
│   │
│   ├── trader/
│   │   ├── __init__.py
│   │   ├── routes.py       # Rotas /api/trader_positions/*, /api/upload_trader_positions, /api/export_trader_positions
│   │   └── db.py           # get_all_trader_positions, add_trader_position, update_trader_position,
│   │                       # delete_trader_position, clear_trader_positions, get_trader_periodos, get_trader_contas
│   │
│   ├── dashboard/
│   │   ├── __init__.py
│   │   ├── routes.py       # GET /api/dashboard_data, GET /api/relatorio_anual, POST /api/despesas_anuais/consolidar
│   │   └── db.py           # get_dashboard_data, get_annual_report
│   │
│   └── relatorios/
│       ├── __init__.py
│       ├── routes.py       # Rotas /api/relatorio_dinamico/*
│       └── db.py           # save_relatorio_dinamico, get_all_relatorios_dinamicos,
│                           # delete_relatorio_dinamico, get_dados_relatorio_dinamico, get_tabelas_campos
│
├── templates/
│   └── index.html          # Inalterado
├── static/
│   └── css/style.css       # Inalterado
├── uploads/                # Runtime — criar com os.makedirs no config.py
└── extratos.db             # Inalterado — banco de dados existente
```

---

## Regras de Implementação

### O que NÃO pode mudar
1. **Todas as URLs das rotas** — o frontend (`index.html`) chama essas rotas diretamente e não será alterado
2. **Schema do banco de dados** — nenhuma tabela, coluna ou constraint deve ser modificada
3. **Comportamento das funções** — lógica de negócio, cálculos e respostas JSON idênticos
4. **Arquivos `templates/index.html` e `static/css/style.css`** — não tocar
5. **`exchange_api.py`** — já está bem isolado, apenas mover para importação correta nos módulos
6. **`extratos.db`** — banco existente com dados reais do usuário

### O que DEVE mudar
1. Cada módulo em `modules/` tem seu próprio Blueprint Flask
2. `db/connection.py` é a única fonte de `get_connection()` — nenhum módulo cria conexão própria
3. `app.py` vira ponto de entrada limpo: cria `Flask`, registra todos os Blueprints, inicia servidor
4. `config.py` centraliza `SECRET_KEY`, `UPLOAD_FOLDER`, `MAX_CONTENT_LENGTH`, `ALLOWED_EXTENSIONS`
5. Cada `db.py` de módulo importa `get_connection` apenas de `db.connection`
6. `db/init.py` chama `init_db()` de cada módulo que precisa criar tabelas

### Padrão de Blueprint

```python
# modules/auth/__init__.py
from flask import Blueprint
bp = Blueprint('auth', __name__)
from . import routes  # noqa

# modules/auth/routes.py
from . import bp
from .db import register_user, verify_user
from flask import request, jsonify, session

@bp.route('/login', methods=['POST'])
def login():
    ...
```

### Padrão de db.py por módulo

```python
# modules/auth/db.py
from db.connection import get_connection
from werkzeug.security import generate_password_hash, check_password_hash

def register_user(email: str, password: str) -> bool:
    conn = get_connection()
    ...
```

### app.py final (ponto de entrada)

```python
from flask import Flask
from config import configure_app
from db import init_all

from modules.auth import bp as auth_bp
from modules.extratos import bp as extratos_bp
from modules.cadastros import bp as cadastros_bp
from modules.despesas_mensais import bp as despesas_mensais_bp
from modules.receitas_mensais import bp as receitas_mensais_bp
from modules.impostos import bp as impostos_bp
from modules.emprestimos import bp as emprestimos_bp
from modules.investimentos import bp as investimentos_bp
from modules.trader import bp as trader_bp
from modules.dashboard import bp as dashboard_bp
from modules.relatorios import bp as relatorios_bp

def create_app():
    app = Flask(__name__)
    configure_app(app)
    init_all()
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(extratos_bp)
    app.register_blueprint(cadastros_bp)
    app.register_blueprint(despesas_mensais_bp)
    app.register_blueprint(receitas_mensais_bp)
    app.register_blueprint(impostos_bp)
    app.register_blueprint(emprestimos_bp)
    app.register_blueprint(investimentos_bp)
    app.register_blueprint(trader_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(relatorios_bp)
    
    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, port=5001)
```

---

## Mapeamento de Funções — Origem → Destino

### De `database.py`

| Função atual | Módulo destino | Arquivo destino |
|---|---|---|
| `get_connection()` | `db/` | `db/connection.py` |
| `init_db()` | `db/` | `db/init.py` |
| `save_category_rule()` | `modules/extratos/` | `db.py` |
| `guess_category()` | `modules/extratos/` | `db.py` |
| `register_user()`, `verify_user()`, `get_user_by_email()` | `modules/auth/` | `db.py` |
| `limpar_dados_usuario()` | `modules/auth/` | `db.py` |
| `get_all_despesas()`, `add_despesa()`, `update_despesa()`, `delete_despesa()`, `overwrite_despesas()`, `clear_despesas()` | `modules/cadastros/` | `db/despesas.py` |
| `get_all_contas()`, `add_conta()`, `update_conta()`, `delete_conta()`, `clear_contas()`, `get_senha_conta()` | `modules/cadastros/` | `db/contas.py` |
| `get_all_receitas()`, `add_receita()`, `update_receita()`, `delete_receita()`, `clear_receitas()` | `modules/cadastros/` | `db/receitas.py` |
| `get_all_investimentos()`, `add_investimento()`, `update_investimento()`, `delete_investimento()`, `clear_investimentos()` | `modules/cadastros/` | `db/investimentos.py` |
| `get_all_usuarios()`, `add_usuario()`, `update_usuario()`, `delete_usuario()`, `clear_usuarios()` | `modules/cadastros/` | `db/usuarios.py` |
| `get_all_tipo_imposto()`, `add_tipo_imposto()`, `update_tipo_imposto()`, `delete_tipo_imposto()`, `clear_tipo_imposto()` | `modules/cadastros/` | `db/tipo_imposto.py` |
| `get_despesas_mensais()`, `save_despesas_mensais_batch()`, `add_despesa_mensal()`, `update_despesa_mensal()`, `delete_despesa_mensal()`, `delete_despesas_mensais_batch()`, `clear_despesas_mensais()`, `consolidar_despesas_anuais()`, `get_consolidacao_tipo_despesa()` | `modules/despesas_mensais/` | `db.py` |
| `get_receitas_mensais()`, `add_receita_mensal()`, `update_receita_mensal()`, `delete_receita_mensal()`, `sync_receitas_from_despesas_mensais()`, `get_totais_receitas()` | `modules/receitas_mensais/` | `db.py` |
| `get_all_tipo_imposto()`, `get_all_lcto_impostos()`, `add_lcto_imposto()`, `update_lcto_imposto()`, `delete_lcto_imposto()`, `get_dashboard_impostos()` | `modules/impostos/` | `db.py` |
| `get_all_lcto_emprestimos()`, `add_lcto_emprestimo()`, `update_lcto_emprestimo()`, `delete_lcto_emprestimo()`, `get_saldo_emprestimos()` | `modules/emprestimos/` | `db.py` |
| `get_all_lcto_investimentos()`, `add_lcto_investimento()`, `update_lcto_investimento()`, `delete_lcto_investimento()`, `clear_lcto_investimentos()` | `modules/investimentos/` | `db.py` |
| `get_all_trader_positions()`, `add_trader_position()`, `update_trader_position()`, `delete_trader_position()`, `clear_trader_positions()`, `get_trader_periodos()`, `get_trader_contas()` | `modules/trader/` | `db.py` |
| `get_dashboard_data()`, `get_annual_report()` | `modules/dashboard/` | `db.py` |
| `save_relatorio_dinamico()`, `get_all_relatorios_dinamicos()`, `delete_relatorio_dinamico()`, `get_dados_relatorio_dinamico()`, `get_tabelas_campos()` | `modules/relatorios/` | `db.py` |

### De `app.py`

| Rotas atuais | Blueprint destino |
|---|---|
| `/`, (render index) | `modules/auth/routes.py` ou `app.py` direto |
| `/login`, `/register`, `/logout`, `/api/me` | `modules/auth/routes.py` |
| `/upload`, `/export`, `/save_category` | `modules/extratos/routes.py` |
| `/api/cad_despesas`, `/api/cad_contas`, `/api/cad_receitas`, `/api/cad_investimentos`, `/api/cad_usuarios`, `/api/cad_tipo_imposto` + upload/export de cada | `modules/cadastros/routes.py` |
| `/api/despesas_mensais/*`, `/export/despesas_mensais`, `/export/consolidacao` | `modules/despesas_mensais/routes.py` |
| `/api/receitas_mensais/*`, `/export/receitas_mensais`, `/api/cotacao` | `modules/receitas_mensais/routes.py` |
| `/api/lcto_impostos/*`, `/api/dashboard_impostos`, `/api/export_lcto_impostos` | `modules/impostos/routes.py` |
| `/api/lcto_emprestimos/*` | `modules/emprestimos/routes.py` |
| `/api/lcto_investimentos/*`, `/api/upload_lcto_investimentos`, `/api/export_lcto_investimentos` | `modules/investimentos/routes.py` |
| `/api/trader_positions/*`, `/api/trader_periodos`, `/api/trader_contas`, `/api/upload_trader_positions`, `/api/export_trader_positions` | `modules/trader/routes.py` |
| `/api/dashboard_data`, `/api/relatorio_anual`, `/api/despesas_anuais/consolidar` | `modules/dashboard/routes.py` |
| `/api/relatorio_dinamico/*` | `modules/relatorios/routes.py` |
| `/api/limpar_dados`, `/api/limpar_configuracoes` | `modules/auth/routes.py` |
| `/api/despesas_mensais/meses` | `modules/despesas_mensais/routes.py` |

### De `parser_utils.py`

| Função atual | Módulo destino | Arquivo destino |
|---|---|---|
| `process_file()` | `modules/extratos/` | `parser.py` |
| `process_despesas_file()` | `modules/extratos/` | `parser.py` |
| `_df_to_transactions()` | `modules/extratos/` | `parser.py` |
| `_find_column()`, `_parse_date()`, `_parse_value()`, `_read_xml_xls()` | `modules/extratos/` | `parser.py` |

---

## Inicialização do Banco de Dados

A estratégia de init_db deve ser preservada: as tabelas são criadas no import, e migrações `ALTER TABLE` são feitas com try/except para não quebrar bancos existentes.

```python
# db/init.py
def init_all():
    from modules.auth.db import init_tables as init_auth
    from modules.extratos.db import init_tables as init_extratos
    from modules.cadastros.db.despesas import init_tables as init_despesas_cad
    # ... todos os módulos com tabelas
    
    init_auth()
    init_extratos()
    # ...
```

Cada `init_tables()` de módulo cria suas tabelas com `CREATE TABLE IF NOT EXISTS` e aplica migrações de colunas com try/except — padrão idêntico ao atual.

---

## Ordem de Implementação Recomendada

Implementar na seguinte ordem para minimizar risco:

1. **`db/connection.py`** — extrair `get_connection()` do `database.py`
2. **`config.py`** — extrair configurações do topo do `app.py`
3. **`modules/auth/`** — módulo mais simples, bom ponto de partida
4. **`modules/extratos/`** — mover `parser_utils.py` + rotas de upload
5. **`modules/cadastros/`** — 6 sub-entidades mas padrão repetitivo
6. **`modules/despesas_mensais/`** — módulo central, mais rotas
7. **`modules/receitas_mensais/`**
8. **`modules/impostos/`**
9. **`modules/emprestimos/`**
10. **`modules/investimentos/`**
11. **`modules/trader/`**
12. **`modules/dashboard/`**
13. **`modules/relatorios/`** — mais complexo (get_dados_relatorio_dinamico)
14. **`app.py` final** — limpar e registrar todos os blueprints
15. **Testar** — subir o servidor, verificar todas as rotas, confirmar que o `index.html` funciona igual

---

## Verificação de Integridade

Antes de considerar a migração completa, verificar:

- [ ] `python app.py` inicia sem erros
- [ ] `GET /` retorna o `index.html`
- [ ] Login/Register funciona
- [ ] Upload de extrato (XLS, CSV, PDF) retorna transações
- [ ] Salvar lançamento mensal persiste no banco
- [ ] Export de Excel funciona
- [ ] Dashboard carrega dados
- [ ] Relatório dinâmico gera corretamente
- [ ] Trader positions import e export funcionam
- [ ] O arquivo `extratos.db` existente é lido sem alterações no schema

---

## Notas Técnicas Importantes

### Rotas inline no `app.py` que acessam banco diretamente
Duas rotas em `app.py` fazem queries diretas ao banco sem chamar função de `database.py`:
- `api_meses_disponiveis()` (linha 606) — mover para `modules/despesas_mensais/routes.py` com import de `db.connection`
- `api_meses_disponiveis_relatorio()` (linha 1213) — mover para `modules/relatorios/routes.py`
- `api_clear_trader_positions()` (linha 1306) — parte da lógica acessa banco diretamente — encapsular em `modules/trader/db.py`

### Imports circulares potenciais
`parser_utils.py` importa de `database` e `exchange_api`. Na estrutura modular:
- `modules/extratos/parser.py` importa de `modules/extratos/db.py` (para `guess_category`)
- `modules/extratos/parser.py` importa de `exchange_api` (permanece no root)

### Gestão de uploads temporários
`UPLOAD_FOLDER = 'uploads'` é criado pelo `config.py`. Rotas que fazem `os.path.join(app.config['UPLOAD_FOLDER'], ...)` devem usar `current_app.config['UPLOAD_FOLDER']` dentro dos blueprints.

### Session em blueprints
`session['user_email']` funciona normalmente em blueprints Flask — nenhuma alteração necessária.

### `fix_app.py`, `test_*.py`, `scratch/`
Arquivos temporários de debug — podem ser ignorados na migração ou deletados após validação.
