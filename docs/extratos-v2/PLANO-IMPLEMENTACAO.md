# Extratos v2 — Plano de Implementação

**Versão:** 1.0 · **Data:** 2026-08-12 · **Estado:** proposta, aguardando aprovação
**Módulo:** `modules/extratos`
**ADR relacionado:** [`.context/decisions/ADR-001-receitas-de-extrato-como-dado.md`](../../.context/decisions/ADR-001-receitas-de-extrato-como-dado.md)

---

## 0. Como usar este documento

Escrito para um desenvolvedor externo que **não conhece a codebase**. Contém:

- O mapa do código atual e o inventário honesto dos problemas (§2)
- A arquitetura alvo, o modelo de dados e os contratos de API (§4-§7)
- Código de referência para os componentes não-óbvios (§8)
- Fases de entrega com critérios de aceite verificáveis (§10)

Cada fase é um PR independente que entrega valor sozinho. **Não implementar as fases fora de ordem** — a Fase 1 é pré-requisito de todas as outras.

Referências de código usam `caminho:linha` relativos à raiz do repositório.

---

## 1. Contexto e objetivo

### O problema de negócio

O MyFinance importa extratos bancários em PDF, XLSX, XLS, CSV e XML. A precisão da extração varia conforme o banco emissor e o formato. Hoje, cada banco novo exige que o fundador altere o parser e faça deploy. Isso torna impossível abrir cadastro para novos usuários: cada cliente com um banco não suportado vira um ticket de engenharia.

### O objetivo

> **Reduzir a > 95% a taxa de importações que terminam sem intervenção do mantenedor**, com os 5% restantes resolvidos pelo próprio usuário — nunca por engenharia.

### Restrições de produto (decididas, não renegociar)

| # | Restrição | Consequência técnica |
|---|---|---|
| R1 | Mercado alvo: **Portugal e Brasil** | Moedas EUR/BRL; datas `dayfirst`; separador decimal `,`; suportar OFX (BR) e CAMT.053/MT940 (PT) |
| R2 | **Nenhum dado real do extrato pode sair do servidor** | A IA recebe apenas amostra anonimizada; a extração roda 100% local |
| R3 | **Revisão obrigatória na primeira importação de cada layout** | A confirmação do usuário é o que promove uma receita a confiável |

---

## 2. Estado atual do código

### 2.1 Mapa

```
MyFinance 2.0/
├── app.py                       # create_app(), registra blueprints, init_all()
├── config.py                    # ALLOWED_EXTENSIONS, UPLOAD_FOLDER, MAX_CONTENT_LENGTH
├── db/connection.py             # get_connection() → PGConnection (wrapper psycopg2 com API sqlite3)
├── exchange_api.py              # get_exchange_rate(date_str, from_currency, to_currency)
├── modules/extratos/
│   ├── __init__.py              # Blueprint 'extratos'
│   ├── routes.py                # POST /upload, POST /save_category, POST /export
│   ├── parser.py                # 922 linhas — toda a extração
│   └── db.py                    # tabela categorias_aprendidas
└── templates/index.html         # 10.428 linhas, SPA com JS inline
```

### 2.2 Stack

- **Runtime:** Python 3.x + Flask (sem factory pattern de blueprint dinâmico; `create_app()` em [app.py:43](../../app.py))
- **DB:** PostgreSQL via `psycopg2`, acessado pelo wrapper `PGConnection`/`PGCursor` em [db/connection.py](../../db/connection.py). Cursores são `RealDictCursor` → linhas são dict-like (`row['coluna']`).
- **Frontend:** template único `templates/index.html`, JS inline, sem build step, sem framework.
- **Deploy:** Render (`render.yaml`, `Procfile`, gunicorn).
- **Tabelas:** criadas por `init_tables()` em cada `modules/<x>/db.py`, chamadas por `init_all()` ([app.py:46](../../app.py)).

### 2.3 Inventário de problemas (o que motiva este plano)

| # | Problema | Localização | Impacto |
|---|---|---|---|
| P1 | **Falha silenciosa.** `except Exception: pass` no caminho de extração; `process_file` devolve `[]` sem distinguir "não achei" de "quebrei" | [parser.py:699-780](../../modules/extratos/parser.py) | Impossível diagnosticar; usuário vê só "nenhuma transação" |
| P2 | **Sem score de confiança.** Extração ou produz linhas ou não produz | `parser.py` inteiro | Erro numérico passa despercebido |
| P3 | **Data de fallback silenciosa.** `_parse_date` devolve `'2023-01-01'` quando não consegue parsear | [parser.py:29,44](../../modules/extratos/parser.py) | **Corrupção de dado**, não erro |
| P4 | **Regra de banco embutida no código genérico** | [parser.py:180](../../modules/extratos/parser.py) (heurística Novo Banco) e [parser.py:390](../../modules/extratos/parser.py) (`_parse_pdf_millennium`) | Banco novo = deploy |
| P5 | **Moeda inferida do nome do arquivo** | [parser.py:196-198](../../modules/extratos/parser.py) | Usuário controla o nome do arquivo; heurística não confiável |
| P6 | **Sem sessão de importação no servidor.** `POST /upload` devolve as transações; o estado vive só em `parsedTransactions` no browser ([index.html:8503](../../templates/index.html)) | [routes.py:14](../../modules/extratos/routes.py) | Correção do usuário não pode alimentar a receita |
| P7 | **`categorias_aprendidas` sem coluna de usuário** | [db.py:8](../../modules/extratos/db.py) | **Vazamento entre contas** — bloqueador de multi-tenancy |
| P8 | **Câmbio consultado por transação** dentro do loop | [parser.py:200](../../modules/extratos/parser.py) | N chamadas por extrato; lento em arquivos grandes |
| P9 | **OFX não aceito no upload.** `ALLOWED_EXTENSIONS` = `{pdf, csv, xls, xlsx, xml}` | [config.py](../../config.py) | Formato padrão e confiável fica de fora |
| P10 | **Sem suite de regressão.** `test_parser*.py` são scripts soltos na raiz | raiz do repo | Consertar um banco quebra outro |

P7 é **independente** deste plano e deve ser corrigido primeiro (Fase 0) — é um bug de segurança, não de arquitetura.

---

## 3. Decisões de arquitetura

Resumo do [ADR-001](../../.context/decisions/ADR-001-receitas-de-extrato-como-dado.md). As quatro decisões são vinculantes:

- **D1 — Receita como dado.** Layout bancário vira registro em `extrato_receitas`, interpretado por um executor genérico.
- **D2 — Fingerprint de layout.** A receita é localizada por hash estrutural do arquivo, nunca pelo nome.
- **D3 — IA induz, nunca lê.** O LLM recebe amostra anonimizada e responde uma pergunta só: *qual coluna é o quê*. Ordem dia/mês, separador decimal e moeda são derivados por código.
- **D4 — Confiança explícita.** Toda extração produz score; a primeira importação de cada fingerprint exige revisão.

### 3.1 Regra de ouro da indução

> **Tudo que pode ser derivado deterministicamente fica em código.**

| Derivação | Onde |
|---|---|
| Ordem dia/mês | Código — `_infer_dayfirst()`: se algum primeiro componente > 12 → `dayfirst=True`; senão default por país (PT e BR = `dayfirst`) |
| Separador decimal / milhar | Código — último separador seguido de exatamente 2 dígitos é o decimal |
| Moeda | Código — símbolo/ISO no cabeçalho ou no texto fixo; nunca do nome do arquivo |
| Sinal (débito/crédito) | Código — coluna dedicada, sinal negativo, ou parênteses |
| **Qual coluna é data / descrição / valor / saldo** | **IA** (ou o mapeador manual) |
| **Onde começa a tabela (header row)** | **IA** (ou o mapeador manual) |
| **Quais linhas descartar** | **IA** (ou o mapeador manual) |

Isso reduz o trabalho do LLM a um problema de mapeamento estrutural, que a amostra mascarada resolve perfeitamente.

---

## 4. Arquitetura alvo

### 4.1 Fluxo

