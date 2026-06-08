# MyFinance 2.0 — Plano de Integração Open Finance
**Versão:** 1.0 | **Data:** 2026-05-26 | **Autor:** Arquitetura técnica gerada com Claude

---

## 1. Visão Geral Estratégica

O objetivo é transformar o MyFinance 2.0 de um sistema que **recebe extratos manualmente** para um sistema que **puxa dados bancários automaticamente** via Open Finance, eliminando uploads e garantindo dados em tempo real.

### 1.1 Escopo Geográfico

| Região | Padrão | Regulador | Status |
|--------|--------|-----------|--------|
| Portugal / UE | PSD2 — Berlin Group NextGenPSD2 | Banco de Portugal / BCE | Obrigatório desde Set/2019 |
| Brasil | Open Finance Brasil (OFB) | Banco Central do Brasil (BCB) | Fase 2 ativa desde Jul/2021 |

### 1.2 Contas Identificadas no Projeto

Com base nos extratos já presentes no workspace:

| Banco | País | Formato atual | Target API |
|-------|------|---------------|------------|
| Novo Banco (NB) | PT 🇵🇹 | XLS / PDF / XML (manual) | GoCardless / TrueLayer PSD2 |
| Revolut | EU 🇪🇺 | CSV (manual) | Revolut Open API (PSD2 nativo) |
| Santander | BR 🇧🇷 | XLS (manual) | Belvo / Open Finance Brasil |

---

## 2. Seleção de Agregadores (Providers)

A abordagem recomendada usa **agregadores** em vez de conectar diretamente aos bancos, pois:
- Já possuem certificação regulatória (eIDAS PT/UE, autorização BCB BR)
- Normalizam os dados de centenas de bancos
- Mantêm a conformidade com mudanças regulatórias

### 2.1 Europa / Portugal — GoCardless (ex-Nordigen)

**Por quê GoCardless:**
- Free tier generoso: 50 requisições/dia grátis para desenvolvimento
- Cobre 2.500+ bancos europeus incluindo Novo Banco Portugal
- Standard Berlin Group (compatível com todos os bancos PSD2)
- Sem necessidade de licença AISP própria

**Alternativa:** TrueLayer (mais robusto para produção, custo por conexão)

**Endpoint base:** `https://bankaccountdata.gocardless.com/api/v2/`

### 2.2 Brasil — Belvo

**Por quê Belvo:**
- Suporte nativo ao ecossistema Open Finance Brasil
- Cobre Santander BR, Itaú, Bradesco, Nubank, C6 Bank
- SDK Python disponível
- Sandbox gratuito para desenvolvimento

**Alternativa:** Pluggy (alternativa nacional 100% brasileira, também excelente)

---

## 3. Arquitetura da Integração

### 3.1 Diagrama de Fluxo

```
┌─────────────────────────────────────────────────────────────────┐
│                        MyFinance 2.0                            │
│                                                                 │
│  ┌──────────────┐    ┌─────────────────┐    ┌───────────────┐  │
│  │   Frontend   │───▶│  Flask Blueprint │───▶│  open_finance │  │
│  │  (index.html)│◀───│  /open_finance/* │◀───│   module      │  │
│  └──────────────┘    └─────────────────┘    └───────┬───────┘  │
│                                                      │          │
│                                              ┌───────▼───────┐  │
│                                              │  Supabase DB  │  │
│                                              │  (novas tabelas│  │
│                                              └───────────────┘  │
└──────────────────────────────┬──────────────────────────────────┘
                               │ HTTPS + OAuth2 / API Key
           ┌───────────────────┼───────────────────┐
           ▼                   ▼                   ▼
   ┌───────────────┐  ┌────────────────┐  ┌──────────────┐
   │  GoCardless   │  │     Belvo      │  │   Revolut    │
   │  (PSD2 / PT)  │  │   (OFB / BR)   │  │  Open API    │
   └───────┬───────┘  └───────┬────────┘  └──────┬───────┘
           │                  │                   │
    ┌──────▼────┐      ┌──────▼────┐      ┌──────▼────┐
    │ Novo Banco│      │ Santander │      │  Revolut  │
    │    (PT)   │      │    (BR)   │      │   (EU)    │
    └───────────┘      └───────────┘      └───────────┘
```

