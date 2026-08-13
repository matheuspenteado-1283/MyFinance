"""Indução de receita por LLM — opcional, com degradação graciosa.

Se ANTHROPIC_API_KEY não estiver configurada ou a chamada falhar, `induzir()`
devolve None e o fluxo cai no mapeador manual.
"""
import json
import os
from typing import Literal, Optional

from pydantic import BaseModel

MODELO = 'claude-opus-5'
MAX_TOKENS = 8000


class ColunaMap(BaseModel):
    papel: Literal['data', 'data_valor', 'descricao', 'valor',
                   'debito', 'credito', 'saldo', 'tipo', 'ignorar']
    header: Optional[str] = None
    indice: Optional[int] = None
    x_min: Optional[float] = None
    x_max: Optional[float] = None


class ReceitaInduzida(BaseModel):
    estrategia: Literal['planilha', 'pdf_tabela', 'pdf_words', 'linhas_regex']
    banco_label: str
    pais: Literal['PT', 'BR', 'OUTRO']
    header_row: Optional[int] = None
    colunas: list[ColunaMap]
    linha_transacao_regex: Optional[str] = None
    ignorar_linhas_regex: list[str] = []
    sinal: Literal['colunas_separadas', 'valor_com_sinal', 'coluna_tipo']
    confianca: int
    observacoes: str = ''


SYSTEM = """Você mapeia a estrutura de extratos bancários de Portugal e do Brasil.

Você recebe uma AMOSTRA ANONIMIZADA: todos os dígitos foram substituídos por 9 e
todas as letras do conteúdo por X. A estrutura (posições, separadores, pontuação,
símbolos de moeda e nomes de cabeçalho) está preservada.

Sua única tarefa é identificar QUAL COLUNA É O QUÊ. Não tente ler valores, datas
ou descrições — eles foram mascarados de propósito e não são a sua tarefa.

Não infira: ordem dia/mês, separador decimal, ou moeda. Esses itens são
calculados deterministicamente pelo sistema a partir dos dados reais.

Se não conseguir identificar a estrutura com segurança, devolva confianca abaixo
de 50 e explique o motivo em observacoes."""


def induzir(sample, pais_hint=None):
    if not os.getenv('ANTHROPIC_API_KEY'):
        return None
    try:
        import anthropic
        client = anthropic.Anthropic()
        resp = client.messages.parse(
            model=MODELO,
            max_tokens=MAX_TOKENS,
            system=SYSTEM,
            messages=[{
                'role': 'user',
                'content': (
                    f'País provável: {pais_hint or "desconhecido"}\n\n'
                    f'Amostra anonimizada:\n```json\n'
                    f'{json.dumps(sample, ensure_ascii=False, indent=1)}\n```'
                ),
            }],
            output_format=ReceitaInduzida,
        )
        receita = resp.parsed_output
        if receita.confianca < 50:
            return None
        return _to_spec(receita)
    except Exception as e:
        import sys
        print(f'[induction] falhou: {type(e).__name__}: {e}', file=sys.stderr)
        return None


def _to_spec(r):
    spec = {
        'estrategia': r.estrategia,
        'sinal': r.sinal,
        'ignorar_linhas_regex': r.ignorar_linhas_regex,
        'moeda': None,
        'dayfirst': None,
        'decimal': None,
    }
    if r.header_row is not None:
        spec['header_row'] = r.header_row
    if r.linha_transacao_regex:
        spec['linha_transacao_regex'] = r.linha_transacao_regex

    if r.estrategia == 'pdf_words':
        spec['faixas_x'] = {
            c.papel: [c.x_min, c.x_max]
            for c in r.colunas
            if c.papel != 'ignorar' and c.x_min is not None
        }
    else:
        por_nome = {c.papel: c.header for c in r.colunas
                    if c.papel != 'ignorar' and c.header}
        por_idx = {c.papel: c.indice for c in r.colunas
                   if c.papel != 'ignorar' and c.indice is not None}
        if por_nome:
            spec['colunas'] = por_nome
        if por_idx:
            spec['colunas_idx'] = por_idx
    return spec
