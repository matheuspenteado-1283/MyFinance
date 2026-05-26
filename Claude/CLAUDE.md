# CLAUDE.md — MyFinance 2.0

> Lido automaticamente em cada sessão. Seguir rigorosamente antes de qualquer alteração de código.

---

## 1. IDENTIDADE DO PROJETO

```
DOMÍNIO:  SaaS-Product / Personal Finance
STACK:    Python 3.11 · Flask · PostgreSQL (Supabase) · Pandas · Anthropic/OpenAI
FASE:     development
DEPLOY:   Render.com (free tier) via Gunicorn
```

---

## 2. STACK TÉCNICA COMPLETA

| Camada | Tecnologia |
|--------|-----------|
| Runtime | Python 3.11 |
| Web Framework | Flask (application factory + Blueprints) |
| Banco de Dados | PostgreSQL via Supabase (`psycopg2-binary`) |
| Wrapper DB | `PGConnection` / `PGCursor` — imita API SQLite (em `db/connection.py`) |
| ORM | Nenhum — SQL puro com `%s` placeholders (psycopg2) |
| Dados / ETL | Pandas, openpyxl, xlrd, pdfplumber, BeautifulSoup4, python-dateutil |
| Câmbio | Frankfurter API (`exchange_api.py`) |
| IA | Anthropic (`claude-sonnet-4-6` / `claude-haiku-4-5-20251001`) ou OpenAI (`gpt-4o` / `gpt-4o-mini`) |
| Servidor prod | Gunicorn — 2 workers, timeout 120s |
| Deploy | Render.com — config em `render.yaml` |
| Frontend | SPA única — `templates/index.html` + `static/css/style.css` |
| Env vars | `python-dotenv` — arquivo `.env` (nunca versionar) |

---

## 3. ARQUITETURA — ESTRUTURA DE FICHEIROS

```
MyFinance 2.0/
├── app.py                  # Ponto de entrada — create_app() + registo de Blueprints
├── config.py               # SECRET_KEY, UPLOAD_FOLDER, MAX_CONTENT_LENGTH, allowed_file()
├── exchange_api.py         # Cotações de câmbio (Frankfurter API) — não alterar
├── requirements.txt        # Dependências Python
├── render.yaml             # Config de deploy Render.com
├── Procfile                # Comando gunicorn para deploy alternativo
├── supabase_schema.sql     # Schema PostgreSQL de referência
│
├── db/
│   ├── __init__.py         # init_all() — chama init_tables() de cada módulo
│   └── connection.py       # get_connection() → PGConnection — ÚNICA FONTE de conexão
│
├── modules/
│   ├── auth/               # Login, register, logout, password reset, email
│   ├── extratos/           # Upload e parsing de extratos bancários (XLS/CSV/PDF/XML)
│   ├── cadastros/          # Dados de referência (despesas, contas, receitas, etc.)
│   │   └── db/             # Sub-módulo: despesas.py, contas.py, receitas.py, ...
│   ├── despesas_mensais/   # Lançamentos mensais de despesas
│   ├── receitas_mensais/   # Lançamentos mensais de receitas
│   ├── impostos/           # Controlo de impostos e lançamentos fiscais
│   ├── emprestimos/        # Gestão de empréstimos
│   ├── investimentos/      # Carteira de investimentos
│   ├── trader/             # Posições de trading (XTB e outras plataformas)
│   ├── dashboard/          # Dados agregados para dashboard
│   ├── relatorios/         # Relatórios dinâmicos
│   ├── budget/             # Orçamento vs. realizado
│   └── ai_agent/           # Agente IA financeiro (Anthropic / OpenAI)
│       ├── analyst.py      # Lógica de análise — prompts e chamadas à API IA
│       ├── collector.py    # Snapshot financeiro — coleta dados para o agente
│       ├── db.py           # Cache de análises e histórico de chat
│       └── AGENT_PROMPT.md # System prompt do agente
│
├── templates/
│   └── index.html          # ⛔ NÃO ALTERAR — SPA completa do frontend
├── static/
│   └── css/style.css       # ⛔ NÃO ALTERAR — estilos da SPA
├── uploads/                # Runtime — criado pelo config.py (git-ignored)
├── Skills/                 # Skills de apoio ao desenvolvimento (não alterar)
├── Agents/
│   └── agent_financial_advisor.md  # ← Agente IA: prompt completo + workflows + exemplos
└── .env.example            # Template de variáveis de ambiente
```