### 3.2 Fluxo OAuth2 (PSD2 / GoCardless)

```
Usuário clica "Conectar Novo Banco"
        │
        ▼
MyFinance → GoCardless: POST /agreements/enduser/
                             (institution_id: NOVO_BANCO_PT)
        │
        ▼ retorna: link de autorização do banco
        │
Usuário é redirecionado → Novo Banco (login no banco)
        │
        ▼ banco redireciona de volta para:
        │  /open_finance/callback?ref={requisition_id}
        ▼
MyFinance salva requisition_id + account_ids no Supabase
        │
        ▼
Sync periódico: GET /accounts/{id}/transactions/
                          (usando access token armazenado)
```

---

## 4. Novo Módulo Flask — `modules/open_finance/`

### 4.1 Estrutura de Ficheiros

```
modules/open_finance/
├── __init__.py
├── routes.py          # Blueprint Flask — endpoints HTTP
├── db.py              # init_tables() + queries Supabase
├── providers/
│   ├── __init__.py
│   ├── base.py        # Classe abstrata OpenFinanceProvider
│   ├── gocardless.py  # Provider GoCardless (PT/EU)
│   ├── belvo.py       # Provider Belvo (BR)
│   └── revolut.py     # Provider Revolut Open API
├── sync.py            # Worker de sincronização periódica
├── mapper.py          # Normaliza transações → formato MyFinance
└── crypto.py          # Encrypt/Decrypt tokens em repouso
```

### 4.2 Blueprint Routes (`routes.py`)

```python
# Endpoints expostos
GET  /open_finance/institutions          # Lista bancos disponíveis por país
POST /open_finance/connect               # Inicia fluxo OAuth (retorna redirect_url)
GET  /open_finance/callback              # Recebe retorno do banco após autorização
GET  /open_finance/connections           # Lista contas conectadas do usuário
POST /open_finance/sync/{account_id}     # Força sync manual de uma conta
DELETE /open_finance/connections/{id}    # Desconecta uma conta bancária
GET  /open_finance/status               # Status de cada conexão (ativa/expirada)
```

### 4.3 Provider Base (Polimorfismo)

```python
# modules/open_finance/providers/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional
from datetime import date

@dataclass
class BankTransaction:
    """Formato normalizado — independente do provider"""
    external_id: str         # ID único do banco
    date: date
    amount: float            # Negativo = débito, Positivo = crédito
    currency: str            # EUR, BRL, USD...
    description: str
    merchant_name: Optional[str]
    category_hint: Optional[str]
    balance_after: Optional[float]
    raw_data: dict           # Payload original para auditoria

class OpenFinanceProvider(ABC):
    
    @abstractmethod
    def get_auth_url(self, account_id: str, redirect_uri: str) -> str:
        """Retorna URL de autorização do banco"""
        pass
    
    @abstractmethod
    def exchange_code(self, code: str, state: str) -> dict:
        """Troca authorization code por access/refresh tokens"""
        pass
    
    @abstractmethod
    def get_accounts(self, connection_id: str) -> List[dict]:
        """Lista contas bancárias disponíveis"""
        pass
    
    @abstractmethod
    def get_transactions(
        self, 
        account_id: str, 
        date_from: date, 
        date_to: date
    ) -> List[BankTransaction]:
        """Busca transações no período"""
        pass
    
    @abstractmethod
    def refresh_token(self, connection_id: str) -> bool:
        """Renova access token expirado"""
        pass
```

### 4.4 Provider GoCardless — PT/EU

