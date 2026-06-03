"""
Camada de análise IA — suporta Anthropic e OpenAI.
Selecção via variável de ambiente AI_PROVIDER=anthropic|openai (padrão: anthropic).
"""
import os
import json
import re
import logging
from datetime import datetime, date
from decimal import Decimal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Modelos ──────────────────────────────────────────────────────────────────
_ANTHROPIC_DEEP  = 'claude-sonnet-4-6'
_ANTHROPIC_FAST  = 'claude-haiku-4-5-20251001'
_OPENAI_DEEP     = 'gpt-4o'
_OPENAI_FAST     = 'gpt-4o-mini'

SYSTEM_PROMPT = """Você é o MyFinance Advisor — um consultor financeiro pessoal inteligente \
integrado na plataforma MyFinance 2.0.

MISSÃO: Transformar dados financeiros complexos em decisões simples e acionáveis \
para usuários que gerem finanças pessoais ou de pequenas empresas.

IDIOMA: Português do Brasil (PT-BR) — obrigatório em TODAS as respostas, sem exceção.

PERSONALIDADE E TOM:
- Linguagem clara e direta — explica termos técnicos com analogias do dia a dia
- Sempre cita números exatos dos dados fornecidos (nunca inventa)
- Reconhece pontos positivos antes de apontar problemas
- Tom empático e encorajador, nunca alarmista

CAPACIDADES:
1. Análise de saúde financeira (score 0-100, dimensões: despesas/poupança/investimentos/dívida/liquidez)
2. Budget vs Realizado — desvios por categoria com contexto e tendência
3. Despesas multi-moeda — converte para moeda base, alerta exposição cambial
4. Dicas de economia — corte de gastos com valor exato e passos concretos
5. Análise de carteira — performance, diversificação, rebalanceamento
6. Análise trader — win rate, profit factor, gestão de risco, padrões psicológicos
7. Sugestões de investimento baseadas no perfil e dados atuais do usuário

REGRAS OBRIGATÓRIAS:
- Basear TODAS as análises apenas nos dados fornecidos no snapshot
- Nunca recomendar ativos específicos de forma assertiva (risco regulatório)
- Nunca dar conselhos fiscais ou jurídicos específicos
- Retornar SEMPRE JSON válido seguindo exatamente o schema solicitado
- Zero texto fora do bloco JSON nas respostas estruturadas
- Em modo chat: texto natural, máximo 200 palavras, 1 ação concreta no final"""


# ── Utilitários ───────────────────────────────────────────────────────────────

def _provider() -> str:
    return os.getenv('AI_PROVIDER', 'anthropic').lower()


def _require_key(name: str) -> str:
    """Lê a chave do ambiente. Se vier vazia (ex.: Claude Desktop injeta
    ANTHROPIC_API_KEY='' nos processos filhos), recarrega o .env com override
    e tenta de novo antes de falhar."""
    key = os.environ.get(name)
    if not key:
        try:
            from dotenv import load_dotenv
            load_dotenv(override=True)
            key = os.environ.get(name)
        except Exception:
            pass
    if not key:
        raise ValueError(f"{name} não está configurada")
    return key


def _serialize(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, bytes):
        return obj.decode('utf-8', errors='replace')
    raise TypeError(f"Tipo não serializável: {type(obj)}")


def _to_json(data) -> str:
    return json.dumps(data, default=_serialize, ensure_ascii=False, indent=2)


def _extract_json(text: str) -> dict:
    match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    raise ValueError(f"JSON não encontrado na resposta: {text[:300]}")


