import pandas as pd

filepath = "MyFinance/PT_EXTRATO_REVOLUT_CSV.csv"
df = pd.read_csv(filepath)
df.columns = df.columns.str.strip().str.lower()
print("Colunas:", df.columns.tolist())

is_revolut = any(c in df.columns for c in ['descrição', 'descricao', 'description']) or any(c in df.columns for c in ['tipo', 'type'])
print("is_revolut:", is_revolut)

for idx, row in df.head().iterrows():
    data_raw = str(row.get('data de início', '') or row.get('data de conclusão', '') or row.get('data de conclusao', '') or row.get('started date', '') or row.get('completed date', ''))
    data = data_raw[:10] if data_raw and data_raw.lower() not in ['nan', 'none', 'nat'] else ''
    desc = str(row.get('descrição') or row.get('descricao') or row.get('description') or row.get('tipo') or row.get('type') or '').strip()
    val_orig = abs(float(row.get('montante') or row.get('amount') or 0))
    print(f"Row {idx} -> Data: {data}, Desc: {desc}, Val: {val_orig}")

