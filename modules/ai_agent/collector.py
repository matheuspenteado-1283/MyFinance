from collections import defaultdict
from datetime import datetime


def collect_financial_snapshot(user_email: str, mes: str = None, ano: int = None) -> dict:
    """Agrega dados financeiros de todos os módulos para análise de IA."""
    if not mes:
        mes = datetime.now().strftime('%Y-%m')
    if not ano:
        ano = int(mes[:4])

    snapshot = {'period': {'mes': mes, 'ano': ano}}

    def _safe(key, fn, *args):
        try:
            snapshot[key] = fn(*args)
        except Exception as e:
            snapshot[key] = {'_error': str(e)}

    from modules.dashboard.db import (
        get_dashboard_overview, get_dashboard_budget,
        get_dashboard_cashflow, get_dashboard_net_worth,
        get_dashboard_investments,
    )
    _safe('overview', get_dashboard_overview, user_email, mes, ano)
    _safe('budget', get_dashboard_budget, user_email, mes, ano)
    _safe('cashflow', get_dashboard_cashflow, user_email, ano)
    _safe('net_worth', get_dashboard_net_worth, user_email, mes, ano)
    _safe('investments_summary', get_dashboard_investments, user_email, mes, ano)

    from modules.investimentos.db import get_all_lcto_investimentos
    _safe('investments', lambda: get_all_lcto_investimentos(user_email)[:30])

    from modules.trader.db import get_all_trader_positions
    def _trader():
        positions = get_all_trader_positions(user_email)
        return {
            'stats': _trader_stats(positions),
            'by_symbol': _trader_by_symbol(positions),
            'recent': positions[:20],
        }
    _safe('trader', _trader)

    from modules.despesas_mensais.db import get_despesas_mensais
    _safe('expenses', lambda: get_despesas_mensais(user_email, mes)[:50])

    from modules.receitas_mensais.db import get_receitas_mensais
    _safe('revenues', lambda: get_receitas_mensais(user_email, mes)[:30])

    from modules.emprestimos.db import get_saldo_emprestimos
    _safe('debt', get_saldo_emprestimos, user_email)

    return snapshot


def _trader_stats(positions: list) -> dict:
    if not positions:
        return {'total_trades': 0}
    winning = [p for p in positions if (p.get('gross_pl') or 0) > 0]
    losing = [p for p in positions if (p.get('gross_pl') or 0) < 0]
    total_pnl = sum((p.get('gross_pl') or 0) for p in positions)
    gross_profit = sum((p.get('gross_pl') or 0) for p in winning)
    gross_loss = abs(sum((p.get('gross_pl') or 0) for p in losing))
    n = len(positions)
    return {
        'total_trades': n,
        'winning_trades': len(winning),
        'losing_trades': len(losing),
        'win_rate_pct': round(len(winning) / n * 100, 1) if n else 0,
        'total_pnl': round(total_pnl, 2),
        'avg_pnl_per_trade': round(total_pnl / n, 2) if n else 0,
        'best_trade_pnl': round(max((p.get('gross_pl') or 0) for p in positions), 2),
        'worst_trade_pnl': round(min((p.get('gross_pl') or 0) for p in positions), 2),
        'gross_profit': round(gross_profit, 2),
        'gross_loss': round(gross_loss, 2),
        'profit_factor': round(gross_profit / gross_loss, 2) if gross_loss > 0 else None,
    }


def _trader_by_symbol(positions: list) -> list:
    by_sym = defaultdict(lambda: {'trades': 0, 'pnl': 0.0, 'wins': 0})
    for p in positions:
        sym = p.get('symbol') or 'UNKNOWN'
        pnl = p.get('gross_pl') or 0
        by_sym[sym]['trades'] += 1
        by_sym[sym]['pnl'] += pnl
        if pnl > 0:
            by_sym[sym]['wins'] += 1
    result = []
    for sym, d in by_sym.items():
        n = d['trades']
        result.append({
            'symbol': sym,
            'trades': n,
            'total_pnl': round(d['pnl'], 2),
            'win_rate_pct': round(d['wins'] / n * 100, 1) if n else 0,
            'avg_pnl': round(d['pnl'] / n, 2) if n else 0,
        })
    return sorted(result, key=lambda x: x['total_pnl'], reverse=True)