```python
# modules/open_finance/providers/gocardless.py
import requests
from .base import OpenFinanceProvider, BankTransaction

GOCARDLESS_BASE = "https://bankaccountdata.gocardless.com/api/v2"

class GoCardlessProvider(OpenFinanceProvider):
    
    def __init__(self, secret_id: str, secret_key: str):
        self.secret_id = secret_id
        self.secret_key = secret_key
        self._token = None
    
    def _get_token(self) -> str:
        """Obtém JWT de acesso à API GoCardless"""
        resp = requests.post(f"{GOCARDLESS_BASE}/token/new/", json={
            "secret_id": self.secret_id,
            "secret_key": self.secret_key
        })
        resp.raise_for_status()
        self._token = resp.json()["access"]
        return self._token
    
    def get_auth_url(self, institution_id: str, redirect_uri: str) -> dict:
        """
        Cria requisition (fluxo de consentimento) e retorna link de autorização
        institution_id exemplos: 
          - NOVO_BANCO_PT (Novo Banco Portugal)
          - REVOLUT_REVOGB21 (Revolut EU)
          - MONTEPIO_MPIOPTPL (Montepio)
        """
        token = self._get_token()
        headers = {"Authorization": f"Bearer {token}"}
        
        # 1. Criar agreement (consentimento de 90 dias)
        agreement = requests.post(f"{GOCARDLESS_BASE}/agreements/enduser/", 
            headers=headers,
            json={
                "institution_id": institution_id,
                "max_historical_days": 730,     # 2 anos de histórico
                "access_valid_for_days": 90,
                "access_scope": ["balances", "details", "transactions"]
            }
        ).json()
        
        # 2. Criar requisition (sessão de autorização)
        requisition = requests.post(f"{GOCARDLESS_BASE}/requisitions/", 
            headers=headers,
            json={
                "redirect": redirect_uri,
                "institution_id": institution_id,
                "agreement": agreement["id"],
                "reference": f"myfinance_{institution_id}",
                "user_language": "PT"
            }
        ).json()
        
        return {
            "redirect_url": requisition["link"],
            "requisition_id": requisition["id"],
            "agreement_id": agreement["id"]
        }
    
    def get_transactions(self, account_id, date_from, date_to) -> list:
        token = self._get_token()
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(
            f"{GOCARDLESS_BASE}/accounts/{account_id}/transactions/",
            headers=headers,
            params={"date_from": str(date_from), "date_to": str(date_to)}
        )
        resp.raise_for_status()
        raw = resp.json()
        
        transactions = []
        for t in raw.get("transactions", {}).get("booked", []):
            transactions.append(BankTransaction(
                external_id=t.get("transactionId", t.get("internalTransactionId")),
                date=t["bookingDate"],
                amount=float(t["transactionAmount"]["amount"]),
                currency=t["transactionAmount"]["currency"],
                description=t.get("remittanceInformationUnstructured", 
                                  t.get("creditorName", "Sem descrição")),
                merchant_name=t.get("creditorName"),
                category_hint=None,
                balance_after=float(t.get("balanceAfterTransaction", {})
                                     .get("balanceAmount", {})
                                     .get("amount", 0)) or None,
                raw_data=t
            ))
        return transactions
```

---

## 5. Schema Supabase — Novas Tabelas

