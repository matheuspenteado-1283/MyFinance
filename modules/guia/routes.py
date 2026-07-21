"""
Serve o Guia do Usuario (Markdown) para a aba Referencia do Manual de Uso.

O conteudo vive em Docs/GUIA_DO_USUARIO_MYFINANCE.md — fonte unica.
Editar aquele arquivo atualiza automaticamente a aplicacao, sem tocar no HTML.
"""
import os
import logging
from flask import jsonify, redirect, render_template, session, url_for

from . import bp

logger = logging.getLogger(__name__)

# Docs/ fica na raiz do projeto (dois niveis acima de modules/guia/)
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GUIA_PATH = os.path.join(_ROOT, 'Docs', 'GUIA_DO_USUARIO_MYFINANCE.md')

# Cache em memoria invalidado por mtime — evita ler o disco a cada request
_cache = {'mtime': None, 'content': None}


def _load_guia():
    """Le o guia do disco, reaproveitando o cache se o arquivo nao mudou."""
    try:
        mtime = os.path.getmtime(GUIA_PATH)
    except OSError:
        return None, None

    if _cache['mtime'] == mtime and _cache['content'] is not None:
        return _cache['content'], mtime

    with open(GUIA_PATH, 'r', encoding='utf-8') as fh:
        content = fh.read()

    _cache['mtime'] = mtime
    _cache['content'] = content
    return content, mtime


@bp.route('/api/guia', methods=['GET'])
def api_guia():
    if 'user_email' not in session:
        return jsonify({'error': 'Nao logado'}), 401

    content, mtime = _load_guia()
    if content is None:
        logger.warning('[guia] Arquivo nao encontrado: %s', GUIA_PATH)
        return jsonify({
            'error': 'Guia nao encontrado no servidor.',
            'path': os.path.relpath(GUIA_PATH, _ROOT),
        }), 404

    return jsonify({'content': content, 'updated_at': mtime})


@bp.route('/guia', methods=['GET'])
def pagina_guia():
    """Pagina web standalone do guia — fora do SPA, com link direto e impressao."""
    if 'user_email' not in session:
        # Nao logado: manda para o login guardando o destino
        return redirect(url_for('auth.index', next='/guia'))
    return render_template('guia.html')
