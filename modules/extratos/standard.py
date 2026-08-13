"""Fast path para formatos padronizados: OFX/QFX (BR) e CAMT.053/MT940 (PT).

`try_parse(filepath)` devolve uma lista de transações (formato §7.1) se o arquivo
for de um desses formatos, ou None para deixar o fluxo fingerprint/indução rodar.
"""
import os
import re

from .parser import _parse_date


def _to_txn(*, data, descricao, valor, is_debit, moeda, idx, saldo=None):
    return {
        'id': f'linha-{idx}',
        'data': data,
        'descricao': descricao,
        'valor_original': abs(valor),
        'moeda': moeda,
        'saldo': saldo,
        'is_debit': is_debit,
        'linha_idx': idx,
        'data_fallback': False,
    }


def _parse_ofx(filepath):
    import xml.etree.ElementTree as ET
    try:
        with open(filepath, 'rb') as f:
            content = f.read()
    except OSError:
        return None

    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        # OFX antigo (SGML) não é XML válido — tenta parse textual.
        return _parse_ofx_sgml(content)

    txns = []
    idx = 0
    moeda = 'BRL'
    for stmt in root.iter():
        if stmt.tag.endswith('CURDEF'):
            moeda = (stmt.text or 'BRL').strip().upper()
            break
    for t in root.iter():
        if not t.tag.endswith('STMTTRN'):
            continue
        def txt(tag):
            for el in t:
                if el.tag.endswith(tag):
                    return el.text.strip() if el.text else ''
            return ''
        data, fallback = _parse_date(txt('DTPOSTED') or txt('DTUSER'))
        if data is None:
            data, fallback = None, True
        desc = txt('MEMO') or txt('NAME')
        valor = _ofx_amount(txt('TRNAMT'))
        txns.append(_to_txn(data=data, descricao=desc, valor=valor,
                            is_debit=valor < 0, moeda=moeda, idx=idx))
        idx += 1
    return txns or None


def _ofx_amount(s):
    s = (s or '').strip()
    try:
        return float(s)
    except ValueError:
        return 0.0


def _parse_ofx_sgml(content):
    texto = content.decode('utf-8', errors='ignore')
    blocos = re.split(r'<STMTTRN>', texto)
    if len(blocos) < 2:
        return None
    txns = []
    idx = 0
    moeda = 'BRL'
    m = re.search(r'<CURDEF>\s*(\w{3})', texto)
    if m:
        moeda = m.group(1).upper()
    for bloco in blocos[1:]:
        def tag(nome):
            m = re.search(rf'<{nome}>\s*(.*?)\s*(?:<|$)', bloco, re.S)
            return m.group(1) if m else ''
        data, fallback = _parse_date(tag('DTPOSTED') or tag('DTUSER'))
        if data is None:
            data, fallback = None, True
        desc = tag('MEMO') or tag('NAME')
        valor = _ofx_amount(tag('TRNAMT'))
        txns.append(_to_txn(data=data, descricao=desc, valor=valor,
                            is_debit=valor < 0, moeda=moeda, idx=idx))
        idx += 1
    return txns or None


def _parse_camt053(filepath):
    import xml.etree.ElementTree as ET
    try:
        with open(filepath, 'rb') as f:
            root = ET.fromstring(f.read())
    except (OSError, ET.ParseError):
        return None
    ns = {'n': 'urn:iso:std:iso:20022:tech:xsd:camt.053.001.02',
          'n8': 'urn:iso:std:iso:20022:tech:xsd:camt.053.001.08'}

    txns = []
    idx = 0
    for ntry in root.iter():
        if not ntry.tag.endswith('Ntry'):
            continue
        amt = ntry.find('n:Amt', ns) or ntry.find('n8:Amt', ns)
        moeda = amt.get('Ccy', 'EUR') if amt is not None else 'EUR'
        valor = float(amt.text) if amt is not None and amt.text else 0.0
        is_debit = (ntry.find('n:CdtDbtInd', ns) or ntry.find('n8:CdtDbtInd', ns))
        is_debit = is_debit.text == 'DBIT' if is_debit is not None else (valor < 0)
        desc = ''
        for el in ntry.iter():
            if el.tag.endswith('AddtlNtryInf'):
                desc = el.text or ''
        data = None
        for el in ntry.iter():
            if el.tag.endswith('ValDt') or el.tag.endswith('BookgDt'):
                data, _ = _parse_date(el.text)
                break
        txns.append(_to_txn(data=data, descricao=desc, valor=valor,
                            is_debit=is_debit, moeda=moeda, idx=idx))
        idx += 1
    return txns or None


def _parse_mt940(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            texto = f.read()
    except OSError:
        return None
    if ':940:' not in texto:
        return None
    txns = []
    idx = 0
    moeda = 'EUR'
    m = re.search(r':60F:.*?([A-Z]{3})(\d{8})([A-Z]{3})', texto, re.S)
    if m:
        moeda = m.group(1)
    for bloco in re.split(r'\n(?=:61:)', texto):
        if not bloco.startswith(':61:'):
            continue
        m = re.match(r':61:(\d{6})(\d{4})?(D|C)(\d+)[,.?]?(\d*)', bloco)
        if not m:
            continue
        data = f'{m.group(1)[:2]}/{m.group(1)[2:4]}/20{m.group(1)[4:6]}'
        is_debit = m.group(3) == 'D'
        inteiro = m.group(4)
        frac = m.group(5) or '00'
        valor = float(f'{inteiro}.{frac}')
        desc = bloco.split(')', 1)[1].split('\n')[0].strip() if ')' in bloco else ''
        data_iso, _ = _parse_date(data)
        txns.append(_to_txn(data=data_iso, descricao=desc, valor=valor,
                            is_debit=is_debit, moeda=moeda, idx=idx))
        idx += 1
    return txns or None


def try_parse(filepath):
    ext = os.path.splitext(filepath)[1].lower()
    if ext in ('.ofx', '.qfx'):
        return _parse_ofx(filepath)
    if ext == '.xml':
        return _parse_camt053(filepath)
    if ext in ('.txt',):
        return _parse_mt940(filepath)
    return None