```sql
-- =============================================================
-- MyFinance 2.0 — Open Finance Schema Extension
-- Adicionar ao supabase_schema.sql
-- =============================================================

-- Tabela 1: Provedores disponíveis (GoCardless, Belvo, Revolut)
CREATE TABLE IF NOT EXISTS of_providers (
    id SERIAL PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,           -- 'gocardless', 'belvo', 'revolut'
    name TEXT NOT NULL,
    country TEXT NOT NULL,               -- 'PT', 'BR', 'EU'
    logo_url TEXT,
    is_active BOOLEAN DEFAULT TRUE
);

-- Tabela 2: Conexões bancárias autorizadas por usuário
CREATE TABLE IF NOT EXISTS of_connections (
    id SERIAL PRIMARY KEY,
    user_email TEXT NOT NULL REFERENCES users(email) ON DELETE CASCADE,
    provider_code TEXT NOT NULL,         -- 'gocardless'
    institution_id TEXT NOT NULL,        -- 'NOVO_BANCO_PT'
    institution_name TEXT,               -- 'Novo Banco'
    requisition_id TEXT,                 -- ID externo GoCardless
    agreement_id TEXT,                   -- ID do consentimento
    
    -- Tokens (criptografados com AES-256)
    access_token_enc TEXT,
    refresh_token_enc TEXT,
    token_expires_at TIMESTAMPTZ,
    
    status TEXT DEFAULT 'pending',       -- pending | active | expired | revoked | error
    last_sync_at TIMESTAMPTZ,
    last_sync_error TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(user_email, institution_id)
);

-- Tabela 3: Contas bancárias individuais por conexão
CREATE TABLE IF NOT EXISTS of_accounts (
    id SERIAL PRIMARY KEY,
    connection_id INTEGER NOT NULL REFERENCES of_connections(id) ON DELETE CASCADE,
    user_email TEXT NOT NULL,
    
    external_account_id TEXT NOT NULL,   -- ID no provider (GoCardless/Belvo)
    iban TEXT,
    account_number TEXT,
    account_name TEXT,                   -- 'Conta Ordenado', 'Conta Poupança'
    account_type TEXT,                   -- 'CACC', 'SVGS', 'TRAN'
    currency TEXT DEFAULT 'EUR',
    
    -- Saldo mais recente
    balance_current DECIMAL(15,2),
    balance_available DECIMAL(15,2),
    balance_updated_at TIMESTAMPTZ,
    
    -- Vincular à cad_contas existente
    cad_conta_id INTEGER REFERENCES cad_contas(id),
    
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(connection_id, external_account_id)
);

-- Tabela 4: Transações importadas via Open Finance
CREATE TABLE IF NOT EXISTS of_transactions (
    id SERIAL PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES of_accounts(id) ON DELETE CASCADE,
    user_email TEXT NOT NULL,
    
    external_id TEXT NOT NULL,           -- ID único do banco (evita duplicatas)
    transaction_date DATE NOT NULL,
    booking_date DATE,
    value_date DATE,
    
    amount DECIMAL(15,2) NOT NULL,       -- Negativo = débito
    currency TEXT NOT NULL DEFAULT 'EUR',
    description TEXT,
    merchant_name TEXT,
    merchant_category TEXT,
    
    -- Campos para conciliação com despesas_mensais
    mapped_to_expense_id INTEGER,        -- FK para despesas_mensais.id (após mapeamento)
    mapping_status TEXT DEFAULT 'pending', -- pending | mapped | ignored | manual
    
    -- Categorização
    category_suggested TEXT,
    category_final TEXT,
    
    -- Dados brutos para auditoria
    raw_payload JSONB,
    
    imported_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(account_id, external_id)      -- Garante idempotência
);

-- Tabela 5: Log de sincronizações
CREATE TABLE IF NOT EXISTS of_sync_log (
    id SERIAL PRIMARY KEY,
    connection_id INTEGER REFERENCES of_connections(id),
    account_id INTEGER REFERENCES of_accounts(id),
    
    sync_type TEXT,                      -- 'manual' | 'scheduled' | 'webhook'
    status TEXT,                         -- 'success' | 'partial' | 'failed'
    transactions_new INTEGER DEFAULT 0,
    transactions_duplicate INTEGER DEFAULT 0,
    error_message TEXT,
    
    started_at TIMESTAMPTZ DEFAULT NOW(),
    finished_at TIMESTAMPTZ
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_of_transactions_user_date 
    ON of_transactions(user_email, transaction_date DESC);

CREATE INDEX IF NOT EXISTS idx_of_transactions_mapping 
    ON of_transactions(user_email, mapping_status) 
    WHERE mapping_status = 'pending';

CREATE INDEX IF NOT EXISTS idx_of_connections_user 
    ON of_connections(user_email, status);
```

---

## 6. Módulo de Sync e Reconciliação

### 6.1 Worker de Sincronização (`sync.py`)

