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


def get_connection(max_retries: int = 4, retry_delay: float = 2.0) -> PGConnection:
    """Conecta ao PostgreSQL com retry para aguentar cold start do Neon."""
    import sys
    db_url = os.getenv("DATABASE_URL")

    if not db_url:
        raise RuntimeError("DATABASE_URL não está configurada no ambiente")

    url = db_url
    if "sslmode" not in url:
        sep = "&" if "?" in url else "?"
        url = url + sep + "sslmode=require"

    # Log do host para diagnóstico (sem expor credenciais)
    try:
        import urllib.parse
        parsed = urllib.parse.urlparse(url)
        print(f"[db] tentando conectar: host={parsed.hostname} port={parsed.port} db={parsed.path}", file=sys.stderr)
    except Exception:
        pass

    last_err: Exception = RuntimeError("Falha ao conectar")
    for attempt in range(max_retries):
        try:
            conn = psycopg2.connect(url, connect_timeout=10)
            print(f"[db] conectado na tentativa {attempt + 1}", file=sys.stderr)
            return PGConnection(conn)
        except Exception as e:
            last_err = e
            print(f"[db] tentativa {attempt + 1}/{max_retries} falhou: {type(e).__name__}: {e}", file=sys.stderr)
            if attempt < max_retries - 1:
                time.sleep(retry_delay)

    raise last_err