```
POST /extratos/importar  (multipart)
        │
        ▼
┌──────────────────────────────────────────────────────────────┐
│ 1. FAST PATH — formato padronizado?                          │
│    .ofx / .qfx (BR) · CAMT.053 / MT940 (PT)                  │
│    → 1 parser serve todos os bancos → pula para (5)          │
└──────────────────────────────────────────────────────────────┘
        │ não
        ▼
┌──────────────────────────────────────────────────────────────┐
│ 2. FINGERPRINT   fingerprint.compute(filepath)               │
│    hash(tokens estáticos + producer PDF + nº colunas)        │
└──────────────────────────────────────────────────────────────┘
        │
        ├── receita VERIFIED/PROPOSED encontrada ──────────┐
        │                                                   │
        ▼ não encontrada                                    │
┌──────────────────────────────────────────────────────────┐ │
│ 3. INDUÇÃO                                               │ │
│    a) anonymizer.build_sample(filepath)                  │ │
│    b) induction.induzir(sample)  → spec (status=proposed) │ │
│    c) se IA indisponível → spec vazio, mapeador manual   │ │
└──────────────────────────────────────────────────────────┘ │
        │                                                    │
        ├────────────────────────────────────────────────────┘
        ▼
┌──────────────────────────────────────────────────────────────┐
│ 4. EXECUTOR   recipes.apply(spec, filepath) → [Transacao]    │
│    determinístico · local · testável · sem IA                │
└──────────────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────────────────┐
│ 5. VALIDAÇÃO  validator.validate(txns, contexto) → score     │
│    saldo encadeado · cobertura · período · duplicatas        │
└──────────────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────────────────┐
│ 6. SESSÃO   grava extrato_importacoes + transações staging   │
│    devolve { importacao_id, score, precisa_revisao, linhas } │
└──────────────────────────────────────────────────────────────┘
        │
        ├── precisa_revisao=false ──► confirmação automática
        └── precisa_revisao=true  ──► tela de revisão
                                          │
                                          ▼
                              POST /extratos/importacoes/<id>/confirmar
                              → grava transações definitivas
                              → receita.status = 'verified'
                              → correções alimentam a receita
```

### 4.2 Módulos novos

```
modules/extratos/
├── parser.py          (existente — vira FALLBACK, não é removido nas Fases 1-3)
├── routes.py          (estendido)
├── db.py              (estendido: novas tabelas + user_email em categorias_aprendidas)
├── errors.py          NOVO — exceções tipadas
├── fingerprint.py     NOVO — identificação de layout
├── anonymizer.py      NOVO — mascaramento (único ponto de saída de dados)
├── validator.py       NOVO — checagens + score
├── recipes.py         NOVO — executor determinístico dirigido por spec
├── induction.py       NOVO — chamada ao LLM (opcional, degradação graciosa)
├── standard.py        NOVO — fast path OFX / CAMT.053 / MT940
└── __tests__/         NOVO — suite de regressão + fixtures
```

**Regra de dependência:** `recipes.py`, `validator.py`, `fingerprint.py` e `anonymizer.py` **não importam** `induction.py`. A IA é opcional; o sistema funciona inteiro sem ela.

---

## 5. Modelo de dados

DDL para `modules/extratos/db.py::init_tables()`. Idempotente (`IF NOT EXISTS`), no padrão dos outros módulos.

```sql
-- ─────────────────────────────────────────────────────────────
-- Fase 0: corrigir multi-tenancy da tabela existente
-- ─────────────────────────────────────────────────────────────
ALTER TABLE categorias_aprendidas ADD COLUMN IF NOT EXISTS user_email TEXT;
-- backfill manual: atribuir as regras existentes ao usuário fundador
ALTER TABLE categorias_aprendidas DROP CONSTRAINT IF EXISTS categorias_aprendidas_padrao_descricao_key;
CREATE UNIQUE INDEX IF NOT EXISTS ux_cat_aprend_user_padrao
    ON categorias_aprendidas (user_email, padrao_descricao);

-- ─────────────────────────────────────────────────────────────
-- Fase 3: biblioteca de receitas (compartilhada entre usuários)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS extrato_receitas (
    id            SERIAL PRIMARY KEY,
    fingerprint   TEXT NOT NULL UNIQUE,
    banco_label   TEXT NOT NULL DEFAULT 'Desconhecido',
    pais          TEXT,                       -- 'PT' | 'BR' | NULL
    formato       TEXT NOT NULL,              -- pdf_table | pdf_words | planilha | csv | ofx | camt
    spec          JSONB NOT NULL,
    status        TEXT NOT NULL DEFAULT 'proposed',   -- proposed | verified | deprecated
    origem        TEXT NOT NULL DEFAULT 'manual',     -- manual | llm | seed
    confirmacoes  INTEGER NOT NULL DEFAULT 0,
    execucoes     INTEGER NOT NULL DEFAULT 0,
    falhas        INTEGER NOT NULL DEFAULT 0,
    criada_por    TEXT,                       -- user_email do primeiro usuário
    criada_em     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizada_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_receitas_status ON extrato_receitas (status);

-- ─────────────────────────────────────────────────────────────
-- Fase 1: sessão de importação (o que hoje só existe no browser)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS extrato_importacoes (
    id             SERIAL PRIMARY KEY,
    user_email     TEXT NOT NULL,
    arquivo_nome   TEXT NOT NULL,
    arquivo_sha256 TEXT,                      -- detecta reimportação do mesmo arquivo
    fingerprint    TEXT,
    receita_id     INTEGER REFERENCES extrato_receitas(id),
    conta_bancaria TEXT,
    score          INTEGER NOT NULL DEFAULT 0,
    checks         JSONB NOT NULL DEFAULT '[]'::jsonb,
    status         TEXT NOT NULL DEFAULT 'pendente',  -- pendente | confirmada | descartada
    total_linhas   INTEGER NOT NULL DEFAULT 0,
    criada_em      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    confirmada_em  TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_import_user ON extrato_importacoes (user_email, criada_em DESC);

-- ─────────────────────────────────────────────────────────────
-- Fase 1: linhas em staging, antes da confirmação
-- ─────────────────────────────────────────────────────────────
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
    raw            JSONB                       -- linha bruta, para depurar a receita
);
CREATE INDEX IF NOT EXISTS ix_staging_import ON extrato_linhas_staging (importacao_id, linha_idx);
```

**Nota sobre JSONB com psycopg2:** passar `psycopg2.extras.Json(dict)` ou `json.dumps(dict)` — o wrapper `PGCursor` repassa os parâmetros direto.

**Por que a biblioteca de receitas é global e não por usuário:** uma receita contém apenas estrutura (nomes de coluna, faixas de x, formatos). Nunca contém valores, descrições, nomes ou identificadores. Isso é garantido por construção e testado (§11.3). É o que permite que o banco resolvido por um usuário funcione para todos os seguintes.

---

## 6. Especificação da Receita (`spec`)

O `spec` é o JSON que o executor interpreta. Quatro estratégias.

### 6.1 `estrategia: "planilha"` (XLSX/XLS/CSV)

```json
{
  "estrategia": "planilha",
  "header_row": 7,
  "colunas": {
    "data": "Data Mov.",
    "data_valor": "Data Valor",
    "descricao": "Descrição",
    "debito": "Débito",
    "credito": "Crédito",
    "saldo": "Saldo"
  },
  "moeda": "EUR",
  "sinal": "colunas_separadas",
  "ignorar_linhas_regex": ["^SALDO ", "^TOTAL", "^\\s*$"]
}
```

- `colunas` é por **nome de cabeçalho**; se a planilha não tiver cabeçalho legível, use `"colunas_idx": {"data": 0, "descricao": 1, "valor": 2}`.
- `sinal`: `colunas_separadas` | `valor_com_sinal` | `coluna_tipo` (com `coluna_tipo` + `valores_debito: ["D","DEB"]`).

### 6.2 `estrategia: "pdf_tabela"`

Igual à planilha, mas as colunas vêm de `pdfplumber.extract_tables()`. Campos extras:

```json
{
  "estrategia": "pdf_tabela",
  "min_colunas": 3,
  "reconstruir_multilinha": true
}
```

### 6.3 `estrategia: "pdf_words"` (generaliza `_parse_pdf_words`)

