from flask import request, jsonify, session

from . import bp
from .db import get_moeda_base, set_moeda_base, MOEDAS_SUPORTADAS


@bp.route('/api/settings', methods=['GET'])
def api_get_settings():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    return jsonify({
        'moeda_base': get_moeda_base(session['user_email']),
        'moedas_suportadas': MOEDAS_SUPORTADAS,
    })


@bp.route('/api/settings', methods=['PUT'])
def api_put_settings():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    d = request.json or {}
    moeda = (d.get('moeda_base') or '').upper().strip()
    if len(moeda) != 3 or not moeda.isalpha():
        return jsonify({'error': 'Moeda inválida'}), 400
    set_moeda_base(session['user_email'], moeda)
    return jsonify({'status': 'ok', 'moeda_base': moeda})
