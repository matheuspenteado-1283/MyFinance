import os
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

        # Detectar moeda inspecionando nomes das colunas de valor (mais confiável)
        col_hint = ' '.join(str(c).lower() for c in [col_val, col_deb, col_cred, *df.columns] if c)
        if 'r$' in col_hint or 'reais' in col_hint or '(brl)' in col_hint:
            moeda = 'BRL'
        elif '€' in col_hint or '(eur)' in col_hint or 'euros' in col_hint:
            moeda = 'EUR'
        elif 'us$' in col_hint or '(usd)' in col_hint or 'dólar' in col_hint or 'dolar' in col_hint:
            moeda = 'USD'
        elif col_deb or col_cred or _find_column(df, ['data operao', 'data operação', 'saldo controlo']):
            # Fallback: débito/crédito separados sem indicador de moeda → Novo Banco PT (EUR)
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
        content = None
        for enc in ('utf-8-sig', 'utf-16', 'utf-8', 'latin-1'):
            try:
                with open(filepath, 'r', encoding=enc, errors='ignore') as f:
                    content = f.read()
                if '<?xml' in content:
                    break
                content = None
            except Exception:
                content = None
        if not content:
            return None
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


def _parse_pdf_text_lines(lines, filepath=''):
    """Tenta extrair transações de linhas de texto de PDF sem tabela estruturada.
    Suporta: dd/mm/yyyy, yyyy-mm-dd, dd-mm-yyyy, dd/mm (sem ano — infere o ano do texto).
    """
    date_full = re.compile(r'\b(\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2}|\d{2}-\d{2}-\d{4})\b')
    date_short = re.compile(r'\b(\d{2}/\d{2})\b')
    value_pattern = re.compile(r'-?(?:R\$|€|USD)?\s*\d{1,3}(?:[.\s]\d{3})*[.,]\d{2}(?:€)?')

    # Detectar moeda nas primeiras linhas do PDF (cabeçalho)
    import datetime
    header_text = ' '.join(lines[:30]).upper()
    if '€' in header_text or ' EUR' in header_text or 'EUROS' in header_text:
        detected_currency = 'EUR'
    elif 'USD' in header_text or 'U$' in header_text or 'DÓLAR' in header_text or 'DOLAR' in header_text:
        detected_currency = 'USD'
    elif 'R$' in header_text or ' BRL' in header_text or 'REAIS' in header_text:
        detected_currency = 'BRL'
    else:
        detected_currency = None  # deixa _df_to_transactions decidir pelo filepath

    # Tenta inferir o ano lendo as linhas de cabeçalho
    year = None
    for line in lines[:15]:
        m = re.search(r'\b(20\d{2})\b', line)
        if m:
            year = m.group(1)
            break
    if not year:
        year = str(datetime.date.today().year)

    rows = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Ignora linhas de saldo/totais
        if re.match(r'(?i)saldo|total|dinheiro em conta', line):
            continue

        date_match = date_full.search(line)
        short_match = None
        if not date_match:
            short_match = date_short.search(line)
            if not short_match:
                continue

        value_matches = value_pattern.findall(line)
        if not value_matches:
            continue

        if date_match:
            raw_date = date_match.group(1)
            desc_start = date_match.end()
        else:
            day, month = short_match.group(1).split('/')
            raw_date = f'{day}/{month}/{year}'
            desc_start = short_match.end()

        # Se a linha tem 2 datas (data lançamento + data-valor, ex: Revolut/Novo Banco),
        # o último valor é o saldo contabilístico — usar o penúltimo (valor da transação).
        # Detecta segunda data na parte restante da linha após a primeira data.
        remaining = line[desc_start:]
        has_second_date = bool(date_full.search(remaining))
        if has_second_date and len(value_matches) >= 2:
            chosen_value = value_matches[-2]
            # A descrição fica entre a 2ª data e o valor da transação
            second_date_match = date_full.search(remaining)
            desc_start2 = desc_start + second_date_match.end()
            chosen_val_pos = line.find(chosen_value, desc_start2)
            description = line[desc_start2:chosen_val_pos].strip(' -|R$€')
        else:
            chosen_value = value_matches[-1]
            last_val_pos = line.rfind(chosen_value)
            description = line[desc_start:last_val_pos].strip(' -|R$€')

        raw_value = chosen_value.replace('R$', '').replace('€', '').replace(' ', '').strip()
        if not description:
            description = line

        rows.append({'data': raw_date, 'descricao': description, 'valor': raw_value})

    if not rows:
        return []

    df = pd.DataFrame(rows)
    if detected_currency:
        df['moeda'] = detected_currency
    return _df_to_transactions(df, filepath=filepath)


