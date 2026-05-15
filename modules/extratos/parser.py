import pandas as pd
import dateutil.parser
import uuid
import re
import pdfplumber
from bs4 import BeautifulSoup

from .db import guess_category
from exchange_api import get_exchange_rate


def _find_column(df, possible_names):
    if df.empty or len(df.columns) == 0:
        return None
    cols = df.columns
    for name in possible_names:
        for col in cols:
            val = str(col).lower().strip()
            if name.lower() in val:
                if val == 'data valor' and name.lower() == 'valor':
                    continue
                return col
    return None


def _parse_date(date_string):
    if pd.isna(date_string):
        return '2023-01-01'
    if isinstance(date_string, pd.Timestamp):
        return date_string.strftime('%Y-%m-%d')
    from datetime import date, datetime
    if isinstance(date_string, (date, datetime)):
        return date_string.strftime('%Y-%m-%d')

    date_str = str(date_string).strip()
    try:
        if re.match(r'^\d{4}', date_str):
            dt = dateutil.parser.parse(date_str, dayfirst=False, fuzzy=True)
        else:
            dt = dateutil.parser.parse(date_str, dayfirst=True, fuzzy=True)
        return dt.strftime('%Y-%m-%d')
    except Exception:
        return '2023-01-01'


def _parse_value(val_str):
    if pd.isna(val_str):
        return 0.0
    if isinstance(val_str, (int, float)):
        return float(val_str)

    val_str = str(val_str).strip()
    val_str = re.sub(r'[^\d\,\.\-]', '', val_str)

    if ',' in val_str and '.' in val_str:
        if val_str.rfind(',') > val_str.rfind('.'):
            val_str = val_str.replace('.', '').replace(',', '.')
        else:
            val_str = val_str.replace(',', '')
    elif ',' in val_str:
        val_str = val_str.replace(',', '.')
    elif val_str.count('.') > 1:
        last_dot = val_str.rfind('.')
        val_str = val_str[:last_dot].replace('.', '') + '.' + val_str[last_dot + 1:]

    try:
        return float(val_str)
    except Exception:
        return 0.0


def _df_to_transactions(df, filepath=''):
    transactions = []

    header_idx = -1
    for idx, row in df.head(30).iterrows():
        row_str = ' '.join(str(v).lower() for v in row.values if not pd.isna(v))
        has_time = any(x in row_str for x in ['data', 'date', 'time', 'registro', 'operao'])
        has_money = any(x in row_str for x in ['valor', 'value', 'amount', 'gross', 'dbito', 'débito', 'montante'])
        has_desc = any(x in row_str for x in ['descri', 'desc', 'historico', 'histórico'])

        if (has_time and has_money) or (has_time and has_desc):
            header_idx = idx
            break

    if header_idx != -1:
        new_header = df.iloc[header_idx]
        df = df[header_idx + 1:].copy()
        df.columns = new_header

    col_date = _find_column(df, ['data oper', 'data de in', 'open time', 'data', 'date', 'registro', 'time'])
    col_desc = _find_column(df, ['descri', 'desc', 'historico', 'histórico', 'lançamento', 'detail', 'comment', 'symbol'])

    col_val = _find_column(df, ['montante', 'valor', 'value', 'amount', 'quantia', 'saída', 'saida', 'gross p/l', 'purchase value'])
    col_deb = _find_column(df, ['dbito', 'débito'])
    col_cred = _find_column(df, ['crdito', 'crédito'])

    if not col_date or not col_desc:
        if len(df.columns) >= 3:
            col_date, col_desc = df.columns[0], df.columns[1]
            if not col_val and not col_deb:
                col_val = df.columns[2]
        else:
            return []

    for index, row in df.iterrows():
        raw_desc = row[col_desc]
        if pd.isna(raw_desc):
            continue

        val_float = 0.0
        has_value = False
        is_debit = False

        if col_val and not pd.isna(row[col_val]):
            v = _parse_value(row[col_val])
            if v < 0:
                is_debit = True
            val_float = abs(v)
            has_value = True
        elif col_deb or col_cred:
            v_deb = _parse_value(row[col_deb]) if col_deb and not pd.isna(row[col_deb]) else 0.0
            v_cred = _parse_value(row[col_cred]) if col_cred and not pd.isna(row[col_cred]) else 0.0
            if v_deb != 0.0:
                val_float = abs(v_deb)
                is_debit = True
                has_value = True
            elif v_cred != 0.0:
                val_float = abs(v_cred)
                is_debit = False
                has_value = True

        if not has_value:
            continue
        if val_float == 0.0 and str(raw_desc).strip() == '':
            continue

        date_str = _parse_date(row[col_date])
        descricao = str(raw_desc).strip()
        if descricao.lower() in ['nan', 'none', '']:
            continue

        moeda = 'BRL'

        if col_deb or col_cred or _find_column(df, ['data operao', 'data operação', 'saldo controlo']):
            moeda = 'EUR'

        col_currency = _find_column(df, ['moeda', 'currency'])
        if col_currency and not pd.isna(row[col_currency]):
            moeda = str(row[col_currency]).strip().upper()
        else:
            val_str_raw = str(row[col_val]).upper() if col_val else ''
            if 'USD' in val_str_raw or 'U$' in val_str_raw:
                moeda = 'USD'
            elif 'EUR' in val_str_raw or '€' in val_str_raw:
                moeda = 'EUR'
            elif 'BRL' in val_str_raw or 'R$' in val_str_raw:
                moeda = 'BRL'

        fp = str(filepath).lower()
        if 'br_' in fp or 'santander' in fp or 'itau' in fp or 'bradesco' in fp or 'nubank' in fp or 'brasil' in fp:
            moeda = 'BRL'

        rate = get_exchange_rate(date_str, moeda, 'EUR')
        valor_eur = round(val_float * rate, 2)
        categoria = guess_category(descricao)

        transactions.append({
            'id': str(uuid.uuid4())[:8],
            'data': date_str,
            'descricao': descricao,
            'valor_original': val_float,
            'moeda': moeda,
            'cambio': rate,
            'valor_eur': valor_eur,
            'pag1': round(val_float / 2, 2),
            'pag2': round(val_float / 2, 2),
            'categoria': categoria,
            'is_debit': is_debit,
            'receita': not is_debit,
        })

    return transactions