---

## 4. PADRÕES DE CÓDIGO OBRIGATÓRIOS

### 4.1 Blueprint — Padrão de cada módulo

```python
# modules/<nome>/__init__.py
from flask import Blueprint
bp = Blueprint('<nome>', __name__)
from . import routes  # noqa

# modules/<nome>/routes.py
from flask import request, jsonify, session
from . import bp
from .db import funcao_do_modulo

def _auth():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    return None

@bp.route('/api/<rota>', methods=['GET'])
def handler():
    err = _auth()
    if err: return err
    user_email = session['user_email']
    ...
    return jsonify(resultado)
```

### 4.2 DB — Padrão de acesso a dados

```python
# modules/<nome>/db.py
from db.connection import get_connection  # SEMPRE desta fonte

def init_tables():
    conn = get_connection()
    conn.execute('''CREATE TABLE IF NOT EXISTS nome_tabela (
        id SERIAL PRIMARY KEY,
        user_email TEXT,
        ...
    )''')
    conn.commit()
    conn.close()
    # Migrações de coluna — sempre com try/except:
    try:
        conn2 = get_connection()
        conn2.execute('ALTER TABLE nome_tabela ADD COLUMN nova_coluna TEXT')
        conn2.commit()
        conn2.close()
    except Exception:
        pass  # Coluna já existe

def get_dados(user_email: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM nome_tabela WHERE user_email = %s', (user_email,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows
```

### 4.3 Placeholders SQL

- **SEMPRE `%s`** (psycopg2) — nunca `?` (SQLite)
- Queries com múltiplos params: `(valor1, valor2)` como tupla
- `RETURNING id` para INSERT quando necessitar do ID gerado

### 4.4 Respostas JSON

```python
# Sucesso
return jsonify({'status': 'ok', 'data': resultado})

# Erro com código HTTP
return jsonify({'error': 'Mensagem descritiva'}), 400

# Lista
return jsonify(lista_de_dicts)
```

### 4.5 Uploads de ficheiros

```python
from config import allowed_file
from flask import current_app
from werkzeug.utils import secure_filename
import os

upload_folder = current_app.config['UPLOAD_FOLDER']  # nunca hardcode
filename = secure_filename(file.filename)
if not allowed_file(filename):
    return jsonify({'error': 'Formato não suportado'}), 400
filepath = os.path.join(upload_folder, filename)
file.save(filepath)
```

---

## 5. MÓDULOS — REFERÊNCIA RÁPIDA

| Módulo | Blueprint | Responsabilidade principal |
|--------|-----------|---------------------------|
| `auth` | `auth` | Login, register, logout, reset senha, limpar dados |
| `extratos` | `extratos` | Upload/parse XLS·CSV·PDF·XML, categorização automática |
| `cadastros` | `cadastros` | CRUD de: despesas, contas, receitas, investimentos, usuários, tipo_imposto |
| `despesas_mensais` | `despesas_mensais` | Lançamentos mensais, consolidação anual, export XLSX |
| `receitas_mensais` | `receitas_mensais` | Receitas mensais, sync com despesas, cotação EUR/BRL |
| `impostos` | `impostos` | Lançamentos fiscais, dashboard de impostos |
| `emprestimos` | `emprestimos` | Controlo de empréstimos, saldo devedor |
| `investimentos` | `investimentos` | Carteira de investimentos, upload/export |
| `trader` | `trader` | Posições de trading, períodos, contas de corretora |
| `dashboard` | `dashboard` | Agregação: despesas por categoria, evolução anual, P&L |
| `relatorios` | `relatorios` | Relatórios dinâmicos configuráveis |
| `budget` | `budget` | Orçamento vs. realizado, import/export XLSX |
| `ai_agent` | `ai_agent` | Análise IA: saúde financeira, budget, tips, trader, chat |

---

## 6. BANCO DE DADOS — TABELAS PRINCIPAIS