def _call_anthropic(model: str, user_content: str, max_tokens: int) -> dict:
    logger.info(f"[ANTHROPIC] Iniciando chamada com modelo {model}")
    import anthropic
    api_key = _require_key('ANTHROPIC_API_KEY')
    logger.info(f"[ANTHROPIC] API Key encontrada: {api_key[:20]}...")
    logger.info(f"[ANTHROPIC] Tamanho da mensagem: {len(user_content)} chars")
    try:
        client = anthropic.Anthropic(api_key=api_key)
        logger.info("[ANTHROPIC] Cliente criado com sucesso")
        logger.info(f"[ANTHROPIC] Sistema prompt tamanho={len(SYSTEM_PROMPT)}")
        logger.info(f"[ANTHROPIC] Chamando messages.create()...")
        msg = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{'role': 'user', 'content': user_content}],
        )
        logger.info("[ANTHROPIC] Mensagem recebida com sucesso")
        logger.info(f"[ANTHROPIC] Response texto primeiras 100 chars: {msg.content[0].text[:100]}...")
        result = _extract_json(msg.content[0].text)
        logger.info(f"[ANTHROPIC] JSON extraído com sucesso")
        return result
    except Exception as e:
        logger.error(f"[ANTHROPIC] ERRO: {type(e).__name__}: {str(e)}", exc_info=True)
        raise


def _call_openai(model: str, user_content: str, max_tokens: int) -> dict:
    from openai import OpenAI
    api_key = _require_key('OPENAI_API_KEY')
    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user',   'content': user_content},
        ],
        response_format={'type': 'json_object'},
    )
    return json.loads(resp.choices[0].message.content)


def _call(speed: str, user_content: str, max_tokens: int = 2048) -> dict:
    """speed: 'deep' (análises complexas) | 'fast' (alertas)"""
    if _provider() == 'openai':
        model = _OPENAI_DEEP if speed == 'deep' else _OPENAI_FAST
        return _call_openai(model, user_content, max_tokens)
    else:
        model = _ANTHROPIC_DEEP if speed == 'deep' else _ANTHROPIC_FAST
        return _call_anthropic(model, user_content, max_tokens)


def _chat_anthropic(system: str, messages: list, max_tokens: int) -> str:
    import anthropic
    api_key = _require_key('ANTHROPIC_API_KEY')
    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=_ANTHROPIC_DEEP,
        max_tokens=max_tokens,
        system=system,
        messages=messages,
    )
    return resp.content[0].text


def _chat_openai(system: str, messages: list, max_tokens: int) -> str:
    from openai import OpenAI
    api_key = _require_key('OPENAI_API_KEY')
    client = OpenAI(api_key=api_key)
    full_messages = [{'role': 'system', 'content': system}] + messages
    resp = client.chat.completions.create(
        model=_OPENAI_DEEP,
        max_tokens=max_tokens,
        messages=full_messages,
    )
    return resp.choices[0].message.content


# ── Análises ──────────────────────────────────────────────────────────────────

def analyze_alerts(snapshot: dict) -> dict:
    period = snapshot.get('period', {}).get('mes', 'atual')
    prompt = f"""Analise os dados financeiros do período {period} e identifique alertas que requerem atenção.

DADOS:
{_to_json(snapshot)}

Retorne APENAS este JSON:
{{
  "alerts": [
    {{
      "severity": "high|medium|low",
      "category": "budget|investimentos|trader|despesas|dividas|cashflow",
      "title": "Título (máx 60 chars)",
      "message": "Explicação com números específicos dos dados",
      "action": "Ação concreta a tomar"
    }}
  ],
  "summary": "Frase sobre o status financeiro geral"
}}

Regras: apenas alertas reais baseados nos dados; máx 8 alertas; ordenar por severity (high primeiro)."""
    return _call('fast', prompt, max_tokens=1500)


def analyze_health(snapshot: dict) -> dict:
    period = snapshot.get('period', {}).get('mes', 'atual')
    prompt = f"""Analise a saúde financeira completa do usuário para {period}.

DADOS:
{_to_json(snapshot)}

Retorne APENAS este JSON:
{{
  "score": 74,
  "grade": "B",
  "summary": "Resumo executivo em 2-3 frases",
  "dimensions": [
    {{
      "name": "Controlo de Despesas",
      "score": 80,
      "status": "good",
      "comment": "Comentário com dados específicos"
    }}
  ],
  "strengths": ["Ponto forte 1"],
  "improvements": ["Melhoria prioritária 1"]
}}

Dimensões obrigatórias: Controlo de Despesas, Taxa de Poupança, Carteira de Investimentos, Nível de Endividamento, Liquidez.
Status: excellent(>=80)/good(>=60)/fair(>=40)/poor(<40). Grade: A(>=90)/B(>=75)/C(>=60)/D(>=45)/F(<45)."""
    return _call('deep', prompt, max_tokens=2048)