def _read_xml_xls(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        if '<?xml' not in content or ('Workbook' not in content and 'worksheet' not in content.lower()):
            return None

        # Use lxml.etree directly for correct namespace + ss:Index handling
        try:
            import lxml.etree as ET
            root = ET.fromstring(content.encode('utf-8', errors='ignore'))
            data = []
            for row in root.xpath('//*[local-name()="Row"]'):
                row_data = []
                for cell in row:
                    if not (cell.tag.endswith('}Cell') or cell.tag == 'Cell'):
                        continue
                    # ss:Index may be stored as {namespace_uri}Index by lxml
                    idx_attr = None
                    for attr_key, attr_val in cell.attrib.items():
                        if attr_key.endswith('}Index') or attr_key in ('Index', 'ss:Index'):
                            idx_attr = attr_val
                            break
                    if idx_attr:
                        target = int(idx_attr) - 1  # 1-based → 0-based
                        while len(row_data) < target:
                            row_data.append('')
                    data_els = [c for c in cell if c.tag.endswith('}Data') or c.tag == 'Data']
                    row_data.append(data_els[0].text or '' if data_els else '')
                if any(row_data):
                    data.append(row_data)
            if data:
                max_len = max(len(r) for r in data)
                padded = [r + [''] * (max_len - len(r)) for r in data]
                return pd.DataFrame(padded)
        except Exception:
            pass

        # Fallback: BeautifulSoup (handles some edge cases lxml misses)
        soup = BeautifulSoup(content, 'xml')
        data = []
        for row in soup.find_all('Row'):
            row_data = []
            for cell in row.find_all('Cell'):
                idx_attr = None
                for key in cell.attrs:
                    if 'Index' in str(key):
                        idx_attr = cell.attrs[key]
                        break
                if idx_attr:
                    target = int(idx_attr) - 1
                    while len(row_data) < target:
                        row_data.append('')
                data_tag = cell.find('Data')
                row_data.append(data_tag.text if data_tag else '')
            if any(row_data):
                data.append(row_data)
        if data:
            max_len = max(len(r) for r in data)
            padded = [r + [''] * (max_len - len(r)) for r in data]
            return pd.DataFrame(padded)
    except Exception:
        pass
    return None


def process_file(filepath):
    if filepath.lower().endswith('.csv'):
        try:
            df = pd.read_csv(filepath, sep=None, engine='python')
            return _df_to_transactions(df, filepath=filepath)
        except Exception:
            return []

    elif filepath.lower().endswith(('.xls', '.xlsx', '.xml')):
        df = _read_xml_xls(filepath)
        if df is not None:
            txns = _df_to_transactions(df, filepath=filepath)
            if txns:
                return txns
        try:
            df = pd.read_excel(filepath)
            txns = _df_to_transactions(df, filepath=filepath)
            if txns:
                return txns
        except Exception:
            pass
        try:
            df = pd.read_excel(filepath, engine='xlrd')
            return _df_to_transactions(df, filepath=filepath)
        except Exception:
            return []

    elif filepath.lower().endswith('.pdf'):
        transactions = []
        try:
            with pdfplumber.open(filepath) as pdf:
                for page in pdf.pages:
                    for table in page.extract_tables():
                        if len(table) > 1:
                            header = table[0]
                            data_rows = table[1:]

                            reconstructed_rows = []
                            for row in data_rows:
                                if any('\n' in str(c) for c in row):
                                    split_cols = [str(c).split('\n') if c is not None else [''] for c in row]
                                    max_l = max(len(col) for col in split_cols)
                                    padded = [col + [''] * (max_l - len(col)) for col in split_cols]
                                    for i in range(max_l):
                                        reconstructed_rows.append([padded[c][i] for c in range(len(padded))])
                                else:
                                    reconstructed_rows.append(row)

                            if reconstructed_rows:
                                df = pd.DataFrame(reconstructed_rows, columns=header)
                                transactions.extend(_df_to_transactions(df, filepath=filepath))
        except Exception:
            pass
        return transactions

    return []


def process_despesas_file(filepath):
    df = None
    if filepath.lower().endswith('.csv'):
        try:
            df = pd.read_csv(filepath, sep=None, engine='python')
        except Exception:
            return []
    elif filepath.lower().endswith(('.xls', '.xlsx', '.xml')):
        df = _read_xml_xls(filepath)
        if df is None:
            try:
                df = pd.read_excel(filepath)
            except Exception:
                try:
                    df = pd.read_excel(filepath, engine='xlrd')
                except Exception:
                    return []

    if df is None or df.empty:
        return []

    header_idx = -1
    for idx, row in df.head(10).iterrows():
        row_str = ' '.join(str(v).lower() for v in row.values if not pd.isna(v))
        if 'despesa' in row_str or 'fator' in row_str or 'prioridade' in row_str:
            header_idx = idx
            break

    if header_idx != -1:
        new_header = df.iloc[header_idx]
        df = df[header_idx + 1:].copy()
        df.columns = new_header

    col_despesa = _find_column(df, ['despesa', 'nome', 'descri', 'titulo'])
    col_tipo = _find_column(df, ['tipo', 'categoria', 'grupo'])
    col_fator = _find_column(df, ['fator', 'divis', 'divisão', 'peso'])
    col_prio = _find_column(df, ['prioridade', 'import', 'urg'])

    if not col_despesa:
        cols = df.columns
        col_despesa = cols[0] if len(cols) > 0 else None
        col_tipo = cols[1] if len(cols) > 1 else None
        col_fator = cols[2] if len(cols) > 2 else None
        col_prio = cols[3] if len(cols) > 3 else None

    if not col_despesa:
        return []

    despesas = []
    for _, row in df.iterrows():
        desp = str(row[col_despesa]).strip() if col_despesa and not pd.isna(row[col_despesa]) else ''
        if not desp or desp.lower() in ['nan', 'none', '']:
            continue

        tipo = str(row[col_tipo]).strip() if col_tipo and not pd.isna(row[col_tipo]) else ''

        try:
            fator_val = str(row[col_fator]).replace(',', '.') if col_fator and not pd.isna(row[col_fator]) else '1'
            fator = int(float(fator_val))
            if fator < 1:
                fator = 1
            if fator > 10:
                fator = 10
        except Exception:
            fator = 1

        prio = str(row[col_prio]).strip() if col_prio and not pd.isna(row[col_prio]) else ''
        if prio.lower() == 'nan':
            prio = ''
        if tipo.lower() == 'nan':
            tipo = ''

        despesas.append({
            'despesa': desp,
            'tipo_despesa': tipo,
            'fator_divisao': fator,
            'prioridade': prio,
        })

    return despesas
