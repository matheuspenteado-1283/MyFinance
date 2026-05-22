import traceback
from datetime import datetime
from flask import request, jsonify, session
from . import bp
from .db import (
    get_cached_analysis, save_analysis, clear_user_cache,
    get_chat_history, save_chat_message, clear_chat_history,
)
from .collector import collect_financial_snapshot
from . import analyst


def _auth():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    return None


def _period():
    mes = request.args.get('mes', datetime.now().strftime('%Y-%m'))
    return mes, int(mes[:4])


def _analysis_endpoint(analysis_type: str, analyzer_fn, ttl_hours: int = 6):
    err = _auth()
    if err:
        return err
    user_email = session['user_email']
    mes, ano = _period()
    force = request.args.get('refresh', '').lower() == 'true'
    if not force:
        cached = get_cached_analysis(user_email, analysis_type, mes)
        if cached:
            cached['_cached'] = True
            return jsonify(cached)
    try:
        snapshot = collect_financial_snapshot(user_email, mes, ano)
        result = analyzer_fn(snapshot)
        result['_period'] = mes
        result['_generated_at'] = datetime.utcnow().isoformat()
        save_analysis(user_email, analysis_type, result, period=mes, ttl_hours=ttl_hours)
        return jsonify(result)
    except Exception:
        traceback.print_exc()
        return jsonify({'error': 'Erro ao gerar análise. Verifique ANTHROPIC_API_KEY.'}), 500


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
    return _analysis_endpoint('trader_analysis', analyst.analyze_trader, ttl_hours=6)


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
        history = get_chat_history(user_email, limit=10)
        snapshot = collect_financial_snapshot(user_email, mes, ano)
        save_chat_message(user_email, 'user', message)
        result = analyst.chat_with_analyst(snapshot, history, message)
        save_chat_message(user_email, 'assistant', result['reply'])
        return jsonify(result)
    except Exception:
        traceback.print_exc()
        return jsonify({'error': 'Erro ao processar mensagem. Verifique ANTHROPIC_API_KEY.'}), 500


@bp.route('/api/ai/chat/history', methods=['GET'])
def api_ai_chat_history():
    err = _auth()
    if err:
        return err
    history = get_chat_history(session['user_email'], limit=30)
    return jsonify({'history': history})


@bp.route('/api/ai/chat/clear', methods=['DELETE'])
def api_ai_chat_clear():
    err = _auth()
    if err:
        return err
    clear_chat_history(session['user_email'])
    return jsonify({'status': 'ok'})


@bp.route('/api/ai/cache', methods=['DELETE'])
def api_ai_clear_cache():
    err = _auth()
    if err:
        return err
    clear_user_cache(session['user_email'])
    return jsonify({'status': 'ok', 'message': 'Cache limpo com sucesso'})
