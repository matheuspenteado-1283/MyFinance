import requests
import datetime

# Cache em memória: { "YYYY-MM-DD_FROM_TO": rate }  — válido enquanto o processo viver
_rate_cache: dict[str, float] = {}


def _db_get_rate(date_str: str, from_currency: str, to_currency: str) -> float | None:
    """Consulta o cache persistente no PostgreSQL. Retorna None se não encontrado."""
    try:
        from db.connection import get_connection
        conn = get_connection()
        row = conn.execute(
            'SELECT rate FROM exchange_rate_cache WHERE date_str=%s AND from_currency=%s AND to_currency=%s',
            (date_str, from_currency, to_currency),
        ).fetchone()
        conn.close()
        return float(row['rate']) if row else None
    except Exception:
        return None


def _db_save_rate(date_str: str, from_currency: str, to_currency: str, rate: float) -> None:
    """Persiste a cotação no PostgreSQL (upsert)."""
    try:
        from db.connection import get_connection
        conn = get_connection()
        conn.execute(
            '''
            INSERT INTO exchange_rate_cache (date_str, from_currency, to_currency, rate)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (date_str, from_currency, to_currency)
            DO UPDATE SET rate = EXCLUDED.rate, fetched_at = NOW()
            ''',
            (date_str, from_currency, to_currency, rate),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def _ensure_cache_table() -> None:
    """Cria a tabela de cache se ainda não existir (executado uma vez na inicialização)."""
    try:
        from db.connection import get_connection
        conn = get_connection()
        conn.execute('''
            CREATE TABLE IF NOT EXISTS exchange_rate_cache (
                date_str      TEXT NOT NULL,
                from_currency TEXT NOT NULL,
                to_currency   TEXT NOT NULL,
                rate          REAL NOT NULL,
                fetched_at    TIMESTAMPTZ DEFAULT NOW(),
                PRIMARY KEY (date_str, from_currency, to_currency)
            )
        ''')
        conn.commit()
        conn.close()
    except Exception:
        pass


_cache_table_ready = False


def get_exchange_rate(date_str: str, from_currency: str, to_currency: str = "EUR") -> float:
    """
    Retorna a cotação histórica para a data e par de moedas.
    Ordem de lookup: memória → PostgreSQL → API externa.
    """
    global _cache_table_ready

    from_currency = from_currency.upper().strip()
    to_currency = to_currency.upper().strip()

    if from_currency == to_currency:
        return 1.0

    cache_key = f"{date_str}_{from_currency}_{to_currency}"

    # 1. Cache em memória (mais rápido)
    if cache_key in _rate_cache:
        return _rate_cache[cache_key]

    # 2. Cache persistente no PostgreSQL
    if not _cache_table_ready:
        _ensure_cache_table()
        _cache_table_ready = True

    db_rate = _db_get_rate(date_str, from_currency, to_currency)
    if db_rate is not None:
        _rate_cache[cache_key] = db_rate
        return db_rate

    # 3. API externa como último recurso
    try:
        effective_date = date_str
        if date_str != "latest":
            dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
            if dt.date() > datetime.date.today():
                effective_date = "latest"
    except ValueError:
        return 1.0

    url = f"https://api.frankfurter.app/{effective_date}?from={from_currency}&to={to_currency}"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        if "rates" in data and to_currency in data["rates"]:
            rate = float(data["rates"][to_currency])
            _rate_cache[cache_key] = rate
            _db_save_rate(date_str, from_currency, to_currency, rate)
            return rate
    except Exception as e:
        print(f"[exchange] erro ao buscar {from_currency}→{to_currency} em {date_str}: {e}")

    return 1.0


def prefetch_rates(pairs: list[tuple[str, str]], to_currency: str = "EUR") -> None:
    """
    Pré-aquece o cache para uma lista de (date_str, from_currency).
    Útil antes de processar extratos com muitas transações.
    """
    unique = set(pairs)
    for date_str, from_currency in unique:
        get_exchange_rate(date_str, from_currency, to_currency)