| Tabela | Módulo | Descrição |
|--------|--------|-----------|
| `users` | auth | Utilizadores (email + password_hash) |
| `password_reset_tokens` | auth | Tokens de reset de senha (TTL 1h) |
| `categorias_aprendidas` | extratos | Regras de categorização por descrição |
| `cad_despesas` | cadastros | Tipos de despesa com fator de divisão |
| `cad_contas` | cadastros | Contas bancárias e dados de acesso |
| `cad_receitas` | cadastros | Tipos de receita |
| `cad_investimentos` | cadastros | Tipos de investimento |
| `cad_usuarios` | cadastros | Usuários internos (usr1/usr2) com fator de pagamento |
| `tb_tipo_imposto` | cadastros | Tipos de imposto com alíquota |
| `despesas_mensais` | despesas_mensais | Lançamentos mensais (multi-moeda, EUR base) |
| `despesas_anuais` | despesas_mensais | Consolidação anual por categoria |
| `receitas_mensais` | receitas_mensais | Receitas por mês de referência |
| `lcto_impostos` | impostos | Lançamentos de impostos |
| `lcto_emprestimos` | emprestimos | Lançamentos de empréstimos |
| `lcto_investimentos` | investimentos | Lançamentos de carteira |
| `trader_positions` | trader | Posições de trading por período/conta |
| `budget_items` | budget | Itens de orçamento por ano/categoria/mês |
| `budget_import_audit` | budget | Auditoria de importações de budget |
| `ai_analysis_cache` | ai_agent | Cache de análises IA (TTL configurável) |
| `ai_chat_history` | ai_agent | Histórico de chat com o agente IA |

**Regra de ouro:** `CREATE TABLE IF NOT EXISTS` em todo `init_tables()`. Migrações apenas com `ALTER TABLE ... ADD COLUMN` dentro de `try/except`. **Nunca `DROP TABLE` ou alterar tipos de colunas existentes.**

---

## 7. VARIÁVEIS DE AMBIENTE

| Variável | Obrigatório | Descrição |
|----------|-------------|-----------|
| `DATABASE_URL` | ✅ | URL completa PostgreSQL (Supabase) |
| `SECRET_KEY` | ✅ | Chave Flask para sessões |
| `AI_PROVIDER` | ✅ | `anthropic` (padrão) ou `openai` |
| `ANTHROPIC_API_KEY` | ✅ se anthropic | Chave Anthropic Console |
| `OPENAI_API_KEY` | opcional | Chave OpenAI Platform |
| `RENDER_EXTERNAL_URL` | auto | URL pública Render — activa keep-alive |
| `SMTP_HOST` | opcional | Servidor SMTP para reset de senha |
| `SMTP_PORT` | opcional | Porta SMTP (padrão 587) |
| `SMTP_USER` | opcional | Email de envio |
| `SMTP_PASS` | opcional | Senha de app SMTP |
| `SMTP_FROM_NAME` | opcional | Nome do remetente (padrão: MyFinance) |

**Nunca** colocar valores reais no código. Usar `.env` local (git-ignored) e `render.yaml` para produção.

---

## 8. REGRAS DE NEGÓCIO CRÍTICAS

### 8.1 Multi-moeda
- Moeda base: **EUR**
- Campo `cambio_eur`: taxa de câmbio para EUR no momento do lançamento
- Campo `valor_eur`: valor convertido para EUR (moeda de referência)
- Cotações via `exchange_api.get_exchange_rate(from_currency, to_currency, date)`

### 8.2 Divisão de despesas (usr1/usr2)
- Campos `usr1` e `usr2` em `despesas_mensais` armazenam percentuais de responsabilidade
- Cálculo: `valor_eur * (usr_target / (usr1 + usr2))`
- SQL usa `NULLIF` e `COALESCE` para evitar divisão por zero

### 8.3 Categorização de extratos
- `extratos/parser.py` processa múltiplos formatos: XLS (Novobanco PF/PJ/Casa, Santander BR), CSV (Revolut, Santander PT), PDF (Novobanco), XML
- `guess_category(descricao)`: match exato em `categorias_aprendidas`, depois substring
- `save_category_rule(padrao, categoria)`: aprende novas regras

### 8.4 Mês de referência
- Formato: `YYYY-MM` (ex: `2026-05`)
- Usado em: `despesas_mensais`, `receitas_mensais`, `lcto_impostos`, `ai_analysis_cache`
- Filtro padrão: mês atual via `datetime.now().strftime('%Y-%m')`