```python
# modules/open_finance/sync.py
from datetime import date, timedelta
from db.connection import get_connection
from .providers.gocardless import GoCardlessProvider
from .mapper import map_transaction_to_expense
from .db import (save_transaction, get_active_connections, 
                 update_connection_sync, log_sync)

def sync_all_users():
    """Chamado pelo scheduler (APScheduler ou Render Cron Job)"""
    conn = get_connection()
    connections = get_active_connections(conn)
    conn.close()
    
    for connection in connections:
        try:
            sync_connection(connection)
        except Exception as e:
            log_sync_error(connection['id'], str(e))

def sync_connection(connection: dict) -> dict:
    """
    Sincroniza uma conexão bancária específica.
    Idempotente: usa UNIQUE(account_id, external_id) para evitar duplicatas.
    """
    provider = _get_provider(connection['provider_code'])
    
    # Janela de sync: últimos 30 dias ou desde último sync
    last_sync = connection.get('last_sync_at')
    date_from = (last_sync.date() - timedelta(days=2)) if last_sync \
                else (date.today() - timedelta(days=30))
    date_to = date.today()
    
    stats = {"new": 0, "duplicate": 0, "errors": 0}
    
    conn = get_connection()
    accounts = get_accounts_for_connection(conn, connection['id'])
    
    for account in accounts:
        transactions = provider.get_transactions(
            account['external_account_id'], 
            date_from, 
            date_to
        )
        
        for tx in transactions:
            result = save_transaction(conn, account, tx)
            if result == 'new':
                stats["new"] += 1
                # Auto-categorização via IA (reutiliza lógica existente)
                category = guess_category(tx.description)
                if category != 'Não Categorizado':
                    auto_map_transaction(conn, tx, account['user_email'])
            elif result == 'duplicate':
                stats["duplicate"] += 1
    
    update_connection_sync(conn, connection['id'])
    log_sync(conn, connection['id'], 'success', stats)
    conn.close()
    return stats
```

### 6.2 Mapeador de Transações (`mapper.py`)

```python
# modules/open_finance/mapper.py
"""
Reconcilia transações Open Finance com despesas_mensais existentes.
Reutiliza a lógica de categorias aprendidas (categorias_aprendidas).
"""
from modules.extratos.db import guess_category
from db.connection import get_connection

def map_transaction_to_expense(of_transaction: dict, user_email: str) -> int | None:
    """
    Tenta mapear uma transação OF para uma despesa existente.
    Retorna o ID de despesas_mensais se encontrado, None caso contrário.
    
    Estratégia de matching:
    1. Match por data + valor exato (±0.01) → alta confiança
    2. Match por descrição parcial + período → média confiança
    3. Sem match → cria nova entrada pendente de revisão manual
    """
    conn = get_connection()
    
    # Busca despesa na mesma data com mesmo valor
    cursor = conn.execute('''
        SELECT id FROM despesas_mensais
        WHERE user_email = %s
          AND ABS(valor_eur - %s) < 0.01
          AND data BETWEEN %s::date - INTERVAL '2 days' 
                       AND %s::date + INTERVAL '2 days'
          AND status_pago = 'Pendente'
        ORDER BY ABS(valor_eur - %s), ABS(data::date - %s::date)
        LIMIT 1
    ''', (user_email, abs(of_transaction['amount']), 
          of_transaction['transaction_date'],
          of_transaction['transaction_date'],
          abs(of_transaction['amount']),
          of_transaction['transaction_date']))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return row['id']
    return None

def auto_create_from_transaction(of_transaction: dict, user_email: str) -> int:
    """
    Cria automaticamente uma despesa_mensal a partir de uma transação OF.
    Usada quando não há matching com lançamento existente.
    """
    category = guess_category(of_transaction['description'])
    
    conn = get_connection()
    cursor = conn.execute('''
        INSERT INTO despesas_mensais 
        (user_email, data, descricao, valor_original, moeda, valor_eur,
         categoria_final, status_pago, mes_referencia, conta_bancaria)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'Pago', %s, %s)
        RETURNING id
    ''', (
        user_email,
        of_transaction['transaction_date'],
        of_transaction['description'],
        abs(of_transaction['amount']),
        of_transaction['currency'],
        abs(of_transaction['amount']),  # converter se necessário
        category,
        of_transaction['transaction_date'][:7],  # YYYY-MM
        of_transaction.get('account_name', '')
    ))
    new_id = cursor.fetchone()['id']
    conn.commit()
    conn.close()
    return new_id
```