```json
{
  "estrategia": "pdf_words",
  "faixas_x": {
    "data":      [40, 90],
    "descricao": [92, 340],
    "debito":    [342, 410],
    "credito":   [412, 480],
    "saldo":     [482, 550]
  },
  "linha_transacao_regex": "^\\d{2}[./-]\\d{2}",
  "duas_datas": true,
  "tolerancia_y": 2.5,
  "moeda": "EUR",
  "ancora_saldo_inicial": "SALDO ANTERIOR",
  "ancora_saldo_final": "SALDO FINAL"
}
```

### 6.4 `estrategia: "linhas_regex"` (último recurso)

```json
{
  "estrategia": "linhas_regex",
  "regex": "^(?P<data>\\d{2}/\\d{2}/\\d{4})\\s+(?P<descricao>.+?)\\s+(?P<valor>-?[\\d.,]+)$",
  "moeda": "BRL"
}
```

### 6.5 Campos comuns a todas as estratégias

| Campo | Tipo | Default | Descrição |
|---|---|---|---|
| `moeda` | `str \| null` | `null` | ISO-4217. `null` = detectar por código |
| `dayfirst` | `bool \| null` | `null` | `null` = inferir (§8.4) |
| `decimal` | `str \| null` | `null` | `null` = inferir |
| `ignorar_linhas_regex` | `list[str]` | `[]` | Linhas descartadas antes do parsing |
| `ancora_saldo_inicial` | `str \| null` | `null` | Regex/texto que precede o saldo de abertura |
| `ancora_saldo_final` | `str \| null` | `null` | Idem para o saldo de fecho |

---

## 7. Contratos de API

Todos os endpoints exigem sessão autenticada (`session['user_email']`, ver [modules/auth/routes.py](../../modules/auth/routes.py)). Adicionar decorator `@login_required` — hoje não existe; criar em `modules/auth/__init__.py`.

### `POST /extratos/importar`

`multipart/form-data`: `files[]` (1..N), `conta_bancaria` (opcional).

**200** — uma entrada por arquivo:

```json
{
  "importacoes": [{
    "importacao_id": 412,
    "arquivo": "extrato_março.pdf",
    "banco_label": "Millennium BCP",
    "fingerprint": "a1b2c3d4e5f6",
    "receita": { "id": 17, "status": "verified", "origem": "llm" },
    "score": 97,
    "precisa_revisao": false,
    "checks": [
      { "nome": "saldo_encadeado", "passou": true,  "peso": 40, "detalhe": "47/47 linhas conferem" },
      { "nome": "cobertura",       "passou": true,  "peso": 25, "detalhe": "47 de 47 linhas com data" },
      { "nome": "datas_periodo",   "passou": true,  "peso": 10, "detalhe": null },
      { "nome": "sem_duplicatas",  "passou": true,  "peso": 10, "detalhe": null },
      { "nome": "sem_data_fallback","passou": true, "peso": 10, "detalhe": null },
      { "nome": "sem_valor_zero",  "passou": true,  "peso": 5,  "detalhe": null }
    ],
    "linhas_suspeitas": [],
    "total_linhas": 47,
    "transacoes": [ /* ver §7.1 */ ]
  }]
}
```

**422** — extração falhou ou não há receita e a indução não produziu resultado usável:

```json
{
  "erro": "layout_desconhecido",
  "mensagem": "Não foi possível identificar as colunas deste extrato.",
  "importacao_id": 413,
  "amostra": { /* payload do mapeador manual, ver §7.2 */ }
}
```

**Nunca devolver 200 com lista vazia.** Estado de erro é código HTTP + `erro` tipado (§8.1).

### 7.1 Objeto transação (staging)

Mantém compatibilidade com o que o front já consome hoje ([index.html:8503](../../templates/index.html)):

```json
{
  "id": "linha-0",
  "data": "2026-03-05",
  "descricao": "TRANSFERENCIA MB WAY",
  "valor_original": 42.30,
  "moeda": "EUR",
  "cambio": 1.0,
  "valor_eur": 42.30,
  "saldo": 1284.55,
  "is_debit": true,
  "receita": false,
  "categoria": "Não Categorizado",
  "pag1": 21.15,
  "pag2": 21.15,
  "suspeita": false,
  "motivos": []
}
```

### 7.2 `GET /extratos/importacoes/<id>/mapeador`

Devolve o payload da tela de mapeamento manual (§9.2):

```json
{
  "importacao_id": 413,
  "formato": "planilha",
  "colunas_detectadas": ["Data Mov.", "Descrição", "Débito", "Crédito", "Saldo"],
  "amostra_linhas": [ ["05-03-2026", "TRF MB WAY", "", "42,30", "1284,55"] ],
  "sugestao": { "data": "Data Mov.", "descricao": "Descrição", "credito": "Crédito" },
  "origem_sugestao": "llm"
}
```

### `POST /extratos/importacoes/<id>/mapeador`

Body: `{ "colunas": {...}, "header_row": 7, "banco_label": "Novo Banco", "pais": "PT" }`
→ grava/atualiza a receita com `status='proposed'`, re-executa e devolve o mesmo payload do `POST /importar`.

### `POST /extratos/importacoes/<id>/confirmar`

Body: `{ "transacoes": [...] }` (as linhas revisadas pelo usuário).

Ações, **em transação única**:
1. Grava as transações definitivas nas tabelas de destino.
2. `extrato_importacoes.status = 'confirmada'`.
3. Se houver `receita_id`: `confirmacoes += 1`; se `status='proposed'` → `'verified'`.
4. Registra as correções (diff staging → confirmado) em log para telemetria.

### `POST /extratos/importacoes/<id>/descartar`

Marca `status='descartada'`; não altera a receita.

---

## 8. Componentes — código de referência

O código abaixo é ponto de partida, não gospel. Os limiares marcados `# CALIBRAR` precisam ser ajustados contra o corpus real (§11).

### 8.1 `modules/extratos/errors.py`

```python
class ExtratoError(Exception):
    """Base. Toda falha de extração é uma destas — nunca um except genérico."""
    codigo = 'erro_extrato'

    def __init__(self, mensagem, detalhe=None):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.detalhe = detalhe

    def to_dict(self):
        return {'erro': self.codigo, 'mensagem': self.mensagem, 'detalhe': self.detalhe}


class FormatoNaoSuportado(ExtratoError):
    codigo = 'formato_nao_suportado'


class ArquivoIlegivel(ExtratoError):
    """PDF corrompido, protegido por senha, XLSX inválido."""
    codigo = 'arquivo_ilegivel'


class LayoutDesconhecido(ExtratoError):
    """Nenhuma receita casou e a indução não produziu spec usável."""
    codigo = 'layout_desconhecido'


class ReceitaFalhou(ExtratoError):
    """A receita existe mas não extraiu nada — provável mudança de layout do banco."""
    codigo = 'receita_falhou'
```

**Regra:** nenhum `except Exception: pass` no caminho de extração. Capturar exceções de biblioteca e re-lançar como `ArquivoIlegivel`/`ReceitaFalhou` com `detalhe` preenchido.

---

### 8.2 `modules/extratos/fingerprint.py`

O desafio: o hash precisa ser **estável entre extratos diferentes do mesmo banco** (conteúdo muda todo mês) e **distinto entre bancos**.

Técnica: usar apenas *template chrome* — texto que se repete. Em PDF multi-página, é a interseção dos tokens alfabéticos de todas as páginas (nomes de comerciantes não se repetem em todas). Em PDF de página única, tokens que aparecem ≥ 2 vezes.

