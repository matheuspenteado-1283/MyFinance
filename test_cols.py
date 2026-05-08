import sys, os
sys.path.append(os.path.abspath('.'))
from parser_utils import _find_column
import pandas as pd

filepath = "MyFinance/PT_EXTRATO_REVOLUT_CSV.csv"
df = pd.read_csv(filepath)

col_date = _find_column(df, ['data oper', 'data de in', 'open time', 'data', 'date', 'registro', 'time'])
col_desc = _find_column(df, ['descri', 'desc', 'historico', 'histórico', 'lançamento', 'detail', 'comment', 'symbol'])
col_val = _find_column(df, ['montante', 'valor', 'value', 'amount', 'quantia', 'saída', 'saida', 'gross p/l', 'purchase value'])
print(f"date: {col_date}, desc: {col_desc}, val: {col_val}")
