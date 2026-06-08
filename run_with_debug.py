import logging
import sys
from app import app

# Configurar logging MÁXIMO
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('server.log')
    ]
)

# Aumentar logging de werkzeug
logging.getLogger('werkzeug').setLevel(logging.DEBUG)
logging.getLogger('flask').setLevel(logging.DEBUG)

print("[MAIN] Iniciando servidor com DEBUG logging completo...")
app.run(debug=False, port=5001)
