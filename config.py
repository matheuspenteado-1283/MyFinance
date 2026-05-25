import os
import datetime
from dotenv import load_dotenv

load_dotenv(override=True)

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'csv', 'xls', 'xlsx', 'xml'}


def configure_app(app):
    app.secret_key = os.getenv('SECRET_KEY', 'chave-super-secreta-extratos')
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    # Serializa datetime/date do PostgreSQL para ISO string no JSON
    from flask.json.provider import DefaultJSONProvider

    class _JSONProvider(DefaultJSONProvider):
        def default(self, obj):
            if isinstance(obj, (datetime.datetime, datetime.date)):
                return obj.isoformat()
            return super().default(obj)

    app.json_provider_class = _JSONProvider
    app.json = _JSONProvider(app)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