---

## 7. Segurança

### 7.1 Criptografia de Tokens em Repouso

```python
# modules/open_finance/crypto.py
"""
Tokens OAuth (access_token, refresh_token) são dados sensíveis.
Devem ser criptografados antes de persistir no Supabase.
Usa AES-256-GCM via biblioteca cryptography (já está no requirements.txt via dependências).
"""
import os
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

def get_encryption_key() -> bytes:
    """Chave de 32 bytes (256 bits) — vem de variável de ambiente"""
    key_b64 = os.environ.get("OF_ENCRYPTION_KEY")
    if not key_b64:
        raise RuntimeError("OF_ENCRYPTION_KEY não configurada")
    return base64.b64decode(key_b64)

def encrypt_token(plaintext: str) -> str:
    """Retorna token criptografado em base64 (nonce + ciphertext)"""
    key = get_encryption_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96 bits
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + ciphertext).decode()

def decrypt_token(encrypted_b64: str) -> str:
    """Decifra token armazenado"""
    key = get_encryption_key()
    aesgcm = AESGCM(key)
    data = base64.b64decode(encrypted_b64)
    nonce, ciphertext = data[:12], data[12:]
    return aesgcm.decrypt(nonce, ciphertext, None).decode()
```

### 7.2 Checklist de Segurança

| Item | Implementação | Prioridade |
|------|---------------|------------|
| Tokens criptografados em repouso | AES-256-GCM (`crypto.py`) | 🔴 Crítica |
| HTTPS obrigatório | Render.com já força TLS | 🔴 Crítica |
| Tokens nunca logados | Remover de logs Flask | 🔴 Crítica |
| State parameter CSRF (OAuth) | UUID v4 por sessão | 🔴 Crítica |
| Refresh automático de tokens | `sync.py` verifica expiração | 🟡 Alta |
| Rate limiting nos endpoints OF | Flask-Limiter (100/hora) | 🟡 Alta |
| Auditoria de acessos | Tabela `of_sync_log` | 🟡 Alta |
| Revogação de consentimento | Endpoint DELETE + chamada ao provider | 🟡 Alta |
| Dados mínimos (GDPR/LGPD) | Não armazenar raw_payload em produção | 🟢 Média |

---

## 8. Variáveis de Ambiente Necessárias

```bash
# Adicionar ao .env (nunca versionar) e às variáveis Render.com

# Open Finance — Chave de criptografia (gerar: python -c "import os,base64; print(base64.b64encode(os.urandom(32)).decode())")
OF_ENCRYPTION_KEY=<base64_32_bytes>

# GoCardless (PT/EU) — https://bankaccountdata.gocardless.com/
GOCARDLESS_SECRET_ID=<seu_secret_id>
GOCARDLESS_SECRET_KEY=<sua_secret_key>

# Belvo (BR) — https://dashboard.belvo.com/
BELVO_SECRET_ID=<seu_secret_id>
BELVO_SECRET_PASSWORD=<sua_password>
BELVO_ENV=sandbox  # ou production

# Revolut Business Open API (se aplicável)
REVOLUT_CLIENT_ID=<client_id>
REVOLUT_PRIVATE_KEY_PATH=<path_to_pem>

# URL base para redirect OAuth (obrigatório)
APP_BASE_URL=https://myfinance.onrender.com
```

---

## 9. Registro no `app.py`

