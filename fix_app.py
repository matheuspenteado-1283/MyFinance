import re

with open('app.py', 'r') as f:
    content = f.read()

# Fix contas
contas_old = """        clear_contas()
        for _, row in df.iterrows():
            add_conta(
                str(row.get('descricao', row.get('Descrição', ''))),
                str(row.get('agencia', row.get('Agência', ''))),
                str(row.get('conta', row.get('Conta', ''))),
                str(row.get('dados_acesso', row.get('Dados Acesso', ''))),
                str(row.get('senha', row.get('Senha', ''))),
                str(row.get('comentarios', row.get('Comentários', '')))
            )
            count += 1"""
contas_new = """        clear_contas()
        df.columns = df.columns.str.strip().str.lower()
        col_desc = next((c for c in df.columns if 'descri' in c), 'descricao')
        col_age = next((c for c in df.columns if 'ag' in c), 'agencia')
        col_conta = next((c for c in df.columns if 'conta' in c and 'dados' not in c), 'conta')
        col_acesso = next((c for c in df.columns if 'acesso' in c), 'dados_acesso')
        col_senha = next((c for c in df.columns if 'senha' in c), 'senha')
        col_obs = next((c for c in df.columns if 'coment' in c), 'comentarios')
        for _, row in df.iterrows():
            def g(c):
                v = row.get(c)
                return '' if pd.isna(v) else str(v).strip()
            add_conta(g(col_desc), g(col_age), g(col_conta), g(col_acesso), g(col_senha), g(col_obs))
            count += 1"""
content = content.replace(contas_old, contas_new)

# Fix receitas
receitas_old = """        clear_receitas()
        for _, row in df.iterrows():
            descricao = row.get('descricao') if pd.notna(row.get('descricao')) else row.get('Descrição')
            if pd.notna(descricao):
                add_receita(str(descricao))
                count += 1"""
receitas_new = """        clear_receitas()
        df.columns = df.columns.str.strip().str.lower()
        col_desc = next((c for c in df.columns if 'descri' in c), 'descricao')
        for _, row in df.iterrows():
            val = row.get(col_desc)
            if pd.notna(val) and str(val).strip():
                add_receita(str(val).strip())
                count += 1"""
content = content.replace(receitas_old, receitas_new)

# Fix investimentos
investimentos_old = """        clear_investimentos()
        for _, row in df.iterrows():
            descricao = row.get('descricao') if pd.notna(row.get('descricao')) else row.get('Descrição')
            if pd.notna(descricao):
                add_investimento(str(descricao))
                count += 1"""
investimentos_new = """        clear_investimentos()
        df.columns = df.columns.str.strip().str.lower()
        col_desc = next((c for c in df.columns if 'descri' in c), 'descricao')
        for _, row in df.iterrows():
            val = row.get(col_desc)
            if pd.notna(val) and str(val).strip():
                add_investimento(str(val).strip())
                count += 1"""
content = content.replace(investimentos_old, investimentos_new)

with open('app.py', 'w') as f:
    f.write(content)