def _parse_pdf_words(pdf, filepath=''):
    """Parsing de PDFs com colunas de débito/crédito separadas usando posição X das palavras.
    Detecta automaticamente quais colunas são 'retirado' (débito) e 'recebido' (crédito).
    Retorna lista de transações ou [] se não conseguir detectar o formato.
    """
    import datetime
    money_re = re.compile(r'^-?\d{1,3}(?:[.\s]\d{3})*[,\.]\d{2}[€$]?$')
    date_re = re.compile(r'^\d{2}/\d{2}/\d{4}$')

    def clean_spaces(s):
        # Remove vários tipos de espaço especial
        return s.replace('\xa0', '').replace('\u202f', '').replace('\u00a0', '').replace(' ', '')

    # Detectar moeda no texto do PDF
    header_text = ''
    for page in pdf.pages[:1]:
        t = page.extract_text() or ''
        header_text = t[:500].upper()
    if '\u20ac' in header_text or ' EUR' in header_text or 'EXTRATO DE EUR' in header_text:
        detected_currency = 'EUR'
    elif 'USD' in header_text or 'U$' in header_text:
        detected_currency = 'USD'
    elif 'R$' in header_text or ' BRL' in header_text:
        detected_currency = 'BRL'
    else:
        detected_currency = None

    # Detectar colunas de débito/crédito analisando palavras de todas as páginas
    debit_x, credit_x = None, None
    for page in pdf.pages:
        for w in page.extract_words():
            txt = w['text'].lower()
            if txt in ('retirado', 'debito', 'saida', 'saída'):
                debit_x = w['x0']
            elif txt in ('recebido', 'credito', 'entrada', 'crédito'):
                credit_x = w['x0']
        if debit_x is not None:
            break

    if debit_x is None:
        return []

    rows = []
    for page in pdf.pages:
        words = page.extract_words()
        # Agrupa palavras por linha usando 'top' (tolerância 3pt)
        lines_map = {}
        for w in words:
            y = round(w['top'] / 3) * 3
            lines_map.setdefault(y, []).append(w)

        for y in sorted(lines_map.keys()):
            wds = sorted(lines_map[y], key=lambda w: w['x0'])

            # Linha de transação: tem pelo menos 2 datas
            dates = [w for w in wds if date_re.match(w['text'])]
            if len(dates) < 2:
                continue

            # Valores monetários na linha
            money_words = []
            for w in wds:
                cleaned = clean_spaces(w['text'])
                if money_re.match(cleaned):
                    money_words.append((w['x0'], w['text']))

            if not money_words:
                continue

            # Descrição: texto entre x1 da 2ª data e x0 do primeiro valor monetário
            date2_x1 = dates[1]['x1']
            first_money_x = money_words[0][0]
            desc_words = [w['text'] for w in wds if w['x0'] > date2_x1 and w['x0'] < first_money_x - 5]
            description = ' '.join(desc_words).strip()
            if not description:
                desc_set = {dates[0]['text'], dates[1]['text']}
                description = ' '.join(
                    w['text'] for w in wds
                    if w['text'] not in desc_set
                    and not money_re.match(clean_spaces(w['text']))
                ).strip()

            # Valor da transação = primeiro valor monetário; último = saldo contabilístico
            val_x, val_raw = money_words[0]
            val_clean = clean_spaces(val_raw).replace('€', '').replace('$', '').replace('.', '').replace(',', '.')
            try:
                val_float = abs(float(val_clean))
            except Exception:
                continue

            if val_float == 0.0:
                continue

            # is_debit: posição X do valor mais próxima da coluna "retirado" que da "recebido"
            if credit_x is not None:
                is_debit = abs(val_x - debit_x) < abs(val_x - credit_x)
            else:
                is_debit = True

            raw_date = dates[0]['text']
            date_str = _parse_date(raw_date)

            moeda = detected_currency or 'EUR'
            rate = get_exchange_rate(date_str, moeda, 'EUR')
            valor_eur = round(val_float * rate, 2)
            categoria = guess_category(description)

            rows.append({
                'id': str(uuid.uuid4())[:8],
                'data': date_str,
                'descricao': description,
                'valor_original': val_float,
                'moeda': moeda,
                'cambio': rate,
                'valor_eur': valor_eur,
                'pag1': round(val_float / 2, 2),
                'pag2': round(val_float / 2, 2),
                'categoria': categoria,
                'is_debit': is_debit,
            })

    return rows