```python
import hashlib
import os
import re
import unicodedata

_ALPHA = re.compile(r'[^\W\d_]{3,}', re.UNICODE)
# Meses e dias variam por extrato — nunca entram no fingerprint.
_STOPWORDS = {
    'janeiro','fevereiro','marco','abril','maio','junho','julho','agosto',
    'setembro','outubro','novembro','dezembro','jan','fev','mar','abr','mai',
    'jun','jul','ago','set','out','nov','dez',
    'segunda','terca','quarta','quinta','sexta','sabado','domingo',
}
MAX_TOKENS = 40   # CALIBRAR contra o corpus


def _norm(token):
    t = unicodedata.normalize('NFKD', token.lower())
    return ''.join(c for c in t if not unicodedata.combining(c))


def _tokens(texto):
    out = set()
    for m in _ALPHA.finditer(texto or ''):
        t = _norm(m.group())
        if t and t not in _STOPWORDS:
            out.add(t)
    return out


def _hash(partes):
    h = hashlib.sha256()
    for p in partes:
        h.update(p.encode('utf-8', errors='ignore'))
        h.update(b'\x00')
    return h.hexdigest()[:16]


def _fingerprint_pdf(filepath):
    import pdfplumber
    with pdfplumber.open(filepath) as pdf:
        producer = (pdf.metadata or {}).get('Producer') or ''
        creator = (pdf.metadata or {}).get('Creator') or ''

        textos = [p.extract_text() or '' for p in pdf.pages]
        if not any(textos):
            raise ArquivoIlegivel('PDF sem camada de texto (provável digitalização).')

        if len(textos) >= 2:
            # Chrome do template = tokens presentes em TODAS as páginas.
            estaveis = _tokens(textos[0])
            for t in textos[1:]:
                estaveis &= _tokens(t)
        else:
            estaveis = set()

        if len(estaveis) < 5:   # CALIBRAR
            # Fallback (1 página, ou páginas heterogêneas):
            # tokens que se repetem dentro do documento.
            contagem = {}
            for t in textos:
                for m in _ALPHA.finditer(t):
                    tok = _norm(m.group())
                    if tok and tok not in _STOPWORDS:
                        contagem[tok] = contagem.get(tok, 0) + 1
            estaveis = {t for t, n in contagem.items() if n >= 2}

        tokens = sorted(estaveis)[:MAX_TOKENS]
        return _hash(['pdf', _norm(producer), _norm(creator), *tokens]), {
            'formato': 'pdf',
            'producer': producer,
            'tokens': tokens,
            'paginas': len(pdf.pages),
        }


def _fingerprint_tabular(filepath, header_cells, n_colunas):
    """Para XLSX/XLS/CSV: cabeçalho normalizado + nº de colunas."""
    tokens = sorted({_norm(c) for c in header_cells if c and _ALPHA.search(str(c))})
    tokens = tokens[:MAX_TOKENS]
    return _hash(['tabular', str(n_colunas), *tokens]), {
        'formato': 'tabular',
        'tokens': tokens,
        'n_colunas': n_colunas,
    }


def compute(filepath, header_cells=None, n_colunas=None):
    """Devolve (fingerprint: str, evidencia: dict).

    `evidencia` é gravada no log — permite depurar por que dois extratos do
    mesmo banco geraram fingerprints diferentes.
    """
    ext = os.path.splitext(filepath)[1].lower()
    if ext == '.pdf':
        return _fingerprint_pdf(filepath)
    return _fingerprint_tabular(filepath, header_cells or [], n_colunas or 0)
```

**Instabilidade é esperada.** Quando um banco muda o layout, o fingerprint muda e uma receita nova é induzida. A receita antiga vira `deprecated` por telemetria (§14), não por detecção automática.

---

### 8.3 `modules/extratos/anonymizer.py`

**Este é o único ponto do sistema que envia dados para fora.** O contrato é testável e o teste é bloqueante (§11.3).

```python
import re

# Marcadores estruturais preservados: identificam moeda e formato numérico,
# e não são informação pessoal.
_PRESERVAR = {
    'R$', 'US$', 'EUR', 'USD', 'BRL', 'GBP', '€', '$', '£',
    'D', 'C', 'DEB', 'CRED',
}
_DIGITO = re.compile(r'\d')
_ALPHA_RUN = re.compile(r'[^\W\d_]+', re.UNICODE)


def mask(texto):
    """Mascara conteúdo preservando estrutura.

    Dígitos → 9. Runs alfabéticos → X (mesmo comprimento).
    Pontuação, espaços e símbolos de moeda intactos.

        '1.234,56'                   → '9.999,99'
        '05/03/2026'                 → '99/99/9999'
        'TRANSFERENCIA JOAO SILVA'   → 'XXXXXXXXXXXXX XXXX XXXXX'
        'R$ 1.500,00'                → 'R$ 9.999,99'
    """
    if texto is None:
        return ''
    s = str(texto)
    if s.strip().upper() in _PRESERVAR:
        return s

    def _sub_alpha(m):
        return 'X' * len(m.group())

    s = _ALPHA_RUN.sub(_sub_alpha, s)
    s = _DIGITO.sub('9', s)
    return s


def build_sample(filepath, max_linhas=6):
    """Monta a amostra enviada ao LLM.

    Cabeçalhos e texto fixo do template ficam em claro (são chrome do banco,
    não dado do usuário). Linhas de dados vão mascaradas.
    """
    ext = filepath.lower().rsplit('.', 1)[-1]
    if ext == 'pdf':
        return _sample_pdf(filepath, max_linhas)
    return _sample_tabular(filepath, max_linhas)


def _sample_tabular(filepath, max_linhas):
    import pandas as pd
    df = pd.read_csv(filepath, sep=None, engine='python', header=None, nrows=40) \
        if filepath.lower().endswith('.csv') \
        else pd.read_excel(filepath, header=None, nrows=40)

    linhas = [[('' if pd.isna(v) else str(v)) for v in row] for row in df.values.tolist()]
    return {
        'formato': 'tabular',
        # Primeiras 15 linhas em claro: contêm o cabeçalho, que é chrome.
        # Valores já mascarados — o cabeçalho é preservado por posição no prompt.
        'linhas': [[mask(c) for c in linha] for linha in linhas[:15]],
        'linhas_cabecalho_candidatas': linhas[:15],   # ver nota abaixo
        'n_colunas': max((len(l) for l in linhas), default=0),
    }
```

> **Nota importante sobre `linhas_cabecalho_candidatas`:** cabeçalho de coluna é chrome do banco e precisa ir em claro para o LLM identificar o papel de cada coluna. Mas o "cabeçalho" pode conter o nome do titular ou o IBAN (comum em extratos PT). **A implementação deve rodar um filtro de PII sobre essas linhas antes de enviar**: descartar qualquer célula que case com IBAN (`[A-Z]{2}\d{2}[A-Z0-9]{11,30}`), NIF/CPF/CNPJ, e-mail, ou sequência ≥ 8 dígitos. O teste de §11.3 cobre isso.

```python
def _sample_pdf(filepath, max_linhas):
    import pdfplumber
    with pdfplumber.open(filepath) as pdf:
        page = pdf.pages[0]
        words = page.extract_words(use_text_flow=False)
        # Agrupa por linha (y aproximado) e preserva x — o LLM precisa das
        # posições para propor as faixas_x.
        linhas = {}
        for w in words:
            chave = round(w['top'] / 3.0)
            linhas.setdefault(chave, []).append(w)

        saida = []
        for chave in sorted(linhas)[:25]:
            palavras = sorted(linhas[chave], key=lambda w: w['x0'])
            saida.append([
                {'t': mask(w['text']), 'x0': round(w['x0'], 1), 'x1': round(w['x1'], 1)}
                for w in palavras
            ])
        return {
            'formato': 'pdf_words',
            'largura': round(page.width, 1),
            'linhas': saida,
        }
```

---

### 8.4 `modules/extratos/validator.py`

O maior ganho por linha de código do projeto inteiro. Resolve P1, P2 e P3.