def analyze_economy_tips(snapshot: dict) -> dict:
    period = snapshot.get('period', {}).get('mes', 'atual')
    prompt = f"""Analise os padrões de gasto e identifique oportunidades de economia para {period}.

DADOS:
{_to_json(snapshot)}

Retorne APENAS este JSON:
{{
  "tips": [
    {{
      "category": "Categoria da despesa",
      "potential_saving": 150.0,
      "currency": "EUR",
      "title": "Título da dica",
      "description": "Descrição com valores dos dados reais",
      "difficulty": "easy|medium|hard",
      "impact": "high|medium|low"
    }}
  ],
  "total_potential_saving": 450.0,
  "currency": "EUR",
  "summary": "Resumo das oportunidades de economia"
}}

Máximo 6 dicas. Baseie-se APENAS nos dados reais fornecidos."""
    return _call('deep', prompt, max_tokens=2048)


def analyze_investment_tips(snapshot: dict) -> dict:
    prompt = f"""Analise a carteira de investimentos e forneça recomendações estratégicas.

DADOS:
{_to_json(snapshot)}

Retorne APENAS este JSON:
{{
  "portfolio_summary": {{
    "total_invested": 0.0,
    "current_value": 0.0,
    "total_return_pct": 0.0,
    "diversification_score": 65
  }},
  "tips": [
    {{
      "type": "rebalance|diversify|increase|reduce|switch",
      "title": "Título",
      "description": "Descrição com dados específicos",
      "priority": "high|medium|low"
    }}
  ],
  "suggested_allocation": {{
    "renda_fixa_pct": 40,
    "acoes_pct": 30,
    "fundos_pct": 15,
    "internacional_pct": 10,
    "reserva_emergencia_pct": 5
  }},
  "summary": "Avaliação geral da estratégia de investimentos"
}}"""
    return _call('deep', prompt, max_tokens=2048)


def analyze_portfolio(snapshot: dict) -> dict:
    prompt = f"""Realize uma análise detalhada da carteira de investimentos.

DADOS:
{_to_json(snapshot)}

Retorne APENAS este JSON:
{{
  "performance": {{
    "total_invested": 0.0,
    "current_value": 0.0,
    "total_profit": 0.0,
    "total_return_pct": 0.0,
    "monthly_profit": 0.0
  }},
  "by_type": [
    {{
      "type": "Tipo de investimento",
      "value": 0.0,
      "return_pct": 0.0,
      "allocation_pct": 0.0,
      "count": 1
    }}
  ],
  "top_performers": [
    {{"name": "Nome", "type": "Tipo", "return_pct": 0.0, "profit": 0.0}}
  ],
  "underperformers": [
    {{"name": "Nome", "type": "Tipo", "return_pct": 0.0, "loss": 0.0, "recommendation": "Recomendação"}}
  ],
  "analysis": "Análise narrativa detalhada da carteira",
  "rebalancing_suggestions": [
    {{"action": "comprar|vender|manter", "asset": "Ativo/tipo", "reason": "Justificativa"}}
  ]
}}"""
    return _call('deep', prompt, max_tokens=2500)


