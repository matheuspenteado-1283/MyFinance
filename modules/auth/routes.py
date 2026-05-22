from flask import request, jsonify, session, render_template, current_app, url_for
from . import bp
from .db import register_user, verify_user, limpar_dados_usuario, create_reset_token, verify_reset_token, consume_reset_token, change_user_email
from .email_utils import send_reset_email
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


@bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    data = request.json or {}
    email = (data.get('email') or '').strip().lower()
    if not email:
        return jsonify({'error': 'E-mail obrigatório'}), 400
    token = create_reset_token(email)
    if token:
        reset_url = url_for('auth.reset_password_page', token=token, _external=True)
        send_reset_email(email, reset_url)
    # Always return success to avoid email enumeration
    return jsonify({'status': 'ok'})


@bp.route('/reset-password', methods=['GET'])
def reset_password_page():
    token = request.args.get('token', '')
    email = verify_reset_token(token) if token else None
    return render_template('reset_password.html', token=token, valid=bool(email))


@bp.route('/reset-password', methods=['POST'])
def reset_password():
    data = request.json or {}
    token = data.get('token', '')
    new_password = data.get('password', '')
    if not token or not new_password:
        return jsonify({'error': 'Dados incompletos'}), 400
    if len(new_password) < 6:
        return jsonify({'error': 'A senha deve ter pelo menos 6 caracteres'}), 400
    if consume_reset_token(token, new_password):
        return jsonify({'status': 'ok'})
    return jsonify({'error': 'Link inválido ou expirado'}), 400


@bp.route('/logout', methods=['POST'])
def logout():
    session.pop('user_email', None)
    return jsonify({'status': 'ok'})


@bp.route('/api/fix_email_migration', methods=['POST'])
def api_fix_email_migration():
    """Rota temporária — remover após usar uma vez."""
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    data = request.json or {}
    old_email = data.get('old_email', '').strip().lower()
    new_email = session['user_email'].lower()
    if not old_email:
        return jsonify({'error': 'old_email obrigatório'}), 400
    from db.connection import get_connection
    TABLES = [
        'cad_investimentos', 'cad_despesas', 'cad_contas',
        'cad_receitas', 'cad_usuarios', 'tb_tipo_imposto',
    ]
    conn = get_connection()
    c = conn.cursor()
    updated = {}
    try:
        for table in TABLES:
            c.execute(f'UPDATE {table} SET user_email = %s WHERE LOWER(user_email) = %s', (new_email, old_email))
            updated[table] = c.rowcount
        conn.commit()
        return jsonify({'status': 'ok', 'updated': updated})
    except Exception as exc:
        conn.rollback()
        return jsonify({'error': str(exc)}), 500
    finally:
        conn.close()


@bp.route('/api/change_email', methods=['POST'])
def api_change_email():
    if 'user_email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    data = request.json or {}
    password = data.get('password', '').strip()
    new_email = data.get('new_email', '').strip().lower()
    if not password or not new_email:
        return jsonify({'error': 'Preencha todos os campos'}), 400
    result = change_user_email(session['user_email'], password, new_email)
    if result.get('ok'):
        session['user_email'] = new_email
        return jsonify({'status': 'ok'})
    return jsonify({'error': result['error']}), 400


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