```python
from dataclasses import dataclass, field
from datetime import date, timedelta


@dataclass
class Check:
    nome: str
    peso: int
    passou: bool
    detalhe: str = None
    linhas: list = field(default_factory=list)   # índices suspeitos


@dataclass
class Resultado:
    score: int
    checks: list
    linhas_suspeitas: list

    def to_dict(self):
        return {
            'score': self.score,
            'checks': [c.__dict__ for c in self.checks],
            'linhas_suspeitas': self.linhas_suspeitas,
        }


PESOS = {
    'saldo_encadeado':    40,
    'cobertura':          25,
    'datas_periodo':      10,
    'sem_duplicatas':     10,
    'sem_data_fallback':  10,
    'sem_valor_zero':      5,
}

LIMIAR_AUTO   = 90   # CALIBRAR — acima disto e receita verified → importa direto
LIMIAR_PARCIAL = 60  # CALIBRAR — entre os dois → revisa só linhas suspeitas


def validate(txns, *, linhas_com_data_no_bruto=None, periodo=None,
             saldo_inicial=None, saldo_final=None):
    checks = []
    suspeitas = set()

    # ── 1. Saldo encadeado ────────────────────────────────────────────────
    # Só aplicável se a receita extraiu a coluna de saldo. É a checagem mais
    # forte: valida CADA linha individualmente, não só o total.
    com_saldo = [t for t in txns if t.get('saldo') is not None]
    if len(com_saldo) >= 2:
        divergentes = []
        for i in range(1, len(com_saldo)):
            ant, cur = com_saldo[i - 1], com_saldo[i]
            delta = round(float(cur['saldo']) - float(ant['saldo']), 2)
            esperado = round(_com_sinal(cur), 2)
            if abs(delta - esperado) > 0.01:
                divergentes.append(cur['linha_idx'])
        suspeitas.update(divergentes)
        checks.append(Check(
            'saldo_encadeado', PESOS['saldo_encadeado'], not divergentes,
            f'{len(com_saldo) - len(divergentes)}/{len(com_saldo)} linhas conferem',
            divergentes,
        ))
    elif saldo_inicial is not None and saldo_final is not None:
        soma = round(sum(_com_sinal(t) for t in txns), 2)
        esperado = round(float(saldo_final) - float(saldo_inicial), 2)
        ok = abs(soma - esperado) <= 0.01
        checks.append(Check('saldo_total', PESOS['saldo_encadeado'], ok,
                            f'soma={soma:.2f} esperado={esperado:.2f}'))
    else:
        # Sem saldo não dá para conferir — o peso migra para a cobertura.
        checks.append(Check('saldo_encadeado', 0, True, 'extrato sem coluna de saldo'))

    # ── 2. Cobertura ──────────────────────────────────────────────────────
    if linhas_com_data_no_bruto:
        ratio = len(txns) / max(linhas_com_data_no_bruto, 1)
        ok = ratio >= 0.95   # CALIBRAR
        checks.append(Check('cobertura', PESOS['cobertura'], ok,
                            f'{len(txns)} extraídas de ~{linhas_com_data_no_bruto} '
                            f'linhas com data no texto bruto'))
    else:
        checks.append(Check('cobertura', PESOS['cobertura'], len(txns) > 0,
                            f'{len(txns)} transações'))

    # ── 3. Datas dentro do período ────────────────────────────────────────
    if txns:
        datas = [t['data'] for t in txns if t.get('data')]
        if periodo:
            ini, fim = periodo
            fora = [t['linha_idx'] for t in txns
                    if t.get('data') and not (ini <= t['data'] <= fim)]
        else:
            # Sem período declarado: aceita janela de 400 dias e rejeita futuro.
            hoje = date.today()
            fora = [t['linha_idx'] for t in txns if t.get('data') and (
                t['data'] > hoje + timedelta(days=1) or
                t['data'] < hoje - timedelta(days=400)
            )]
        suspeitas.update(fora)
        checks.append(Check('datas_periodo', PESOS['datas_periodo'], not fora,
                            f'{len(fora)} datas fora do período', fora))

    # ── 4. Duplicatas exatas ──────────────────────────────────────────────
    vistos, dups = {}, []
    for t in txns:
        chave = (t.get('data'), (t.get('descricao') or '').strip(),
                 t.get('valor_original'))
        if chave in vistos:
            dups.append(t['linha_idx'])
        vistos[chave] = t['linha_idx']
    suspeitas.update(dups)
    checks.append(Check('sem_duplicatas', PESOS['sem_duplicatas'], not dups,
                        f'{len(dups)} linhas idênticas', dups))

    # ── 5. Data de fallback (corrupção silenciosa do parser antigo) ───────
    fallback = [t['linha_idx'] for t in txns if t.get('data_fallback')]
    suspeitas.update(fallback)
    checks.append(Check('sem_data_fallback', PESOS['sem_data_fallback'], not fallback,
                        f'{len(fallback)} datas não parseadas', fallback))

    # ── 6. Valores zero ───────────────────────────────────────────────────
    zeros = [t['linha_idx'] for t in txns
             if t.get('valor_original') in (None, 0, 0.0)]
    suspeitas.update(zeros)
    checks.append(Check('sem_valor_zero', PESOS['sem_valor_zero'], not zeros,
                        f'{len(zeros)} valores nulos', zeros))

    # ── Score ─────────────────────────────────────────────────────────────
    peso_total = sum(c.peso for c in checks) or 1
    obtido = sum(c.peso for c in checks if c.passou)
    score = round(100 * obtido / peso_total)

    return Resultado(score, checks, sorted(suspeitas))


def _com_sinal(t):
    v = float(t.get('valor_original') or 0)
    return -abs(v) if t.get('is_debit') else abs(v)
```

**Contagem de `linhas_com_data_no_bruto`:** extrair o texto bruto do arquivo e contar linhas que casam com uma regex de data genérica (`\d{1,2}[/.\-]\d{1,2}([/.\-]\d{2,4})?`). É a checagem que pega o caso "o parser leu 12 de 47 linhas e achou que estava tudo bem".

**Inferência determinística de `dayfirst`** (usada pelo executor, não pelo validador):

```python
def infer_dayfirst(strings_de_data, pais=None):
    """PT e BR são dayfirst. Só devolve False com PROVA (componente > 12)."""
    import re
    primeiro_maior_12 = False
    segundo_maior_12 = False
    for s in strings_de_data:
        m = re.match(r'^\s*(\d{1,2})[/.\-](\d{1,2})', str(s))
        if not m:
            continue
        a, b = int(m.group(1)), int(m.group(2))
        if a > 12:
            primeiro_maior_12 = True
        if b > 12:
            segundo_maior_12 = True
    if primeiro_maior_12 and not segundo_maior_12:
        return True
    if segundo_maior_12 and not primeiro_maior_12:
        return False
    return True   # default PT/BR
```

---

### 8.5 `modules/extratos/recipes.py` (executor)

Assinatura pública:

```python
def apply(spec: dict, filepath: str) -> list[dict]:
    """Executa a receita. Devolve lista de transações (§7.1) com `linha_idx`.

    Levanta ReceitaFalhou se a receita não produzir nenhuma linha.
    Levanta ArquivoIlegivel se o arquivo não puder ser aberto.
    NUNCA devolve [] silenciosamente.
    """
    estrategia = spec.get('estrategia')
    if estrategia == 'planilha':
        txns = _apply_planilha(spec, filepath)
    elif estrategia == 'pdf_tabela':
        txns = _apply_pdf_tabela(spec, filepath)
    elif estrategia == 'pdf_words':
        txns = _apply_pdf_words(spec, filepath)
    elif estrategia == 'linhas_regex':
        txns = _apply_linhas_regex(spec, filepath)
    else:
        raise ReceitaFalhou(f'Estratégia desconhecida: {estrategia!r}')

    if not txns:
        raise ReceitaFalhou(
            'A receita não extraiu nenhuma transação.',
            detalhe={'estrategia': estrategia},
        )
    return txns
```

**Reaproveitar do `parser.py` atual** (mover para `recipes.py`, sem alterar comportamento):

| Função a reaproveitar | Origem | Ajuste necessário |
|---|---|---|
| `_UNICODE_FIXES` / `_clean_text` | [parser.py:50-61](../../modules/extratos/parser.py) | Nenhum — está correto |
| `_parse_value` | [parser.py:64](../../modules/extratos/parser.py) | Aceitar `decimal`/`milhar` do spec em vez de inferir sempre |
| `_read_xml_xls` | [parser.py:222](../../modules/extratos/parser.py) | Nenhum |
| `_parse_pdf_words` (lógica de faixas x) | [parser.py:546](../../modules/extratos/parser.py) | Parametrizar as faixas pelo spec em vez de detectá-las |

**A reescrever:**

- `_parse_date` — **não pode mais devolver `'2023-01-01'`**. Deve devolver `(data, fallback: bool)`; o executor marca `data_fallback=True` na transação e o validador pega. Ver P3.
- Detecção de moeda — vem do `spec['moeda']` ou de um detector que olha o texto do documento. **Remover a inferência por nome de arquivo** ([parser.py:196-198](../../modules/extratos/parser.py)).

