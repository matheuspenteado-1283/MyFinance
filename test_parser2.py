import sys
import os

# Adiciona o diretório atual ao path para poder importar
sys.path.append(os.path.abspath('.'))

from parser_utils import process_file
try:
    res = process_file('MyFinance/PT_EXTRATO_REVOLUT_CSV.csv')
    print(f"process_file result count: {len(res)}")
    for i, r in enumerate(res[:3]):
        print(f"{i}: {r['data']} - {r['descricao']} - {r['valor_original']}")
except Exception as e:
    print("Erro:", e)

