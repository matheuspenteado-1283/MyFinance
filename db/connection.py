import os
import time
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


class PGCursor:
    """Wrapper em torno de RealDictCursor para manter compatibilidade com o código SQLite."""

    def __init__(self, cursor):
        self._cur = cursor

    def execute(self, sql, params=None):
        self._cur.execute(sql, params)
        return self

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    def __iter__(self):
        return iter(self._cur)

    @property
    def rowcount(self):
        return self._cur.rowcount


class PGConnection:
    """Wrapper em torno de psycopg2 connection que imita a API do sqlite3.

    Suporta:
      - conn.execute(sql, params)  → retorna PGCursor (padrão usado em despesas_mensais etc.)
      - conn.cursor()              → retorna PGCursor
      - conn.commit() / conn.close()
    """

    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        return PGCursor(self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor))

    def execute(self, sql, params=None):
        cur = self.cursor()
        cur.execute(sql, params)
        return cur

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        if not self._conn.closed:
            self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()


def _parse_db_url(db_url: str) -> dict:
    """Extrai parâmetros de conexão do DATABASE_URL, ignorando parâmetros não suportados pelo psycopg2."""
    import urllib.parse

    # psycopg2 não suporta estes parâmetros de query string
    UNSUPPORTED_PARAMS = {"channel_binding", "options"}

    parsed = urllib.parse.urlparse(db_url)
    params = {
        "host":     parsed.hostname,
        "port":     parsed.port or 5432,
        "dbname":   parsed.path.lstrip("/"),
        "user":     parsed.username,
        "password": urllib.parse.unquote(parsed.password or ""),
        "sslmode":  "require",
        "connect_timeout": 10,
    }

    # Mantém apenas parâmetros suportados da query string
    for key, value in urllib.parse.parse_qsl(parsed.query):
        if key not in UNSUPPORTED_PARAMS and key not in params:
            params[key] = value

    return params


def get_connection(max_retries: int = 4, retry_delay: float = 2.0) -> PGConnection:
    import sys
    db_url = os.getenv("DATABASE_URL")

    if not db_url:
        raise RuntimeError("DATABASE_URL não está configurada no ambiente")

    params = _parse_db_url(db_url)
    print(f"[db] conectando: host={params['host']} port={params['port']} db={params['dbname']}", file=sys.stderr)

    last_err: Exception = RuntimeError("Falha ao conectar")
    for attempt in range(max_retries):
        try:
            conn = psycopg2.connect(**params)
            print(f"[db] conectado na tentativa {attempt + 1}", file=sys.stderr)
            return PGConnection(conn)
        except Exception as e:
            last_err = e
            print(f"[db] tentativa {attempt + 1}/{max_retries} falhou: {type(e).__name__}: {e}", file=sys.stderr)
            if attempt < max_retries - 1:
                time.sleep(retry_delay)

    raise last_err