**Câmbio (P8):** coletar o conjunto `{(data, moeda)}` distinto e chamar `get_exchange_rate` uma vez por par, com cache local no escopo da importação.

---

### 8.6 `modules/extratos/induction.py`

Opcional por design. Se `ANTHROPIC_API_KEY` não estiver configurada ou a chamada falhar, `induzir()` devolve `None` e o fluxo cai no mapeador manual.

```python
import os
import json
from typing import Literal, Optional
from pydantic import BaseModel

MODELO = 'claude-opus-5'
MAX_TOKENS = 8000   # thinking está LIGADO por padrão no Opus 5:
                    # max_tokens limita thinking + resposta somados.


class ColunaMap(BaseModel):
    papel: Literal['data', 'data_valor', 'descricao', 'valor',
                   'debito', 'credito', 'saldo', 'tipo', 'ignorar']
    header: Optional[str]        # nome do cabeçalho (formato tabular)
    indice: Optional[int]        # índice da coluna (tabular sem cabeçalho)
    x_min: Optional[float]       # faixa x (pdf_words)
    x_max: Optional[float]


class ReceitaInduzida(BaseModel):
    estrategia: Literal['planilha', 'pdf_tabela', 'pdf_words', 'linhas_regex']
    banco_label: str
    pais: Literal['PT', 'BR', 'OUTRO']
    header_row: Optional[int]
    colunas: list[ColunaMap]
    linha_transacao_regex: Optional[str]
    ignorar_linhas_regex: list[str]
    sinal: Literal['colunas_separadas', 'valor_com_sinal', 'coluna_tipo']
    confianca: int               # 0-100, autoavaliação do modelo
    observacoes: str


SYSTEM = """Você mapeia a estrutura de extratos bancários de Portugal e do Brasil.

Você recebe uma AMOSTRA ANONIMIZADA: todos os dígitos foram substituídos por 9 e
todas as letras do conteúdo por X. A estrutura (posições, separadores, pontuação,
símbolos de moeda e nomes de cabeçalho) está preservada.

Sua única tarefa é identificar QUAL COLUNA É O QUÊ. Não tente ler valores, datas
ou descrições — eles foram mascarados de propósito e não são a sua tarefa.

Não infira: ordem dia/mês, separador decimal, ou moeda. Esses itens são
calculados deterministicamente pelo sistema a partir dos dados reais.

Se não conseguir identificar a estrutura com segurança, devolva confianca abaixo
de 50 e explique o motivo em observacoes."""


def induzir(sample: dict, pais_hint: str = None) -> Optional[dict]:
    """Devolve um dict `spec` (§6) ou None se a IA estiver indisponível."""
    if not os.getenv('ANTHROPIC_API_KEY'):
        return None
    try:
        import anthropic
        client = anthropic.Anthropic()
        resp = client.messages.parse(
            model=MODELO,
            max_tokens=MAX_TOKENS,
            system=SYSTEM,
            messages=[{
                'role': 'user',
                'content': (
                    f'País provável: {pais_hint or "desconhecido"}\n\n'
                    f'Amostra anonimizada:\n```json\n'
                    f'{json.dumps(sample, ensure_ascii=False, indent=1)}\n```'
                ),
            }],
            output_format=ReceitaInduzida,
        )
        receita = resp.parsed_output
        if receita.confianca < 50:   # CALIBRAR
            return None
        return _to_spec(receita)
    except Exception as e:
        import sys
        print(f'[induction] falhou: {type(e).__name__}: {e}', file=sys.stderr)
        return None


def _to_spec(r: ReceitaInduzida) -> dict:
    """Converte a saída achatada do LLM no formato spec (§6)."""
    spec = {
        'estrategia': r.estrategia,
        'sinal': r.sinal,
        'ignorar_linhas_regex': r.ignorar_linhas_regex,
        'moeda': None,      # derivado por código
        'dayfirst': None,   # derivado por código
        'decimal': None,    # derivado por código
    }
    if r.header_row is not None:
        spec['header_row'] = r.header_row
    if r.linha_transacao_regex:
        spec['linha_transacao_regex'] = r.linha_transacao_regex

    if r.estrategia == 'pdf_words':
        spec['faixas_x'] = {
            c.papel: [c.x_min, c.x_max]
            for c in r.colunas
            if c.papel != 'ignorar' and c.x_min is not None
        }
    else:
        por_nome = {c.papel: c.header for c in r.colunas
                    if c.papel != 'ignorar' and c.header}
        por_idx = {c.papel: c.indice for c in r.colunas
                   if c.papel != 'ignorar' and c.indice is not None}
        if por_nome:
            spec['colunas'] = por_nome
        if por_idx:
            spec['colunas_idx'] = por_idx
    return spec
```

**Notas de API (verificadas contra a documentação vigente):**

| Item | Valor |
|---|---|
| Model ID | `claude-opus-5` (string exata, sem sufixo de data) |
| Preço | $5 / 1M tokens de entrada, $25 / 1M de saída |
| Custo estimado por indução | ~2k entrada + ~600 saída ≈ **US$ 0,025** — pago **uma vez por banco** |
| Structured output | `client.messages.parse(..., output_format=ModeloPydantic)` → `resp.parsed_output` |
| Thinking | **Ligado por padrão** no Opus 5. `max_tokens` limita thinking + resposta juntos → não usar valores apertados |
| Parâmetros proibidos | `temperature`, `top_p`, `top_k` retornam **400** no Opus 5. Não incluir |
| `stop_reason: "refusal"` | Possível; `parse()` levanta exceção nesse caso — já coberta pelo `except` |
| Schema | Structured outputs exige `additionalProperties: false` e todos os campos em `required`. Por isso `colunas` é **lista de objetos com esquema fixo**, não um dict de chaves dinâmicas |

Se o custo por indução for preocupante em escala, `claude-haiku-4-5` ($1/$5) é uma alternativa a testar — mas só depois de o corpus de regressão existir, para medir a queda de qualidade objetivamente.

---

### 8.7 Integração em `routes.py`

Esqueleto do orquestrador. Substitui [routes.py:14-49](../../modules/extratos/routes.py).

```python
@bp.route('/extratos/importar', methods=['POST'])
@login_required
def importar():
    user = session['user_email']
    resultados = []

    for file in request.files.getlist('files[]'):
        if not file or not allowed_file(file.filename):
            continue
        filepath = _salvar_upload(file)
        try:
            resultados.append(_processar(filepath, file.filename, user,
                                         request.form.get('conta_bancaria')))
        except ExtratoError as e:
            imp_id = _criar_importacao_falha(user, file.filename, e)
            resultados.append({**e.to_dict(), 'importacao_id': imp_id,
                               'arquivo': file.filename})
        finally:
            _remover_upload(filepath)   # não reter arquivo do usuário

    if all('erro' in r for r in resultados):
        return jsonify({'importacoes': resultados}), 422
    return jsonify({'importacoes': resultados}), 200


def _processar(filepath, nome, user, conta):
    # 1. Fast path
    txns = standard.try_parse(filepath)         # OFX/CAMT/MT940 → None se não for
    receita = None

    if txns is None:
        # 2. Fingerprint
        fp, evid = fingerprint.compute(filepath)
        receita = receitas_db.buscar_por_fingerprint(fp)

        # 3. Indução
        if receita is None:
            sample = anonymizer.build_sample(filepath)
            spec = induction.induzir(sample)
            if spec is None:
                raise LayoutDesconhecido(
                    'Não foi possível identificar as colunas deste extrato.',
                    detalhe={'fingerprint': fp, 'evidencia': evid},
                )
            receita = receitas_db.criar(fp, spec, origem='llm', criada_por=user)

        # 4. Executor
        txns = recipes.apply(receita['spec'], filepath)

    # 5. Validação
    ctx = validator.contexto_do_arquivo(filepath)
    res = validator.validate(txns, **ctx)

    # 6. Sessão de importação
    precisa_revisao = (
        receita is None
        or receita['status'] != 'verified'
        or res.score < validator.LIMIAR_AUTO
    )
    imp_id = importacoes_db.criar(user, nome, receita, res, txns, conta)
    return {
        'importacao_id': imp_id,
        'arquivo': nome,
        'receita': _receita_resumo(receita),
        'precisa_revisao': precisa_revisao,
        'total_linhas': len(txns),
        **res.to_dict(),
        'transacoes': _serializar(txns, res),
    }
