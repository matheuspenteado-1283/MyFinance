from flask import request, jsonify, session, render_template, current_app
from . import bp
from .db import register_user, verify_user, limpar_dados_usuario
from modules.cadastros.db.despesas import clear_despesas
from modules.cadastros.db.contas import clear_contas
from modules.cadastros.db.receitas import clear_receitas
from modules.cadastros.db.investimentos import clear_investimentos
from modules.cadastros.db.usuarios import clear_usuarios
from modules.cadastros.db.tipo_imposto import clear_tipo_imposto


@bp.route('/')
def index():
    return render_template('index.html')


@bp.route('/api/me', methods=['GET'])
def api_me():
    if 'user_email' in session:
        return jsonify({'logged_in': True, 'email': session['user_email']})
    return jsonify({'logged_in': False}), 401


@bp.route('/register', methods=['POST'])
def register():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    if not email or not password:
        return jsonify({'error': 'E-mail e senha são obrigatórios'}), 400
    if register_user(email, password):
        session['user_email'] = email
        return jsonify({'status': 'ok'})
    return jsonify({'error': 'E-mail já cadastrado'}), 400


@bp.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    if verify_user(email, password):
        session['user_email'] = email
        return jsonify({'status': 'ok'})
    return jsonify({'error': 'Credenciais inválidas'}), 401


@bp.route('/logout', methods=['POST'])
def logout():
    session.pop('user_email', None)
    return jsonify({'status': 'ok'})


@bp.route('/api/limpar_dados', methods=['POST'])
def api_limpar_dados():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    limpar_dados_usuario(session['user_email'])
    return jsonify({'status': 'ok'})


@bp.route('/api/limpar_configuracoes', methods=['POST'])
def api_limpar_configuracoes():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    data = request.json or {}
    email = session['user_email']
    if data.get('despesas'):
        clear_despesas(email)
    if data.get('contas'):
        clear_contas(email)
    if data.get('receitas'):
        clear_receitas(email)
    if data.get('investimentos'):
        clear_investimentos(email)
    if data.get('usuarios'):
        clear_usuarios(email)
    if data.get('tipo_imposto'):
        clear_tipo_imposto(email)
    return jsonify({'status': 'ok'})
