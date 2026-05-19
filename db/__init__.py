import sys
from .connection import get_connection

def init_all():
    # Tabelas já criadas via supabase_schema.sql — init é idempotente.
    # Envolto em try/except para não derrubar o processo se a DB ainda
    # não estiver acessível no momento do cold start.
    try:
        from modules.auth.db import init_tables as init_auth
        from modules.extratos.db import init_tables as init_extratos
        from modules.cadastros.db.despesas import init_tables as init_cad_despesas
        from modules.cadastros.db.contas import init_tables as init_cad_contas
        from modules.cadastros.db.receitas import init_tables as init_cad_receitas
        from modules.cadastros.db.investimentos import init_tables as init_cad_investimentos
        from modules.cadastros.db.usuarios import init_tables as init_cad_usuarios
        from modules.cadastros.db.tipo_imposto import init_tables as init_cad_tipo_imposto
        from modules.despesas_mensais.db import init_tables as init_despesas_mensais
        from modules.receitas_mensais.db import init_tables as init_receitas_mensais
        from modules.impostos.db import init_tables as init_impostos
        from modules.emprestimos.db import init_tables as init_emprestimos
        from modules.investimentos.db import init_tables as init_investimentos
        from modules.trader.db import init_tables as init_trader
        from modules.relatorios.db import init_tables as init_relatorios
        from modules.budget.db import init_tables as init_budget

        init_auth()
        init_extratos()
        init_cad_despesas()
        init_cad_contas()
        init_cad_receitas()
        init_cad_investimentos()
        init_cad_usuarios()
        init_cad_tipo_imposto()
        init_despesas_mensais()
        init_receitas_mensais()
        init_impostos()
        init_emprestimos()
        init_investimentos()
        init_trader()
        init_relatorios()
        init_budget()
    except Exception as e:
        print(f"[init_all] aviso: {e}", file=sys.stderr)
