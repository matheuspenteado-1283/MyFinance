from dataclasses import dataclass, field
from datetime import date, timedelta

PESOS = {
    'saldo_encadeado':    40,
    'cobertura':          25,
    'datas_periodo':      10,
    'sem_duplicatas':     10,
    'sem_data_fallback':  10,
    'sem_valor_zero':      5,
}

LIMIAR_AUTO    = 90
LIMIAR_PARCIAL = 60


@dataclass
class Check:
    nome: str
    peso: int
    passou: bool
    detalhe: str = None
    linhas: list = field(default_factory=list)


@dataclass
class Resultado:
    score: int
    checks: list
    linhas_suspeitas: list

    def to_dict(self):
        return {
            'score': self.score,
            'checks': [c.__dict__ for c in self.checks],
            'linhas_suspeitas': self.linhas_suspeitas,
        }


def _com_sinal(t):
    v = float(t.get('valor_original') or 0)
    return -abs(v) if t.get('is_debit') else abs(v)


def _as_date(d):
    """Aceita `date`/`datetime` ou string ISO 'YYYY-MM-DD'."""
    if isinstance(d, date):
        return d
    from datetime import datetime
    try:
        return datetime.strptime(str(d)[:10], '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


def validate(txns, *, linhas_com_data_no_bruto=None, periodo=None,
             saldo_inicial=None, saldo_final=None):
    checks = []
    suspeitas = set()

    # ── 1. Saldo encadeado ────────────────────────────────────────────────
    com_saldo = [t for t in txns if t.get('saldo') is not None]
    if len(com_saldo) >= 2:
        divergentes = []
        for i in range(1, len(com_saldo)):
            ant, cur = com_saldo[i - 1], com_saldo[i]
            try:
                delta = round(float(cur['saldo']) - float(ant['saldo']), 2)
            except (TypeError, ValueError):
                divergentes.append(cur.get('linha_idx'))
                continue
            esperado = round(_com_sinal(cur), 2)
            if abs(delta - esperado) > 0.01:
                divergentes.append(cur.get('linha_idx'))
        suspeitas.update(d for d in divergentes if d is not None)
        checks.append(Check(
            'saldo_encadeado', PESOS['saldo_encadeado'], not divergentes,
            f'{len(com_saldo) - len(divergentes)}/{len(com_saldo)} linhas conferem',
            divergentes,
        ))
    elif saldo_inicial is not None and saldo_final is not None:
        soma = round(sum(_com_sinal(t) for t in txns), 2)
        esperado = round(float(saldo_final) - float(saldo_inicial), 2)
        ok = abs(soma - esperado) <= 0.01
        checks.append(Check('saldo_total', PESOS['saldo_encadeado'], ok,
                            f'soma={soma:.2f} esperado={esperado:.2f}'))
    else:
        checks.append(Check('saldo_encadeado', 0, True, 'extrato sem coluna de saldo'))

    # ── 2. Cobertura ──────────────────────────────────────────────────────
    if linhas_com_data_no_bruto:
        ratio = len(txns) / max(linhas_com_data_no_bruto, 1)
        ok = ratio >= 0.95
        checks.append(Check('cobertura', PESOS['cobertura'], ok,
                            f'{len(txns)} extraídas de ~{linhas_com_data_no_bruto} '
                            f'linhas com data no texto bruto'))
    else:
        checks.append(Check('cobertura', PESOS['cobertura'], len(txns) > 0,
                            f'{len(txns)} transações'))

    # ── 3. Datas dentro do período ────────────────────────────────────────
    if txns:
        if periodo:
            ini, fim = periodo
            fora = [t.get('linha_idx') for t in txns
                    if t.get('data') and not (ini <= _as_date(t['data']) <= fim)]
        else:
            hoje = date.today()
            fora = [t.get('linha_idx') for t in txns
                    if t.get('data') and (
                        _as_date(t['data']) > hoje + timedelta(days=1) or
                        _as_date(t['data']) < hoje - timedelta(days=400)
                    )]
        suspeitas.update(i for i in fora if i is not None)
        checks.append(Check('datas_periodo', PESOS['datas_periodo'], not fora,
                            f'{len(fora)} datas fora do período', fora))

    # ── 4. Duplicatas exatas ──────────────────────────────────────────────
    vistos, dups = {}, []
    for t in txns:
        chave = (t.get('data'), (t.get('descricao') or '').strip(),
                 t.get('valor_original'))
        if chave in vistos:
            dups.append(t.get('linha_idx'))
        vistos[chave] = t.get('linha_idx')
    suspeitas.update(i for i in dups if i is not None)
    checks.append(Check('sem_duplicatas', PESOS['sem_duplicatas'], not dups,
                        f'{len(dups)} linhas idênticas', dups))

    # ── 5. Data de fallback ───────────────────────────────────────────────
    fallback = [t.get('linha_idx') for t in txns if t.get('data_fallback')]
    suspeitas.update(i for i in fallback if i is not None)
    checks.append(Check('sem_data_fallback', PESOS['sem_data_fallback'], not fallback,
                        f'{len(fallback)} datas não parseadas', fallback))

    # ── 6. Valores zero ───────────────────────────────────────────────────
    zeros = [t.get('linha_idx') for t in txns
             if t.get('valor_original') in (None, 0, 0.0)]
    suspeitas.update(i for i in zeros if i is not None)
    checks.append(Check('sem_valor_zero', PESOS['sem_valor_zero'], not zeros,
                        f'{len(zeros)} valores nulos', zeros))

    # ── Score ─────────────────────────────────────────────────────────────
    peso_total = sum(c.peso for c in checks) or 1
    obtido = sum(c.peso for c in checks if c.passou)
    score = round(100 * obtido / peso_total)

    return Resultado(score, checks, sorted(i for i in suspeitas if i is not None))


def infer_dayfirst(strings_de_data, pais=None):
    """PT e BR são dayfirst. Só devolve False com PROVA (componente > 12)."""
    import re
    primeiro_maior_12 = False
    segundo_maior_12 = False
    for s in strings_de_data:
        m = re.match(r'^\s*(\d{1,2})[/.\-](\d{1,2})', str(s))
        if not m:
            continue
        a, b = int(m.group(1)), int(m.group(2))
        if a > 12:
            primeiro_maior_12 = True
        if b > 12:
            segundo_maior_12 = True
    if primeiro_maior_12 and not segundo_maior_12:
        return True
    if segundo_maior_12 and not primeiro_maior_12:
        return False
    return True


def contar_linhas_com_data(texto_bruto):
    import re
    padrao = re.compile(r'\d{1,2}[/.\-]\d{1,2}([/.\-]\d{2,4})?')
    total = 0
    for linha in (texto_bruto or '').split('\n'):
        if padrao.search(linha):
            total += 1
    return total


def contexto_do_arquivo(filepath):
    """Extrai do arquivo bruto o que o validador precisa.

    Devolve dict com `linhas_com_data_no_bruto` (e `saldo_inicial`/`saldo_final`
    quando encontráveis por âncora). Mantido simples de propósito — o fast path e
    o executor suprem o resto.
    """
    ext = filepath.lower().rsplit('.', 1)[-1]
    texto = ''
    try:
        if ext == 'pdf':
            import pdfplumber
            with pdfplumber.open(filepath) as pdf:
                texto = '\n'.join((p.extract_text() or '') for p in pdf.pages)
        else:
            import pandas as pd
            if ext == 'csv':
                df = pd.read_csv(filepath, sep=None, engine='python', header=None, nrows=40)
            else:
                df = pd.read_excel(filepath, header=None, nrows=40)
            texto = '\n'.join(' '.join('' if pd.isna(v) else str(v) for v in row)
                              for row in df.values.tolist())
    except Exception:
        texto = ''
    return {'linhas_com_data_no_bruto': contar_linhas_com_data(texto)}
