"""Executor determinístico dirigido por `spec` (receita).

Nunca devolve [] silenciosamente: ou extrai linhas, ou levanta ReceitaFalhou.
Reaproveita os primitivos de parsing já testados do parser.py.
"""
import re

from .errors import ReceitaFalhou, ArquivoIlegivel
from .parser import _clean_text, _parse_value, _parse_date


def apply(spec, filepath):
    estrategia = spec.get('estrategia')
    if estrategia == 'planilha':
        txns = _apply_planilha(spec, filepath)
    elif estrategia == 'pdf_tabela':
        txns = _apply_pdf_tabela(spec, filepath)
    elif estrategia == 'pdf_words':
        txns = _apply_pdf_words(spec, filepath)
    elif estrategia == 'linhas_regex':
        txns = _apply_linhas_regex(spec, filepath)
    else:
        raise ReceitaFalhou(f'Estratégia desconhecida: {estrategia!r}')

    if not txns:
        raise ReceitaFalhou(
            'A receita não extraiu nenhuma transação.',
            detalhe={'estrategia': estrategia},
        )
    return txns


def _ignorar(spec, texto):
    for padrao in spec.get('ignorar_linhas_regex', []) or []:
        if re.search(padrao, texto):
            return True
    return False


def _parse_data_spec(s, spec):
    if s is None:
        return None, False
    s = str(s).strip()
    if not s:
        return None, False
    from datetime import datetime
    dayfirst = spec.get('dayfirst')
    if dayfirst is None:
        dayfirst = True
    try:
        dt = datetime.strptime(s, '%d/%m/%Y') if dayfirst else datetime.strptime(s, '%m/%d/%Y')
        return dt.strftime('%Y-%m-%d'), False
    except ValueError:
        return _parse_date(s)


def _read_tabular(filepath):
    import pandas as pd
    if filepath.lower().endswith('.csv'):
        return pd.read_csv(filepath, sep=None, engine='python', header=None)
    return pd.read_excel(filepath, header=None)


def _colunas_map(spec):
    return spec.get('colunas') or spec.get('colunas_idx') or {}


def _montar_transacao(*, data, descricao, valor, is_debit, moeda, saldo, idx, extra=None):
    txn = {
        'id': f'linha-{idx}',
        'data': data,
        'descricao': descricao,
        'valor_original': valor,
        'moeda': moeda,
        'saldo': saldo,
        'is_debit': is_debit,
        'linha_idx': idx,
    }
    if extra:
        txn.update(extra)
    return txn


def _apply_planilha(spec, filepath):
    import pandas as pd
    df = _read_tabular(filepath)

    header_row = spec.get('header_row', 0)
    colunas = _colunas_map(spec)
    por_indice = any(isinstance(k, int) or str(k).isdigit() for k in colunas)

    if not por_indice and header_row is not None:
        df.columns = [str(c) for c in df.iloc[header_row]]
        df = df.iloc[header_row + 1:]

    moeda = spec.get('moeda') or 'EUR'
    sinal = spec.get('sinal', 'colunas_separadas')

    def pegar(row, papel):
        alvo = colunas.get(papel)
        if alvo is None:
            return None
        if por_indice:
            idx = int(alvo)
            if idx < len(row):
                v = row.iloc[idx]
                return None if pd.isna(v) else v
            return None
        if alvo in df.columns:
            v = row[alvo]
            return None if pd.isna(v) else v
        return None

    txns = []
    for i, (_, row) in enumerate(df.iterrows()):
        descricao = _clean_text(pegar(row, 'descricao') or '').strip()
        if not descricao or _ignorar(spec, descricao):
            continue

        data, fallback = _parse_data_spec(pegar(row, 'data'), spec)

        valor = None
        is_debit = False
        if sinal == 'colunas_separadas':
            deb = _parse_value(pegar(row, 'debito'))
            cre = _parse_value(pegar(row, 'credito'))
            if deb:
                valor, is_debit = abs(deb), True
            elif cre:
                valor, is_debit = abs(cre), False
        elif sinal == 'coluna_tipo':
            raw = pegar(row, 'valor')
            tipo = str(pegar(row, 'tipo') or '').upper()
            valores_debito = [v.upper() for v in spec.get('valores_debito', ['D', 'DEB'])]
            is_debit = any(t in tipo for t in valores_debito)
            valor = abs(_parse_value(raw))
        else:  # valor_com_sinal
            raw = pegar(row, 'valor')
            parsed = _parse_value(raw)
            is_debit = parsed < 0
            valor = abs(parsed)

        saldo = _parse_value(pegar(row, 'saldo'))
        if pegar(row, 'saldo') is None:
            saldo = None

        if valor is None:
            continue

        txn = _montar_transacao(data=data, descricao=descricao, valor=valor,
                                is_debit=is_debit, moeda=moeda, saldo=saldo, idx=i,
                                extra={'data_fallback': fallback})
        txns.append(txn)
    return txns


