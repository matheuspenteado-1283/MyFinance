import requests
import datetime

# Cache em memória para não martelar a API à toa durante o mesmo processamento.
# Formato: { "YYY-MM-DD_CURRENCY": rate_float }
_rate_cache = {}

def get_exchange_rate(date_str: str, from_currency: str, to_currency: str = "EUR") -> float:
    """
    Busca a cotação histórica na data especificada.
    date_str deve ser no formato YYYY-MM-DD.
    """
    from_currency = from_currency.upper().strip()
    to_currency = to_currency.upper().strip()
    
    if from_currency == to_currency:
        return 1.0
        
    cache_key = f"{date_str}_{from_currency}_{to_currency}"
    if cache_key in _rate_cache:
        return _rate_cache[cache_key]
        
    # Validar se a data é futura, a API pode quebrar, entao usamos a data atual se for
    try:
        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        if dt.date() > datetime.date.today():
            date_str = "latest"
    except ValueError:
        return 1.0 # Em caso de erro de data, evitamos travar o processo

    url = f"https://api.frankfurter.app/{date_str}?from={from_currency}&to={to_currency}"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        if "rates" in data and to_currency in data["rates"]:
            rate = float(data["rates"][to_currency])
            _rate_cache[cache_key] = rate
            return rate
    except Exception as e:
        print(f"Erro ao buscar cotação de {from_currency} na data {date_str}: {e}")
        
    return 1.0 # Fallback se falhar
