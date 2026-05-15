import os
import threading
import time
import requests
from flask import Flask

from config import configure_app
from db import init_all

from modules.auth import bp as auth_bp
from modules.extratos import bp as extratos_bp
from modules.cadastros import bp as cadastros_bp
from modules.despesas_mensais import bp as despesas_mensais_bp
from modules.receitas_mensais import bp as receitas_mensais_bp
from modules.impostos import bp as impostos_bp
from modules.emprestimos import bp as emprestimos_bp
from modules.investimentos import bp as investimentos_bp
from modules.trader import bp as trader_bp
from modules.dashboard import bp as dashboard_bp
from modules.relatorios import bp as relatorios_bp


def _start_keep_alive():
    """Pings own /health every 10 min to prevent Render free-tier spin-down."""
    url = os.getenv("RENDER_EXTERNAL_URL")
    if not url:
        return

    def ping():
        while True:
            time.sleep(600)
            try:
                requests.get(f"{url}/health", timeout=10)
            except Exception:
                pass

    t = threading.Thread(target=ping, daemon=True)
    t.start()


def create_app():
    app = Flask(__name__)
    configure_app(app)
    init_all()

    # Endpoint de diagnóstico — remover após validar deploy
    from flask import jsonify
    import traceback

    @app.route('/health')
    def health():
        return jsonify({"status": "ok"}), 200

    @app.route('/debug/db')
    def debug_db():
        try:
            from db.connection import get_connection
            import os
            conn = get_connection()
            cur = conn.cursor()
            cur.execute('SELECT COUNT(*) as n FROM users')
            row = cur.fetchone()
            conn.close()
            return jsonify({
                "status": "ok",
                "users": dict(row)['n'],
                "host": os.getenv("DB_HOST", "not set"),
            })
        except Exception as e:
            return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500

    app.register_blueprint(auth_bp)
    app.register_blueprint(extratos_bp)
    app.register_blueprint(cadastros_bp)
    app.register_blueprint(despesas_mensais_bp)
    app.register_blueprint(receitas_mensais_bp)
    app.register_blueprint(impostos_bp)
    app.register_blueprint(emprestimos_bp)
    app.register_blueprint(investimentos_bp)
    app.register_blueprint(trader_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(relatorios_bp)

    return app


app = create_app()
_start_keep_alive()

if __name__ == '__main__':
    app.run(debug=True, port=5001)