### 8.5 Agente IA
- Modelo rápido (`claude-haiku-*`): chat em tempo real
- Modelo completo (`claude-sonnet-*`): análises estruturadas (saúde financeira, budget, tips)
- Cache de análises: TTL 6h por padrão, forçar refresh com `?refresh=true`
- Respostas estruturadas: **sempre JSON válido**, sem texto fora do bloco JSON
- Chat: texto natural, máximo 200 palavras, 1 ação concreta no final
- **Prompt mestre do agente:** ver `Agents/agent_financial_advisor.md`
  - Define identidade, workflows (A–E), regras de qualidade e exemplos de interação
  - `SYSTEM_PROMPT` em `modules/ai_agent/analyst.py` é a versão compacta para API
  - Ao adicionar nova capacidade ao agente: actualizar ambos os ficheiros

---

## 9. O QUE NUNCA ALTERAR

| Item | Motivo |
|------|--------|
| `templates/index.html` | SPA completa — todas as rotas frontend estão hardcoded neste ficheiro |
| `static/css/style.css` | Estilos da SPA — alterações quebram o visual |
| URLs de todas as rotas API | Frontend chama directamente — qualquer rename quebra a UI |
| Schema de tabelas existentes | Dados reais de utilizador — nunca DROP ou renomear colunas |
| `exchange_api.py` | Já isolado e estável |
| `db/connection.py` — interface pública | `PGConnection` / `PGCursor` são usados em todos os módulos |

---

## 10. ADIÇÃO DE NOVOS MÓDULOS

Seguir este checklist ao criar qualquer novo módulo:

```
[ ] Criar pasta modules/<nome>/
[ ] __init__.py: Blueprint + import routes
[ ] routes.py: rotas com _auth() guard, jsonify(), session['user_email']
[ ] db.py: init_tables() com CREATE IF NOT EXISTS + migrações try/except
[ ] Registrar Blueprint em app.py
[ ] Chamar init_tables() em db/__init__.py → init_all()
[ ] Adicionar tabela ao supabase_schema.sql
[ ] Variáveis de ambiente novas → .env.example
[ ] Nunca criar get_connection() própria — importar de db.connection
```

---

## 11. DEPLOY E INFRAESTRUTURA

- **Plataforma:** Render.com (`render.yaml`)
- **Build:** `pip install -r requirements.txt`
- **Start:** `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120`
- **Keep-alive:** thread daemon pinga `/health` a cada 10min (Render free tier dorme após 15min)
- **Python version:** 3.11.0 (definido em `render.yaml`)
- **Branches:** `main` → auto-deploy em produção

### Variáveis no Render (nunca no código):
`DATABASE_URL`, `SECRET_KEY`, `AI_PROVIDER`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`

---

## 12. FORMATO DE RESPOSTA CLAUDE (neste projecto)

```
MÓDULO: [módulo(s) afectado(s)]
TIPO:   [nova rota | nova tabela | fix | refactor | nova feature]
[ASSUME: x = y — confirmar ou corrigir se errado]

--- código (apenas diff/bloco alterado) ---

PRÓXIMO PASSO: [acção recomendada]
TESTE:         [como verificar que funciona]
```

- Nunca gerar o ficheiro inteiro — apenas a secção modificada
- Para ficheiros > 100 linhas: `# ... resto inalterado ...`
- Máximo 1 pergunta de clarificação por turno

---

## 13. CHECKLIST ANTES DE QUALQUER ALTERAÇÃO

```
[ ] Identifiquei o módulo correcto (não vou alterar código fora do scope)
[ ] Não vou alterar index.html, style.css ou URLs de rotas existentes
[ ] Usando %s como placeholder SQL (não ?)
[ ] Importando get_connection() de db.connection (não criando conexão própria)
[ ] init_tables() com CREATE TABLE IF NOT EXISTS + migrações try/except
[ ] Credenciais/keys via os.getenv() (nunca hardcode)
[ ] Resposta JSON via jsonify() com código HTTP apropriado
[ ] _auth() guard em todas as rotas que requerem login
[ ] Se nova tabela: adicionada ao supabase_schema.sql e ao db/__init__.py
```

---

*Versão: 2.0 | Gerado em 2026-05-26 | Stack: Python·Flask·PostgreSQL·Supabase·Anthropic*
