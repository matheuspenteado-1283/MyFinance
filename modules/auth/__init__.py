from functools import wraps

from flask import Blueprint, jsonify, session

bp = Blueprint('auth', __name__)


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if 'user_email' not in session:
            return jsonify({'error': 'Não autenticado'}), 401
        return fn(*args, **kwargs)
    return wrapper


from . import routes  # noqa