```python
# Adicionar ao bloco de registro de Blueprints em app.py

from modules.open_finance.routes import open_finance_bp

# ... após os outros blueprints:
app.register_blueprint(open_finance_bp, url_prefix='/open_finance')

# Inicializar scheduler para sync automático (APScheduler)
from apscheduler.schedulers.background import BackgroundScheduler
from modules.open_finance.sync import sync_all_users

if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
    scheduler = BackgroundScheduler(timezone="Europe/Lisbon")
    scheduler.add_job(
        func=sync_all_users,
        trigger="interval",
        hours=6,               # Sync a cada 6 horas
        id='open_finance_sync',
        replace_existing=True
    )
    scheduler.start()
```

---

## 10. Impacto no Frontend (`index.html`)

### 10.1 Nova Aba "Open Finance"

Adicionar nova aba/seção na SPA com:

```
╔══════════════════════════════════════════════════════╗
║  🏦  OPEN FINANCE — Contas Conectadas                 ║
╠══════════════════════════════════════════════════════╣
║  [+ Conectar Nova Conta]                             ║
║                                                      ║
║  ┌──────────────────────────────────────────────┐    ║
║  │ 🏦 Novo Banco PT          ✅ Ativo           │    ║
║  │ IBAN: PT50 0007 0000 ****  Saldo: €2.847,50  │    ║
║  │ Último sync: há 2 horas   [Sync] [Detalhes]  │    ║
║  └──────────────────────────────────────────────┘    ║
║                                                      ║
║  ┌──────────────────────────────────────────────┐    ║
║  │ 💳 Revolut EU             ✅ Ativo           │    ║
║  │ IBAN: LT12 3250 ****      Saldo: €487,20     │    ║
║  │ Último sync: há 1 hora    [Sync] [Detalhes]  │    ║
║  └──────────────────────────────────────────────┘    ║
║                                                      ║
║  📥 Transações Pendentes de Revisão: 12              ║
║  [Revisar e Mapear Transações]                       ║
╚══════════════════════════════════════════════════════╝
```

### 10.2 Tela de Revisão de Transações

```
╔══════════════════════════════════════════════════════════════╗
║  📥 Transações Pendentes — Revisão Manual                    ║
╠══════════════════════════════════════════════════════════════╣
║  Data       │ Descrição          │ Valor    │ Ação           ║
║─────────────┼────────────────────┼──────────┼────────────────║
║  24/05/2026 │ LIDL PORTO         │ -€47,30  │ [✓Despesa][✗]  ║
║  23/05/2026 │ SALARIO EMPRESA X  │ +€3200   │ [✓Receita][✗]  ║
║  22/05/2026 │ MB WAY JOAO S      │ -€150    │ [✓Despesa][✗]  ║
╚══════════════════════════════════════════════════════════════╝
```

---

## 11. Plano de Implementação em Fases

### Fase 1 — Foundation (2 semanas)
**Objetivo:** Infraestrutura base, sem UI visível para usuário

- [ ] Criar schema SQL (5 tabelas + índices)
- [ ] Implementar `crypto.py` + gerar `OF_ENCRYPTION_KEY`
- [ ] Criar `modules/open_finance/__init__.py` + `db.py` + `routes.py` (esqueleto)
- [ ] Registrar blueprint em `app.py`
- [ ] Criar conta GoCardless sandbox (gratuito)
- [ ] Criar conta Belvo sandbox (gratuito)
- [ ] Adicionar variáveis de ambiente no Render.com

**Entrega:** Endpoints `/open_finance/health` e `/open_finance/institutions` funcionando

---

### Fase 2 — Conexão PT/EU (2 semanas)
**Objetivo:** Conectar Novo Banco Portugal via GoCardless

- [ ] Implementar `providers/gocardless.py` (auth + transactions)
- [ ] Implementar fluxo OAuth completo (`/connect` → callback → salvar tokens)
- [ ] Implementar `GET /open_finance/connections` + listar contas
- [ ] Testar com instituição sandbox GoCardless
- [ ] Adicionar UI básica (botão "Conectar Banco" em `index.html`)
- [ ] Teste end-to-end: conectar → autorizar → listar contas

**Entrega:** Usuário consegue conectar Novo Banco e ver contas (sem ainda importar transações)

---

### Fase 3 — Import de Transações (2 semanas)
**Objetivo:** Importar e exibir transações automaticamente

