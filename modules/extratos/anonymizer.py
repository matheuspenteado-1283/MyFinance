import re

_PRESERVAR = {
    'R$', 'US$', 'EUR', 'USD', 'BRL', 'GBP', '€', '$', '£',
    'D', 'C', 'DEB', 'CRED',
}
_DIGITO = re.compile(r'\d')
_ALPHA_RUN = re.compile(r'[^\W\d_]+', re.UNICODE)

# Padrões de PII a descartar das linhas de cabeçalho antes de enviar ao LLM.
_PII = [
    re.compile(r'[A-Z]{2}\d{2}[A-Z0-9]{11,30}'),        # IBAN
    re.compile(r'\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b'),    # CPF
    re.compile(r'\b\d{9}\b'),                            # NIF
    re.compile(r'[\w.+-]+@[\w-]+\.[\w.]+'),              # e-mail
    re.compile(r'\d{8,}'),                               # sequência longa de dígitos
]


def _contem_pii(celula):
    s = str(celula)
    for padrao in _PII:
        if padrao.search(s):
            return True
    return False


def mask(texto):
    if texto is None:
        return ''
    s = str(texto)
    if s.strip().upper() in _PRESERVAR:
        return s

    def _sub_alpha(m):
        return 'X' * len(m.group())

    s = _ALPHA_RUN.sub(_sub_alpha, s)
    s = _DIGITO.sub('9', s)
    return s


def build_sample(filepath, max_linhas=6):
    ext = filepath.lower().rsplit('.', 1)[-1]
    if ext == 'pdf':
        return _sample_pdf(filepath, max_linhas)
    return _sample_tabular(filepath, max_linhas)


def _sample_tabular(filepath, max_linhas):
    import pandas as pd
    df = pd.read_csv(filepath, sep=None, engine='python', header=None, nrows=40) \
        if filepath.lower().endswith('.csv') \
        else pd.read_excel(filepath, header=None, nrows=40)

    linhas = [[('' if pd.isna(v) else str(v)) for v in row] for row in df.values.tolist()]

    # Só o CABEÇALHO (primeira linha) vai em claro, e apenas células que são
    # rótulos (sem dígitos) e passam no filtro de PII. Linhas de dados e qualquer
    # célula com dígito/PII vão mascaradas — nunca deixar nome/IBAN/titular vazar.
    cabecalho = []
    if linhas:
        primeira = linhas[0]
        cabecalho.append([
            c if (c and not _contem_pii(c) and not re.search(r'\d', c) and len(c) <= 40)
            else mask(c)
            for c in primeira
        ])

    return {
        'formato': 'tabular',
        'linhas': [[mask(c) for c in linha] for linha in linhas[:15]],
        'linhas_cabecalho_candidatas': cabecalho,
        'n_colunas': max((len(l) for l in linhas), default=0),
    }


def _sample_pdf(filepath, max_linhas):
    import pdfplumber
    with pdfplumber.open(filepath) as pdf:
        page = pdf.pages[0]
        words = page.extract_words(use_text_flow=False)
        linhas = {}
        for w in words:
            chave = round(w['top'] / 3.0)
            linhas.setdefault(chave, []).append(w)

        saida = []
        for chave in sorted(linhas)[:25]:
            palavras = sorted(linhas[chave], key=lambda w: w['x0'])
            saida.append([
                {'t': mask(w['text']), 'x0': round(w['x0'], 1), 'x1': round(w['x1'], 1)}
                for w in palavras
            ])
        return {
            'formato': 'pdf_words',
            'largura': round(page.width, 1),
            'linhas': saida,
        }