```

**`_remover_upload`:** hoje os arquivos ficam em `uploads/` indefinidamente ([routes.py:31](../../modules/extratos/routes.py)). Apagar após processar — são dados financeiros do usuário.

---

## 9. Interface (`templates/index.html`)

Sem build step e sem framework. Todo o JS é inline. Manter o padrão existente.

### 9.1 Faixa de confiança acima da tabela de revisão

Inserir antes de `#transactionsTable` ([index.html:2148](../../templates/index.html)):

```html
<div id="confidenceBanner" class="conf-banner" style="display:none;">
  <span class="conf-score"></span>
  <span class="conf-msg"></span>
  <button class="btn btn-xs" id="confDetailsBtn">Ver checagens</button>
</div>
```

Três estados:

| Score | Estado | Mensagem |
|---|---|---|
| ≥ 90 e receita `verified` | verde | *"47 transações · saldo confere · pronto para importar"* |
| 60-89 ou receita `proposed` | âmbar | *"3 linhas de 47 precisam da sua confirmação"* → filtra a tabela para `suspeita=true` |
| < 60 | vermelho | *"Não conseguimos ler este extrato com segurança"* → abre o mapeador |

**Revisão dirigida:** quando âmbar, marcar as linhas suspeitas com classe CSS e oferecer um toggle *"mostrar só as suspeitas"*. Nunca pedir que o usuário revise 47 linhas quando 3 são o problema.

### 9.2 Mapeador manual

Modal com uma tabela de pré-visualização (5 primeiras linhas do arquivo) e um `<select>` por coluna:

```
┌──────────────────────────────────────────────────────────┐
│  Como ler este extrato?                                  │
│  Banco: [Novo Banco          ]   País: [Portugal ▾]      │
│                                                          │
│  Coluna 1      Coluna 2       Coluna 3      Coluna 4     │
│  [Data     ▾]  [Descrição ▾]  [Débito  ▾]  [Saldo   ▾]   │
│  ──────────────────────────────────────────────────────  │
│  05-03-2026   TRF MB WAY      42,30        1.284,55      │
│  06-03-2026   COMPRA XPTO     15,00        1.269,55      │
│                                                          │
│  ⓘ Você faz isto uma vez. Os próximos extratos deste     │
│    banco serão lidos automaticamente.                    │
│                            [Cancelar]  [Testar leitura]  │
└──────────────────────────────────────────────────────────┘
```

Papéis disponíveis no select: `Data`, `Data valor`, `Descrição`, `Valor`, `Débito`, `Crédito`, `Saldo`, `Tipo (D/C)`, `Ignorar`.

Quando a indução por IA rodou, os selects vêm **pré-preenchidos** e a frase muda para *"Detectámos este mapeamento — confirme ou corrija"*. É a mesma tela; a IA só reduz o trabalho.

"Testar leitura" chama `POST /extratos/importacoes/<id>/mapeador` e mostra o resultado sem confirmar.

---

## 10. Fases de entrega

Cada fase é um PR. Máximo 400 linhas por PR conforme `CLAUDE.md` §4.3 — as fases 1 e 3 provavelmente precisam ser divididas em 2 PRs cada.

### Fase 0 — Multi-tenancy de categorias *(bloqueador de segurança, independente)*

**Escopo:** `modules/extratos/db.py`, `modules/extratos/routes.py`
**Entrega:** `categorias_aprendidas` ganha `user_email`; `guess_category` e `save_category_rule` passam a receber o usuário; migração faz backfill das regras existentes.

**Critérios de aceite:**
- [ ] Regra de categoria criada pelo usuário A não aparece para o usuário B
- [ ] Regras pré-existentes continuam funcionando para o usuário fundador
- [ ] Índice único é `(user_email, padrao_descricao)`

---

### Fase 1 — Validação, erros tipados e sessão de importação

**Escopo:** `errors.py`, `validator.py`, tabelas `extrato_importacoes` + `extrato_linhas_staging`, `routes.py`, banner na UI
**Depende de:** Fase 0

**Entrega:**
- Toda extração produz score e lista de checagens
- `except Exception: pass` eliminado do caminho de extração ([parser.py:699-780](../../modules/extratos/parser.py))
- `_parse_date` deixa de corromper: devolve flag de fallback em vez de `'2023-01-01'`
- Estado da importação passa a existir no servidor
- Banner de confiança + filtro de linhas suspeitas na UI

O parser atual continua sendo o motor de extração nesta fase. É a camada de confiança que muda.

**Critérios de aceite:**
- [ ] Extrato com coluna de saldo válido → `saldo_encadeado` passa, score ≥ 90
- [ ] Extrato com uma linha adulterada → `saldo_encadeado` falha e aponta o `linha_idx` correto
- [ ] PDF sem camada de texto → HTTP 422 com `erro: "arquivo_ilegivel"`, não 200 com lista vazia
- [ ] Data não parseável → linha marcada `suspeita`, **nunca** gravada como `2023-01-01`
- [ ] `grep -rn "except Exception:\s*pass" modules/extratos/` não retorna nada no caminho de extração
- [ ] Arquivo removido de `uploads/` após o processamento

---

### Fase 2 — Revisão dirigida e mapeador manual

**Escopo:** endpoints do mapeador, modal na UI, tabela `extrato_receitas` (mínima), `confirmar`/`descartar`
**Depende de:** Fase 1

**Entrega:** o usuário resolve sozinho um banco desconhecido. Zero IA. **É aqui que o cadastro pode ser aberto.**

**Critérios de aceite:**
- [ ] Um extrato de banco não suportado é importado com sucesso via mapeador manual, sem alteração de código
- [ ] O mapeamento é salvo como receita e reutilizado na importação seguinte do mesmo layout
- [ ] `POST /confirmar` grava as transações definitivas e promove a receita a `verified`
- [ ] Um usuário sem conhecimento técnico consegue completar o mapeador (teste com uma pessoa real)

---

### Fase 3 — Fingerprint e executor dirigido por receita

**Escopo:** `fingerprint.py`, `recipes.py`, migração das regras hardcoded para receitas seed
**Depende de:** Fase 2

**Entrega:** regra de banco vira dado. `_parse_pdf_millennium` ([parser.py:390](../../modules/extratos/parser.py)) e a heurística do Novo Banco ([parser.py:180](../../modules/extratos/parser.py)) viram linhas em `extrato_receitas` com `origem='seed'`.

**Critérios de aceite:**
- [ ] Dois extratos diferentes do mesmo banco produzem o **mesmo** fingerprint
- [ ] Extratos de bancos diferentes produzem fingerprints **diferentes**
- [ ] Millennium BCP e Novo Banco continuam sendo lidos, agora via receita seed
- [ ] Suporte a um banco novo é adicionável por `INSERT`, sem deploy
- [ ] Suite de regressão (§11) passa

---

### Fase 4 — Indução por LLM

**Escopo:** `anonymizer.py`, `induction.py`, integração no fluxo
**Depende de:** Fase 3

**Entrega:** o mapeador manual chega pré-preenchido. A revisão obrigatória continua.

**Critérios de aceite:**
- [ ] Teste de vazamento (§11.3) passa e é bloqueante no CI
- [ ] Sem `ANTHROPIC_API_KEY` configurada, o fluxo cai no mapeador manual **sem erro**
- [ ] Em ≥ 8 de 10 bancos do corpus, a sugestão da IA é aceita pelo usuário sem correção
- [ ] Custo medido por indução registrado em log

---

### Fase 5 — Fast path de formatos padrão + corpus de regressão

**Escopo:** `standard.py`, `ALLOWED_EXTENSIONS`, `__tests__/`, onboarding
**Depende de:** Fase 1 (independente das 2-4)

**Entrega:** OFX (BR) e CAMT.053/MT940 (PT) com um parser só. Onboarding passa a sugerir esses formatos quando o banco os oferece.

**Critérios de aceite:**
- [ ] `.ofx` e `.qfx` aceitos no upload
- [ ] OFX de 3 bancos brasileiros diferentes lidos pelo mesmo parser, score ≥ 95
- [ ] Suite de regressão roda em CI

