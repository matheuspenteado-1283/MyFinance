import os
import sys
import time
import threading
import psycopg2
import psycopg2.extras
import psycopg2.pool
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Wrappers de compatibilidade (mantêm a API usada em todo o código)
# ---------------------------------------------------------------------------

class PGCursor:
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
    """Imita a API do sqlite3: conn.execute(), conn.cursor(), commit(), close()."""

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


class _PooledConnection(PGConnection):
    """Devolve a conexão ao pool em vez de fechá-la."""

    def __init__(self, conn, pool: psycopg2.pool.ThreadedConnectionPool):
        super().__init__(conn)
        self._pool = pool
        self._returned = False

    def close(self):
        if not self._returned and not self._conn.closed:
            try:
                if self._conn.status == psycopg2.extensions.STATUS_IN_TRANSACTION:
                    self._conn.rollback()
            except Exception:
                pass
            self._pool.putconn(self._conn)
            self._returned = True

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()


# ---------------------------------------------------------------------------
# Connection pool — singleton por processo
# ---------------------------------------------------------------------------

_pool: psycopg2.pool.ThreadedConnectionPool | None = None
_pool_lock = threading.Lock()


def _parse_db_url(db_url: str) -> dict:
    import urllib.parse
    UNSUPPORTED_PARAMS = {"channel_binding", "options"}
    parsed = urllib.parse.urlparse(db_url)
    params = {
        "host":            parsed.hostname,
        "port":            parsed.port or 5432,
        "dbname":          parsed.path.lstrip("/"),
        "user":            parsed.username,
        "password":        urllib.parse.unquote(parsed.password or ""),
        "sslmode":         "require",
        "connect_timeout": 10,
        "keepalives":      1,
        "keepalives_idle": 30,
    }
    for key, value in urllib.parse.parse_qsl(parsed.query):
        if key not in UNSUPPORTED_PARAMS and key not in params:
            params[key] = value
    return params


def _build_pool() -> psycopg2.pool.ThreadedConnectionPool:
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL não está configurada no ambiente")
    params = _parse_db_url(db_url)
    print(f"[db] criando pool: host={params['host']} db={params['dbname']}", file=sys.stderr)
    # Supabase free tier: ~10 conexões diretas (porta 5432).
    # 4 workers × maxconn=2 = 8 conexões máximas — fica abaixo do limite.
    return psycopg2.pool.ThreadedConnectionPool(minconn=1, maxconn=2, **params)


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is not None and not _pool.closed:
        return _pool
    with _pool_lock:
        if _pool is not None and not _pool.closed:
            return _pool
        _pool = _build_pool()
        return _pool


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def get_connection(max_retries: int = 3, retry_delay: float = 1.0) -> PGConnection:
    """Retorna uma conexão do pool. A conexão é devolvida ao pool no close()."""
    last_err: Exception = RuntimeError("Pool indisponível")
    for attempt in range(max_retries):
        try:
            pool = _get_pool()
            raw = pool.getconn()
            if raw.closed:
                pool.putconn(raw)
                raise psycopg2.OperationalError("Conexão do pool está fechada")
            # Garante estado limpo
            if raw.status == psycopg2.extensions.STATUS_IN_TRANSACTION:
                raw.rollback()
            return _PooledConnection(raw, pool)
        except psycopg2.pool.PoolError:
            # Pool esgotado — tentar novamente
            last_err = psycopg2.pool.PoolError("Pool esgotado")
            time.sleep(retry_delay * (2 ** attempt))
        except Exception as e:
            last_err = e
            print(f"[db] tentativa {attempt + 1}/{max_retries} falhou: {type(e).__name__}: {e}", file=sys.stderr)
            # Pool pode estar corrompido; reinicializa
            global _pool
            with _pool_lock:
                try:
                    if _pool is not None:
                        _pool.closeall()
                except Exception:
                    pass
                _pool = None
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (2 ** attempt))

    raise last_err