def _apply_pdf_tabela(spec, filepath):
    import pdfplumber
    colunas = _colunas_map(spec)
    min_colunas = spec.get('min_colunas', 3)
    moeda = spec.get('moeda') or 'EUR'
    sinal = spec.get('sinal', 'colunas_separadas')

    txns = []
    idx = 0
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                if not table or len(table[0]) < min_colunas:
                    continue
                header = [str(c) for c in table[0]]
                header_idx = {nome: header.index(nome) for nome in colunas.values()
                              if nome in header}
                for row in table[1:]:
                    descricao = _clean_text(row[header_idx['descricao']] or '') \
                        if 'descricao' in header_idx else ''
                    if not descricao or _ignorar(spec, descricao):
                        continue
                    data, fallback = _parse_data_spec(
                        row[header_idx['data']] if 'data' in header_idx else None, spec)
                    valor = None
                    is_debit = False
                    if sinal == 'colunas_separadas':
                        deb = _parse_value(row[header_idx['debito']]) if 'debito' in header_idx else 0.0
                        cre = _parse_value(row[header_idx['credito']]) if 'credito' in header_idx else 0.0
                        if deb:
                            valor, is_debit = abs(deb), True
                        elif cre:
                            valor, is_debit = abs(cre), False
                    else:
                        parsed = _parse_value(row[header_idx['valor']] if 'valor' in header_idx else None)
                        is_debit = parsed < 0
                        valor = abs(parsed)
                    saldo = _parse_value(row[header_idx['saldo']]) if 'saldo' in header_idx else None
                    txns.append(_montar_transacao(
                        data=data, descricao=descricao, valor=valor, is_debit=is_debit,
                        moeda=moeda, saldo=saldo, idx=idx,
                        extra={'data_fallback': fallback}))
                    idx += 1
    return txns


def _apply_pdf_words(spec, filepath):
    import pdfplumber
    faixas = spec.get('faixas_x', {})
    moeda = spec.get('moeda') or 'EUR'
    tolerancia = spec.get('tolerancia_y', 2.5)
    linha_regex = re.compile(spec.get('linha_transacao_regex', r'^\d{2}[./-]\d{2}'))

    def em_faixa(x, papel):
        faixa = faixas.get(papel)
        if not faixa:
            return False
        return faixa[0] <= x < faixa[1]

    txns = []
    idx = 0
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            words = page.extract_words()
            linhas = {}
            for w in words:
                chave = round(w['top'] / tolerancia)
                linhas.setdefault(chave, []).append(w)
            for chave in sorted(linhas):
                wds = sorted(linhas[chave], key=lambda w: w['x0'])
                texto = ' '.join(w['text'] for w in wds)
                if not linha_regex.match(texto) or _ignorar(spec, texto):
                    continue
                data_w = next((w for w in wds if em_faixa(w['x0'], 'data')), None)
                desc = ' '.join(w['text'] for w in wds if em_faixa(w['x0'], 'descricao')).strip()
                deb = next((_parse_value(w['text']) for w in wds if em_faixa(w['x0'], 'debito')), 0.0)
                cre = next((_parse_value(w['text']) for w in wds if em_faixa(w['x0'], 'credito')), 0.0)
                saldo_w = next((w for w in wds if em_faixa(w['x0'], 'saldo')), None)
                saldo = _parse_value(saldo_w['text']) if saldo_w else None

                if deb:
                    valor, is_debit = abs(deb), True
                elif cre:
                    valor, is_debit = abs(cre), False
                else:
                    continue

                data, fallback = _parse_data_spec(data_w['text'] if data_w else None, spec)
                txns.append(_montar_transacao(
                    data=data, descricao=desc, valor=valor, is_debit=is_debit,
                    moeda=moeda, saldo=saldo, idx=idx,
                    extra={'data_fallback': fallback}))
                idx += 1
    return txns


def _apply_linhas_regex(spec, filepath):
    padrao = re.compile(spec['regex'])
    moeda = spec.get('moeda') or 'BRL'
    txns = []
    idx = 0
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        for linha in f:
            linha = _clean_text(linha).strip()
            if not linha or _ignorar(spec, linha):
                continue
            m = padrao.search(linha)
            if not m:
                continue
            g = m.groupdict()
            data, fallback = _parse_data_spec(g.get('data'), spec)
            valor_parsed = _parse_value(g.get('valor'))
            is_debit = valor_parsed < 0
            txns.append(_montar_transacao(
                data=data, descricao=g.get('descricao', '').strip(),
                valor=abs(valor_parsed), is_debit=is_debit, moeda=moeda, saldo=None,
                idx=idx, extra={'data_fallback': fallback}))
            idx += 1
    return txns
