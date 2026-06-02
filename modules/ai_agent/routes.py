import traceback
import logging
from datetime import datetime
from flask import request, jsonify, session
from . import bp
from .collector import collect_financial_snapshot
from . import analyst

logger = logging.getLogger(__name__)


def _auth():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    return None


def _period():
    mes = request.args.get('mes', datetime.now().strftime('%Y-%m'))
    return mes, int(mes[:4])


# ── Cache helpers — falham silenciosamente se BD offline ─────────────────────

def _get_cache(user_email, analysis_type, mes):
    try:
        from .db import get_cached_analysis
        return get_cached_analysis(user_email, analysis_type, mes)
    except Exception:
        return None


def _save_cache(user_email, analysis_type, result, mes, ttl_hours):
    try:
        from .db import save_analysis
        save_analysis(user_email, analysis_type, result, period=mes, ttl_hours=ttl_hours)
    except Exception:
        pass  # cache indisponível — continua sem guardar


def _get_history(user_email, limit=10):
    try:
        from .db import get_chat_history
        return get_chat_history(user_email, limit=limit)
    except Exception:
        return []


def _save_msg(user_email, role, content):
    try:
        from .db import save_chat_message
        save_chat_message(user_email, role, content)
    except Exception:
        pass


# ── Endpoint genérico para análises ──────────────────────────────────────────

def _analysis_endpoint(analysis_type: str, analyzer_fn, ttl_hours: int = 6):
    logger.info(f"[_analysis_endpoint] Iniciando para {analysis_type}")
    err = _auth()
    if err:
        logger.warning(f"[_analysis_endpoint] Falha na autenticação")
        return err
    user_email = session['user_email']
    mes, ano = _period()
    force = request.args.get('refresh', '').lower() == 'true'
    logger.info(f"[_analysis_endpoint] user_email={user_email}, mes={mes}, ano={ano}")

    if not force:
        cached = _get_cache(user_email, analysis_type, mes)
        if cached:
            logger.info(f"[_analysis_endpoint] Cache hit para {analysis_type}")
            cached['_cached'] = True
            return jsonify(cached)

    try:
        logger.info(f"[_analysis_endpoint] Coletando snapshot para {user_email}...")
        snapshot = collect_financial_snapshot(user_email, mes, ano)
        logger.info(f"[_analysis_endpoint] Snapshot coletado, chamando {analyzer_fn.__name__}...")
        result = analyzer_fn(snapshot)
        result['_period'] = mes
        result['_generated_at'] = datetime.utcnow().isoformat()
        _save_cache(user_email, analysis_type, result, mes, ttl_hours)
        logger.info(f"[_analysis_endpoint] {analysis_type} concluído com sucesso")
        return jsonify(result)
    except ValueError as e:
        logger.error(f"[_analysis_endpoint] ValueError: {str(e)}")
        if "API_KEY" in str(e):
            return jsonify({'error': str(e)}), 500
        raise
    except Exception as e:
        logger.error(f"[_analysis_endpoint] Exception: {type(e).__name__}: {str(e)}", exc_info=True)
        traceback.print_exc()
        return jsonify({'error': 'Erro ao gerar análise. Verifique ANTHROPIC_API_KEY.'}), 500


# ── Rotas ─────────────────────────────────────────────────────────────────────

@bp.route('/api/ai/alerts', methods=['GET'])
def api_ai_alerts():
    return _analysis_endpoint('alerts', analyst.analyze_alerts, ttl_hours=2)


@bp.route('/api/ai/health', methods=['GET'])
def api_ai_health():
    return _analysis_endpoint('health', analyst.analyze_health, ttl_hours=6)


@bp.route('/api/ai/economy-tips', methods=['GET'])
def api_ai_economy_tips():
    return _analysis_endpoint('economy_tips', analyst.analyze_economy_tips, ttl_hours=6)


@bp.route('/api/ai/investment-tips', methods=['GET'])
def api_ai_investment_tips():
    return _analysis_endpoint('investment_tips', analyst.analyze_investment_tips, ttl_hours=6)


@bp.route('/api/ai/portfolio', methods=['GET'])
def api_ai_portfolio():
    return _analysis_endpoint('portfolio', analyst.analyze_portfolio, ttl_hours=6)


@bp.route('/api/ai/trader-analysis', methods=['GET'])
def api_ai_trader_analysis():
    try:
        logger.info("[api_ai_trader_analysis] Iniciando...")
        result = _analysis_endpoint('trader_analysis', analyst.analyze_trader, ttl_hours=6)
        logger.info(f"[api_ai_trader_analysis] Concluído: {type(result)}")
        return result
    except Exception as e:
        logger.error(f"[api_ai_trader_analysis] ERRO: {type(e).__name__}: {str(e)}", exc_info=True)
        traceback.print_exc()
        raise


@bp.route('/api/ai/budget-multicurrency', methods=['GET'])
def api_ai_budget_multicurrency():
    return _analysis_endpoint('budget_multicurrency', analyst.analyze_budget_multicurrency, ttl_hours=4)


@bp.route('/api/ai/chat', methods=['POST'])
def api_ai_chat():
    err = _auth()
    if err:
        return err
    user_email = session['user_email']
    data = request.get_json() or {}
    message = (data.get('message') or '').strip()
    if not message:
        return jsonify({'error': 'Mensagem não pode ser vazia'}), 400
    mes = data.get('mes', datetime.now().strftime('%Y-%m'))
    ano = int(mes[:4])
    try:
        history = _get_history(user_email, limit=10)
        snapshot = collect_financial_snapshot(user_email, mes, ano)
        _save_msg(user_email, 'user', message)
        result = analyst.chat_with_analyst(snapshot, history, message)
        _save_msg(user_email, 'assistant', result['reply'])
        return jsonify(result)
    except ValueError as e:
        if "API_KEY" in str(e):
            return jsonify({'error': str(e)}), 500
        raise
    except Exception:
        traceback.print_exc()
        return jsonify({'error': 'Erro ao processar mensagem. Verifique ANTHROPIC_API_KEY.'}), 500


@bp.route('/api/ai/chat/history', methods=['GET'])
def api_ai_chat_history():
    err = _auth()
    if err:
        return err
    history = _get_history(session['user_email'], limit=30)
    return jsonify({'history': history})


@bp.route('/api/ai/chat/clear', methods=['DELETE'])
def api_ai_chat_clear():
    err = _auth()
    if err:
        return err
    try:
        from .db import clear_chat_history
        clear_chat_history(session['user_email'])
    except Exception:
        pass
    return jsonify({'status': 'ok'})


@bp.route('/api/ai/cache', methods=['DELETE'])
def api_ai_clear_cache():
    err = _auth()
    if err:
        return err
    try:
        from .db import clear_user_cache
        clear_user_cache(session['user_email'])
    except Exception:
        pass
    return jsonify({'status': 'ok', 'message': 'Cache limpo'})