---

## 11. Testes

### 11.1 Estrutura

```
modules/extratos/__tests__/
├── conftest.py
├── fixtures/
│   ├── pt_millennium_2026-01.pdf.json     # amostras ANONIMIZADAS, versionadas
│   ├── pt_novobanco_2026-02.xlsx.json
│   ├── br_nubank_2026-01.csv
│   └── esperado/
│       ├── pt_millennium_2026-01.json      # transações esperadas
│       └── pt_novobanco_2026-02.json
├── test_fingerprint.py
├── test_anonymizer.py      ← bloqueante
├── test_validator.py
├── test_recipes.py
└── test_regressao.py
```

**Fixtures nunca contêm dado financeiro real.** Gerar a partir de extratos reais passando pelo `anonymizer`, e revisar manualmente antes de commitar.

### 11.2 Regressão

```python
@pytest.mark.parametrize('caso', listar_fixtures())
def test_regressao(caso):
    spec = carregar_receita_seed(caso.receita)
    txns = recipes.apply(spec, caso.arquivo)
    esperado = json.load(open(caso.esperado))

    assert len(txns) == len(esperado)
    for real, exp in zip(txns, esperado):
        assert real['data'] == exp['data']
        assert abs(real['valor_original'] - exp['valor_original']) < 0.01
        assert real['is_debit'] == exp['is_debit']
```

Um banco novo suportado = uma fixture nova. **Isso é o que impede que consertar o Novo Banco quebre o Millennium.**

### 11.3 Teste de vazamento *(bloqueante — falha o build)*

```python
import re

PII = [
    (re.compile(r'[A-Z]{2}\d{2}[A-Z0-9]{11,30}'), 'IBAN'),
    (re.compile(r'\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b'), 'CPF'),
    (re.compile(r'\b\d{9}\b'), 'NIF'),
    (re.compile(r'[\w.+-]+@[\w-]+\.[\w.]+'), 'email'),
    (re.compile(r'\d{8,}'), 'sequência longa de dígitos'),
]


def test_amostra_nao_contem_digito_diferente_de_9():
    """Invariante forte: após mascarar, o único dígito possível é 9."""
    sample = anonymizer.build_sample('fixtures/extrato_com_pii.xlsx')
    texto = json.dumps(sample, ensure_ascii=False)
    encontrados = re.findall(r'[0-8]', texto)
    assert not encontrados, f'dígito não mascarado na amostra: {encontrados[:5]}'


def test_amostra_nao_contem_pii_conhecida():
    fixture = 'fixtures/extrato_com_pii.xlsx'   # nome, IBAN, NIF, e-mail plantados
    sample = anonymizer.build_sample(fixture)
    texto = json.dumps(sample, ensure_ascii=False)
    for padrao, nome in PII:
        assert not padrao.search(texto), f'{nome} vazou na amostra'
    for termo in ('JOAO', 'SILVA', 'PT50', 'joao@'):
        assert termo not in texto.upper(), f'{termo!r} vazou na amostra'
```

> ⚠️ Cuidado: `x0`/`x1` do PDF são floats reais e vão passar pelo teste de dígitos se serializados como números. **Serializar coordenadas como `int` arredondado e excluí-las explicitamente do teste**, ou usar chaves separadas que o teste ignora. Coordenadas são estrutura, não conteúdo — mas o teste precisa saber disso.

### 11.4 Cobertura mínima

Conforme `CLAUDE.md` §6.1: 80% em `validator.py`, `recipes.py`, `fingerprint.py`, `anonymizer.py`.

---

## 12. Segurança e privacidade

| Item | Regra |
|---|---|
| Arquivo do usuário | Apagado de `uploads/` imediatamente após o processamento |
| Chave da API | `ANTHROPIC_API_KEY` em variável de ambiente; documentar em `.env.example` e `render.yaml` |
| Saída de dados | **Apenas** `anonymizer.build_sample()`. Nenhum outro módulo pode chamar a API externa |
| PII em logs | Nunca logar descrição, valor ou nome de titular. Logar `fingerprint`, `score`, `receita_id`, `linha_idx` |
| Receitas compartilhadas | Contêm só estrutura. Auditar `spec` antes de promover a `verified` na primeira versão |
| Consentimento | Se a Fase 4 for ativada, a política de privacidade precisa mencionar o envio de amostra estrutural anonimizada a um processador terceiro (LGPD art. 7º / GDPR art. 6º) |

---

## 13. Observabilidade

Tabela ou log estruturado com, por importação:

- `fingerprint`, `receita_id`, `score`, `duracao_ms`, `origem_receita`, `precisou_revisao`, `n_correcoes`

Métricas derivadas:

| Métrica | Alvo | Ação se fora |
|---|---|---|
| % importações sem intervenção do mantenedor | > 95% | É a métrica de sucesso do projeto |
| % receitas `proposed` → `verified` sem correção | > 80% | Baixo = indução ruim; revisar o prompt |
| Taxa de falha por `receita_id` | < 5% | Alto = o banco mudou de layout; marcar `deprecated` |
| Custo de indução / mês | — | Acompanhar; migrar para Haiku se escalar |

---

## 14. Riscos

| Risco | Probabilidade | Mitigação |
|---|---|---|
| Fingerprint instável (banco muda rodapé todo mês) | Média | Calibrar `MAX_TOKENS` e o filtro de stopwords contra o corpus real na Fase 3; medir antes de escolher o limiar |
| Indução com alucinação de coluna | Média | Revisão obrigatória (R3) é a rede de segurança; a validação de saldo pega o erro numérico |
| PDF digitalizado (sem camada de texto) | Alta | Erro tipado `arquivo_ilegivel` com mensagem clara. **OCR está fora de escopo** |
| Extrato sem coluna de saldo | Alta | A checagem mais forte fica indisponível; o peso migra para cobertura. Score máximo cai — ajustar `LIMIAR_AUTO` por presença de saldo |
| Custo da API cresce com o número de bancos | Baixa | Custo é uma vez por banco, não por importação. ~US$ 0,03 × N bancos |
| Open Banking torna o parser irrelevante | Média (PT) | Registrado no ADR-001. Revisitar ao fim da Fase 3 |

---

## 15. Fora de escopo

Explicitamente **não** entra neste plano:

- **OCR** de extratos digitalizados / fotografados
- **Open Banking** (PSD2 / Open Finance) — registrado como risco estratégico no ADR-001
- Categorização automática por IA — problema diferente, não confundir com extração
- Reescrita do `templates/index.html` ou introdução de build step
- Remoção do `parser.py` atual — permanece como fallback até a Fase 5 no mínimo

---

## 16. Checklist de PR

Conforme `CLAUDE.md` §6.3, mais os itens específicos deste módulo:

```
[ ] Segue a estrutura de módulos definida em §4.2
[ ] Nenhum import cruzado: recipes/validator/fingerprint/anonymizer NÃO importam induction
[ ] Tipos definidos; sem `any` / dict solto sem contrato
[ ] Nenhum `except Exception: pass` no caminho de extração
[ ] Nenhuma condição por nome de banco ou nome de arquivo
[ ] Testes adicionados/atualizados; test_anonymizer passa
[ ] Fixture nova adicionada se o PR suporta um banco novo
[ ] Sem secrets em código
[ ] Commit message no formato Conventional Commits
[ ] < 400 linhas (exceto scaffolding inicial)
[ ] .context/architecture.md atualizado se a arquitetura mudou
```

---

## Apêndice A — Ordem de leitura sugerida para o desenvolvedor

1. Este documento, §2 e §4
2. [ADR-001](../../.context/decisions/ADR-001-receitas-de-extrato-como-dado.md)
3. [`modules/extratos/parser.py`](../../modules/extratos/parser.py) — funções `process_file` (l.699), `_df_to_transactions` (l.90), `_parse_pdf_words` (l.546)
4. [`modules/extratos/routes.py`](../../modules/extratos/routes.py) — 108 linhas, leitura completa
5. [`db/connection.py`](../../db/connection.py) — entender o wrapper `PGConnection`
6. [`templates/index.html`](../../templates/index.html) — apenas o bloco `#uploadSection` / `#reviewSection` (l. 2120-2180) e o handler de upload (l. 8490-8545)