- [ ] Implementar `sync.py` (sync manual via endpoint POST)
- [ ] Implementar `mapper.py` (reconciliação com despesas_mensais)
- [ ] Salvar transações em `of_transactions` (idempotente)
- [ ] Reutilizar `categorias_aprendidas` para auto-categorização
- [ ] UI: tela de revisão de transações pendentes
- [ ] Endpoint para confirmar/ignorar transações

**Entrega:** Transações do Novo Banco aparecem automaticamente no MyFinance

---

### Fase 4 — Brasil + Scheduler (2 semanas)
**Objetivo:** Suporte Santander BR + sync automático

- [ ] Implementar `providers/belvo.py`
- [ ] Testar com Santander BR sandbox Belvo
- [ ] Implementar APScheduler para sync a cada 6h
- [ ] Dashboard de status das conexões
- [ ] Alertas de conexão expirada (email)
- [ ] Botão "Desconectar" com revogação de consentimento

**Entrega:** Sistema totalmente automatizado PT + BR

---

### Fase 5 — Produção & Conformidade (1 semana)
**Objetivo:** Hardening para produção

- [ ] Remover raw_payload do armazenamento (apenas metadados)
- [ ] Rate limiting com Flask-Limiter
- [ ] Página de consentimento GDPR/LGPD para usuário
- [ ] Testes automatizados dos providers (pytest + mocks)
- [ ] Documentação dos endpoints (README ou Swagger)
- [ ] Monitorização via `/open_finance/status`

---

## 12. Dependências Python Adicionais

```txt
# Adicionar ao requirements.txt

# Open Finance / HTTP
httpx==0.27.0              # Cliente HTTP assíncrono (mais robusto que requests)
cryptography==42.0.8       # AES-256-GCM para tokens

# Scheduler (sync automático)
apscheduler==3.10.4

# Providers SDK (opcional — pode usar httpx diretamente)
# belvo-python==1.0.0      # SDK oficial Belvo

# Segurança adicional
flask-limiter==3.8.0       # Rate limiting
```

---

## 13. Estimativa de Esforço

| Fase | Esforço | Risco | Valor Gerado |
|------|---------|-------|--------------|
| Fase 1 — Foundation | 3 dias | 🟢 Baixo | Infra segura |
| Fase 2 — Conexão PT/EU | 4 dias | 🟡 Médio | Novo Banco conectado |
| Fase 3 — Importação | 5 dias | 🟡 Médio | Zero uploads manuais (PT) |
| Fase 4 — Brasil + Scheduler | 4 dias | 🟡 Médio | Automação completa |
| Fase 5 — Produção | 2 dias | 🟢 Baixo | Conformidade GDPR/LGPD |
| **Total** | **~18 dias** | | **MyFinance automatizado** |

---

## 14. Custos Estimados

| Serviço | Plano Dev | Plano Produção |
|---------|-----------|----------------|
| GoCardless | Grátis (50 req/dia) | ~€0,25/conexão/mês |
| Belvo | Grátis (sandbox) | ~$0,10/conexão/mês |
| Revolut Open API | Grátis (AISP certificado) | Grátis |
| APScheduler no Render | Incluído (sem custo extra) | Incluído |
| **Total estimado** | **€0** | **< €5/mês** |

---

## 15. Riscos e Mitigações

| Risco | Probabilidade | Mitigação |
|-------|--------------|-----------|
| Novo Banco PT não suporta GoCardless | Médio | Verificar lista de bancos; alternativa: TrueLayer |
| Token expira durante sync offline | Alto | Refresh automático + notificação de reconexão |
| API do banco muda formato de resposta | Baixo | `raw_data` preservado para re-processar |
| GDPR — armazenar dados bancários | Alto | Criptografia + consentimento explícito + right-to-delete |
| Rate limit do provider | Médio | Cache de 6h + retry com exponential backoff |

---

*Documento gerado em 2026-05-26 | Próximo passo: executar Fase 1 — criar o schema SQL e o módulo base*