def _read_ofx_xml(filepath):
    """Lê arquivos XML no formato OFX/SGML bancário e retorna DataFrame."""
    try:
        import lxml.etree as ET
        with open(filepath, 'rb') as f:
            content = f.read()
        # OFX moderno é XML válido
        try:
            root = ET.fromstring(content)
        except ET.XMLSyntaxError:
            return None
        ns = {'': ''}
        rows = []
        for stmttrn in root.xpath('//*[local-name()="STMTTRN"]'):
            def txt(tag):
                el = stmttrn.find('.//*[local-name()='+"'"+tag+"'"+']')
                return el.text.strip() if el is not None and el.text else ''
            rows.append({
                'data': txt('DTPOSTED') or txt('DTUSER'),
                'descricao': txt('MEMO') or txt('NAME'),
                'valor': txt('TRNAMT'),
            })
        if rows:
            return pd.DataFrame(rows)
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
        # Tenta SpreadsheetML (Excel XML)
        df = _read_xml_xls(filepath)
        if df is not None:
            txns = _df_to_transactions(df, filepath=filepath)
            if txns:
                return txns
        # Tenta OFX/XML bancário
        if filepath.lower().endswith('.xml'):
            df = _read_ofx_xml(filepath)
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

                # Fallback 1: parsing por posição X das palavras (detecta débito/crédito por coluna)
                if not transactions:
                    transactions = _parse_pdf_words(pdf, filepath)

                # Fallback 2: extração de texto linha a linha quando não há tabelas detectáveis
                if not transactions:
                    all_lines = []
                    for page in pdf.pages:
                        text = page.extract_text()
                        if text:
                            all_lines.extend(text.split('\n'))
                    transactions = _parse_pdf_text_lines(all_lines, filepath)
        except Exception:
            pass
        return transactions

    return []


def _debug_file(filepath):
    """Returns diagnostic info about why a file produced 0 transactions."""
    import traceback
    info = {'file': os.path.basename(filepath), 'steps': []}
    try:
        ext = filepath.lower().split('.')[-1]
        info['ext'] = ext

        if ext in ('xls', 'xlsx', 'xml'):
            # Step 1: XML parse
            try:
                df_xml = _read_xml_xls(filepath)
                if df_xml is not None:
                    info['steps'].append({
                        'method': 'xml',
                        'rows': len(df_xml),
                        'cols': list(df_xml.columns[:10]),
                        'sample': df_xml.head(5).astype(str).values.tolist(),
                    })
                    txns = _df_to_transactions(df_xml, filepath=filepath)
                    info['steps'][-1]['transactions'] = len(txns)
                else:
                    info['steps'].append({'method': 'xml', 'result': 'None (not XML format)'})
            except Exception as e:
                info['steps'].append({'method': 'xml', 'error': str(e)})

            # Step 2: openpyxl
            try:
                df2 = pd.read_excel(filepath)
                info['steps'].append({
                    'method': 'openpyxl',
                    'rows': len(df2),
                    'cols': list(df2.columns[:10]),
                })
                txns2 = _df_to_transactions(df2, filepath=filepath)
                info['steps'][-1]['transactions'] = len(txns2)
            except Exception as e:
                info['steps'].append({'method': 'openpyxl', 'error': str(e)})

            # Step 3: xlrd
            try:
                df3 = pd.read_excel(filepath, engine='xlrd')
                info['steps'].append({
                    'method': 'xlrd',
                    'rows': len(df3),
                    'cols': list(df3.columns[:10]),
                })
                txns3 = _df_to_transactions(df3, filepath=filepath)
                info['steps'][-1]['transactions'] = len(txns3)
            except Exception as e:
                info['steps'].append({'method': 'xlrd', 'error': str(e)})

    except Exception as e:
        info['error'] = str(e)
        info['trace'] = traceback.format_exc()
    return info


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
