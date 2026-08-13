import json
import os
import re
import tempfile

import pytest

from modules.extratos import anonymizer, fingerprint, validator, recipes


# ─────────────────────────────────────────────────────────────────────────────
# anonimizador (bloqueante)
# ─────────────────────────────────────────────────────────────────────────────

def test_mask_substitui_digitos_e_letras():
    assert anonymizer.mask('1.234,56') == '9.999,99'
    assert anonymizer.mask('05/03/2026') == '99/99/9999'
    assert anonymizer.mask('TRANSFERENCIA JOAO SILVA') == 'XXXXXXXXXXXXX XXXX XXXXX'


def _conteudo_serializado(sample):
    """Serializa apenas o CONTEÚDO (linhas mascaradas), ignorando metadados
    estruturais (n_colunas, largura, x0/x1) que carregam números reais.
    """
    partes = [json.dumps(sample.get('linhas', []), ensure_ascii=False),
              json.dumps(sample.get('linhas_cabecalho_candidatas', []), ensure_ascii=False)]
    return '\n'.join(partes)


def test_amostra_nao_contem_digito_diferente_de_9():
    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
        f.close()
        try:
            import pandas as pd
            df = pd.DataFrame([
                ['Data', 'Descrição', 'IBAN', 'Valor'],
                ['05/03/2026', 'TRF JOAO SILVA', 'PT50000000000000000000000', '42,30'],
                ['06/03/2026', 'joao.silva@email.com', '123456789', '15,00'],
            ])
            df.to_excel(f.name, header=False, index=False)
            sample = anonymizer.build_sample(f.name)
            texto = _conteudo_serializado(sample)
            encontrados = re.findall(r'[0-8]', texto)
            assert not encontrados, f'dígito não mascarado na amostra: {encontrados[:5]}'
        finally:
            os.unlink(f.name)


def test_amostra_nao_contem_pii_conhecida():
    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
        f.close()
        try:
            import pandas as pd
            df = pd.DataFrame([
                ['Data', 'Descrição', 'IBAN', 'NIF', 'Valor'],
                ['05/03/2026', 'JOAO SILVA', 'PT50000000000000000000000', '123456789', '42,30'],
                ['06/03/2026', 'joao@empresa.pt', 'PT50000000000000000000000', '987654321', '15,00'],
            ])
            df.to_excel(f.name, header=False, index=False)
            sample = anonymizer.build_sample(f.name)
            texto = _conteudo_serializado(sample)
            for termo in ('JOAO', 'SILVA', 'PT50', 'joao@'):
                assert termo not in texto.upper(), f'{termo!r} vazou na amostra'
            # Invariante forte: nenhum dígito 0-8 sobrevive — logo nenhum
            # IBAN/NIF/CPF (que contêm dígitos 0-8) pode vazar.
            assert not re.findall(r'[0-8]', texto)
        finally:
            os.unlink(f.name)


# ─────────────────────────────────────────────────────────────────────────────
# validador
# ─────────────────────────────────────────────────────────────────────────────

def test_validador_saldo_encadeado_passa():
    txns = [
        {'linha_idx': 0, 'data': '2026-03-05', 'descricao': 'A', 'valor_original': 42.30, 'is_debit': False, 'saldo': 1284.55},
        {'linha_idx': 1, 'data': '2026-03-06', 'descricao': 'B', 'valor_original': 15.00, 'is_debit': True, 'saldo': 1269.55},
        {'linha_idx': 2, 'data': '2026-03-07', 'descricao': 'C', 'valor_original': 10.00, 'is_debit': True, 'saldo': 1259.55},
    ]
    res = validator.validate(txns)
    assert res.score == 100


def test_validador_aponta_linha_adulterada():
    txns = [
        {'linha_idx': 0, 'data': '2026-03-05', 'descricao': 'A', 'valor_original': 42.30, 'is_debit': False, 'saldo': 1284.55},
        {'linha_idx': 1, 'data': '2026-03-06', 'descricao': 'B', 'valor_original': 15.00, 'is_debit': True, 'saldo': 9999.00},
    ]
    res = validator.validate(txns)
    assert 1 in res.linhas_suspeitas


def test_validador_data_fallback_suspeita():
    txns = [
        {'linha_idx': 0, 'data': None, 'descricao': 'A', 'valor_original': 10.0, 'is_debit': True,
         'saldo': None, 'data_fallback': True},
    ]
    res = validator.validate(txns)
    assert 0 in res.linhas_suspeitas


def test_infer_dayfirst():
    assert validator.infer_dayfirst(['15/03/2026']) is True
    assert validator.infer_dayfirst(['03/15/2026']) is False


# ─────────────────────────────────────────────────────────────────────────────
# recipes
# ─────────────────────────────────────────────────────────────────────────────

def _csv(conteudo):
    f = tempfile.NamedTemporaryFile(suffix='.csv', delete=False, mode='w')
    f.write(conteudo)
    f.close()
    return f.name


def test_recipe_planilha():
    p = _csv('Data;Descricao;Debito;Credito;Saldo\n'
             '05/03/2026;TRF MB WAY;;42,30;1284,55\n'
             '06/03/2026;COMPRA;15,00;;1269,55\n')
    try:
        spec = {'estrategia': 'planilha', 'header_row': 0,
                'colunas': {'data': 'Data', 'descricao': 'Descricao',
                            'debito': 'Debito', 'credito': 'Credito', 'saldo': 'Saldo'},
                'moeda': 'EUR', 'sinal': 'colunas_separadas'}
        txns = recipes.apply(spec, p)
        assert len(txns) == 2
        assert txns[0]['valor_original'] == 42.30 and not txns[0]['is_debit']
        assert txns[1]['valor_original'] == 15.00 and txns[1]['is_debit']
    finally:
        os.unlink(p)


def test_recipe_sem_linhas_levanta():
    from modules.extratos.errors import ReceitaFalhou
    p = _csv('col1;col2\nx;y\n')
    try:
        spec = {'estrategia': 'planilha', 'header_row': 0,
                'colunas': {'data': 'col1', 'descricao': 'col2'}, 'sinal': 'colunas_separadas'}
        with pytest.raises(ReceitaFalhou):
            recipes.apply(spec, p)
    finally:
        os.unlink(p)


# ─────────────────────────────────────────────────────────────────────────────
# fingerprint
# ─────────────────────────────────────────────────────────────────────────────

def test_fingerprint_tabular_estavel_e_distinto():
    a = _csv('Data;Descricao;Valor\n05/03/2026;A;10,00\n')
    b = _csv('Data;Descricao;Valor\n06/04/2026;B;20,00\n')
    c = _csv('Data;Historico;Montante\n05/03/2026;A;10,00\n')
    try:
        fp_a, _ = fingerprint.compute(a, header_cells=['Data', 'Descricao', 'Valor'], n_colunas=3)
        fp_b, _ = fingerprint.compute(b, header_cells=['Data', 'Descricao', 'Valor'], n_colunas=3)
        fp_c, _ = fingerprint.compute(c, header_cells=['Data', 'Historico', 'Montante'], n_colunas=3)
        assert fp_a == fp_b
        assert fp_a != fp_c
    finally:
        for f in (a, b, c):
            os.unlink(f)
