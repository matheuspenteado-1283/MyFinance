# ADR-001: Receitas de extrato como dado, não como código

**Data:** 2026-08-12
**Estado:** proposed
**Módulo:** `modules/extratos`
**Decisor:** Matheus Penteado
**Documento de implementação:** [`docs/extratos-v2/PLANO-IMPLEMENTACAO.md`](../../docs/extratos-v2/PLANO-IMPLEMENTACAO.md)

---

## Contexto

O parser de extratos (`modules/extratos/parser.py`, 922 linhas) implementa suporte a
cada banco como ramo condicional dentro da lógica genérica:

- `_parse_pdf_millennium()` — função dedicada ao Millennium BCP
- `parser.py:180` — heurística "débito/crédito separados sem moeda → Novo Banco PT (EUR)"
- `parser.py:196-198` — moeda inferida do **nome do arquivo** (`'nubank' in filepath` → BRL)
- `parser.py:762-780` — cascata de 3 fallbacks de PDF, tentados em ordem fixa

Consequências observadas:

1. Cada banco novo exige alteração de código + deploy, feitos pelo fundador.
2. Não existe score de confiança: `process_file()` devolve linhas ou `[]`.
   Falhas são silenciosas (`except Exception: pass` em `parser.py:699-780`).
3. Ajustar um banco pode quebrar outro — não há suite de regressão.
4. O custo marginal de suportar o enésimo banco é constante e humano.

Isto bloqueia a abertura de cadastro para novos usuários: cada cliente novo com
um banco não suportado vira um ticket de engenharia.

## Decisão

**A regra de leitura de um layout bancário passa a ser um registro em banco de dados
("receita"), interpretado por um executor genérico — não um ramo de código.**

Quatro decisões acopladas:

### D1 — Receita como dado

Uma tabela `extrato_receitas` guarda, por layout, um `spec` JSON descrevendo como
extrair transações (colunas, faixas de x, formato de data, separadores, regex de
descarte). Um executor determinístico (`recipes.py`) interpreta o `spec`.
Adicionar banco = inserir linha, não fazer deploy.

### D2 — Identificação por fingerprint de layout

A receita é localizada por hash estrutural do arquivo (cabeçalhos, texto fixo,
posições de coluna, `Producer` do PDF) — nunca pelo nome do arquivo, que é
controlado pelo usuário e não é confiável.

### D3 — IA induz a receita, nunca lê o extrato

Quando nenhuma receita casa, um LLM recebe **apenas uma amostra anonimizada**
(dígitos → `9`, texto → `X`) e propõe o mapeamento de colunas. A extração real
roda localmente, com código determinístico. Nenhum valor, nome, IBAN ou descrição
real sai do servidor.

Corolário importante: **tudo que pode ser derivado deterministicamente fica em
código, não na IA** — ordem dia/mês, separador decimal e moeda são calculados por
regra, não inferidos pelo modelo. A IA responde uma pergunta só: *qual coluna é o quê*.

### D4 — Confiança explícita e revisão obrigatória na primeira vez

Toda extração produz um score de validação (conferência de saldo, contagem de
linhas, intervalo de datas, duplicatas). A primeira importação de cada fingerprint
passa por tela de revisão obrigatória; a confirmação do usuário promove a receita
de `proposed` para `verified`. Importações seguintes daquele layout são automáticas.

## Alternativas consideradas

| Alternativa | Por que não foi escolhida agora |
|---|---|
| Continuar adicionando ramos por banco | Custo marginal constante e humano; não escala com cadastro aberto |
| LLM como extrator (lê o extrato inteiro) | Viola o requisito de privacidade; custo por importação; erro numérico silencioso e indetectável |
| Open Banking (PSD2 / Open Finance) | Resolveria a categoria inteira, mas exige parceria/certificação e credenciais bancárias. **Não descartado** — ver "Consequências / risco estratégico" |
| Exigir sempre OFX/CAMT do usuário | Nem todo banco exporta; fricção alta no onboarding. Adotado como *fast path*, não como única via |

## Consequências

### Positivas

- Banco novo é resolvido pelo **primeiro usuário que o traz**, automaticamente,
  e passa a funcionar para todos os seguintes. Custo marginal → zero.
- A biblioteca de receitas é compartilhável entre contas **por construção**: uma
  receita contém estrutura, nunca dado. Isso a torna um ativo com efeito de rede.
- Falhas deixam de ser silenciosas; passa a existir métrica de qualidade por banco.
- O executor genérico é testável com fixtures — regressão vira possível.

### Negativas / custos

- Introduz 3 tabelas novas e ~5 módulos novos em `modules/extratos/`.
- `parser.py` atual precisa ser mantido como fallback durante a transição
  (não será removido nas Fases 1-3).
- Fingerprint instável (banco muda layout) gera receita duplicada; mitigado por
  versionamento e `status = deprecated`.
- Dependência de API de LLM na Fase 4 — precisa de degradação graciosa: sem API
  disponível, o mapeador manual continua funcionando.

### Risco estratégico registrado

Se Open Banking (PSD2 em PT, Open Finance em BR) for adotado por um concorrente,
o parser vira commodity. **Revisitar esta ADR ao fim da Fase 3.** A arquitetura
de receitas não conflita com Open Banking: o agregador vira apenas mais uma
`origem` de transações, a jusante do executor.

## Regras derivadas (vinculantes)

1. Nenhuma nova condição por nome de banco em `parser.py`. Banco específico → receita.
2. Nenhuma inferência baseada em nome de arquivo.
3. Nenhum `except Exception: pass` no caminho de extração — erro é estruturado e propagado.
4. Nenhum dado real do extrato em chamada de API externa. O anonimizador é o único
   ponto de saída, e tem teste que falha o build se vazar dígito ou palavra.