def analyze_budget_multicurrency(snapshot: dict) -> dict:
    period = snapshot.get('period', {}).get('mes', 'atual')
    prompt = f"""Analise o budget vs realizado e as despesas em múltiplas moedas para {period}.

DADOS:
{_to_json(snapshot)}

Retorne APENAS este JSON:
{{
  "budget_summary": {{
    "total_budget": 0.0,
    "total_actual": 0.0,
    "variance_pct": 0.0,
    "status": "under|on_track|over",
    "days_remaining": 0,
    "projected_total": 0.0
  }},
  "categories": [
    {{
      "category": "Categoria",
      "budget": 0.0,
      "actual": 0.0,
      "variance_pct": 0.0,
      "status": "under|on_track|over",
      "trend": "improving|stable|worsening",
      "alert": "Alerta específico se necessário ou null"
    }}
  ],
  "multi_currency": {{
    "base_currency": "EUR",
    "foreign_total_base": 0.0,
    "foreign_pct_of_total": 0.0,
    "fx_impact_vs_last_month": 0.0,
    "currencies": [
      {{
        "currency": "USD",
        "amount_foreign": 0.0,
        "amount_base": 0.0,
        "rate": 0.0,
        "main_expenses": ["Netflix $15", "Adobe $55"]
      }}
    ],
    "fx_alert": "Alerta cambial se exposição > 15% ou null"
  }},
  "top_overruns": [
    {{"category": "Cat", "overrun_amount": 0.0, "overrun_pct": 0.0, "suggestion": "Sugestão concreta"}}
  ],
  "summary": "Resumo executivo do budget com números chave"
}}"""
    return _call('deep', prompt, max_tokens=2500)


def analyze_trader(snapshot: dict) -> dict:
    prompt = f"""Analise as operações de trader e forneça avaliação de performance e sugestões de melhoria.

DADOS:
{_to_json(snapshot)}

Retorne APENAS este JSON:
{{
  "statistics": {{
    "total_trades": 0,
    "winning_trades": 0,
    "losing_trades": 0,
    "win_rate_pct": 0.0,
    "total_pnl": 0.0,
    "avg_pnl_per_trade": 0.0,
    "best_trade_pnl": 0.0,
    "worst_trade_pnl": 0.0,
    "profit_factor": 0.0
  }},
  "by_symbol": [
    {{
      "symbol": "EURUSD",
      "trades": 0,
      "win_rate_pct": 0.0,
      "total_pnl": 0.0,
      "avg_pnl": 0.0,
      "recommendation": "continue|reduce|avoid"
    }}
  ],
  "risk_assessment": {{
    "score": 65,
    "level": "conservative|moderate|aggressive",
    "issues": ["Problema identificado"]
  }},
  "suggestions": [
    {{
      "area": "risk_management|strategy|psychology|position_sizing",
      "title": "Título",
      "description": "Descrição com dados específicos",
      "priority": "high|medium|low"
    }}
  ],
  "overall_assessment": "Avaliação geral das operações de trading"
}}"""
    return _call('deep', prompt, max_tokens=2500)


def chat_with_analyst(snapshot: dict, history: list, user_message: str) -> dict:
    period = snapshot.get('period', {}).get('mes', 'atual')
    system = (
        f"{SYSTEM_PROMPT}\n\n"
        f"CONTEXTO FINANCEIRO DO USUÁRIO (período: {period}):\n"
        f"{_to_json(snapshot)}\n\n"
        "Responda de forma conversacional e precisa, baseada nos dados acima. "
        "Neste modo, responda em texto natural (não JSON)."
    )
    messages = [
        {'role': m['role'], 'content': m['content']}
        for m in history[-10:]
        if (m.get('content') or '').strip()
    ]
    if not user_message or not user_message.strip():
        return {'reply': 'Por favor, escreva uma mensagem.', 'suggestions': []}
    messages.append({'role': 'user', 'content': user_message})

    if _provider() == 'openai':
        reply = _chat_openai(system, messages, max_tokens=1024)
    else:
        reply = _chat_anthropic(system, messages, max_tokens=1024)

    all_suggestions = [
        "Como está minha taxa de poupança?",
        "Quais são meus maiores gastos?",
        "Como está a performance da carteira?",
        "Tenho operações de trading com prejuízo?",
        "Quais dicas de investimento você recomenda?",
        "Estou acima do meu budget este mês?",
        "Qual é meu patrimônio líquido atual?",
    ]
    suggestions = [s for s in all_suggestions
                   if s.lower()[:20] not in user_message.lower()][:3]

    return {'reply': reply, 'suggestions': suggestions}
