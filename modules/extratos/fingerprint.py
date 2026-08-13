import hashlib
import os
import re
import unicodedata

from .errors import ArquivoIlegivel

_ALPHA = re.compile(r'[^\W\d_]{3,}', re.UNICODE)
_STOPWORDS = {
    'janeiro', 'fevereiro', 'marco', 'abril', 'maio', 'junho', 'julho', 'agosto',
    'setembro', 'outubro', 'novembro', 'dezembro', 'jan', 'fev', 'mar', 'abr', 'mai',
    'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez',
    'segunda', 'terca', 'quarta', 'quinta', 'sexta', 'sabado', 'domingo',
}
MAX_TOKENS = 40


def _norm(token):
    t = unicodedata.normalize('NFKD', token.lower())
    return ''.join(c for c in t if not unicodedata.combining(c))


def _tokens(texto):
    out = set()
    for m in _ALPHA.finditer(texto or ''):
        t = _norm(m.group())
        if t and t not in _STOPWORDS:
            out.add(t)
    return out


def _hash(partes):
    h = hashlib.sha256()
    for p in partes:
        h.update(p.encode('utf-8', errors='ignore'))
        h.update(b'\x00')
    return h.hexdigest()[:16]


def _fingerprint_pdf(filepath):
    import pdfplumber
    with pdfplumber.open(filepath) as pdf:
        producer = (pdf.metadata or {}).get('Producer') or ''
        creator = (pdf.metadata or {}).get('Creator') or ''

        textos = [p.extract_text() or '' for p in pdf.pages]
        if not any(textos):
            raise ArquivoIlegivel('PDF sem camada de texto (provável digitalização).')

        if len(textos) >= 2:
            estaveis = _tokens(textos[0])
            for t in textos[1:]:
                estaveis &= _tokens(t)
        else:
            estaveis = set()

        if len(estaveis) < 5:
            contagem = {}
            for t in textos:
                for m in _ALPHA.finditer(t):
                    tok = _norm(m.group())
                    if tok and tok not in _STOPWORDS:
                        contagem[tok] = contagem.get(tok, 0) + 1
            estaveis = {t for t, n in contagem.items() if n >= 2}

        tokens = sorted(estaveis)[:MAX_TOKENS]
        return _hash(['pdf', _norm(producer), _norm(creator), *tokens]), {
            'formato': 'pdf',
            'producer': producer,
            'tokens': tokens,
            'paginas': len(pdf.pages),
        }


def _fingerprint_tabular(filepath, header_cells, n_colunas):
    tokens = sorted({_norm(c) for c in header_cells if c and _ALPHA.search(str(c))})
    tokens = tokens[:MAX_TOKENS]
    return _hash(['tabular', str(n_colunas), *tokens]), {
        'formato': 'tabular',
        'tokens': tokens,
        'n_colunas': n_colunas,
    }


def compute(filepath, header_cells=None, n_colunas=None):
    ext = os.path.splitext(filepath)[1].lower()
    if ext == '.pdf':
        return _fingerprint_pdf(filepath)
    return _fingerprint_tabular(filepath, header_cells or [], n_colunas or 0)
