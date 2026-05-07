# Skill: Criar Relatório Dinâmico com Múltiplas Moedas

**Objetivo:** Criar relatórios dinâmicos customizados onde o usuário pode escolher tabelas, campos, agrupadores e visualizar colunas mensais em diferentes moedas de lançamento.

---

## Fase 1: Definição da Estrutura do Relatório 🎯

**Objetivo:** Entender quais dados o usuário quer analisar e como quer visualizá-los.

- [ ] **Selecionar Tabelas Fonte:** Quais tabelas devem ser incluídas no relatório?
  - despesas_mensais (lançamentos com valor_original, moeda, cambio_eur, valor_eur, categoria_final, etc.)
  - receitas_mensais (receitas com valor_original, moeda_original, cotacao, valor_eur, valor_brl, etc.)
  - lcto_impostos (impostos com tp_imposto, valor_faturado, moeda_faturado, valor_imposto, etc.)
  - lcto_emprestimos (empréstimos com tipo, beneficiario, valor_operacao, moeda_emp, etc.)
  - lcto_investimentos (investimentos com banco, tp_investimento, valor_inv, moeda, valor_atual, etc.)

- [ ] **Selecionar Campos a Exibir:** Quais colunas devem aparecer no relatório?
  - Para cada tabela: listar campos disponíveis e permitir seleção múltipla

- [ ] **Definir Agrupadores (GROUP BY):** Por qual campo os dados serão agrupados?
  - Exemplos: categoria_final, tp_investimento, tp_imposto, tipo_receita, banco, beneficiario, mês/ano
  - Os agrupadores devem ser exibidos na primeira coluna e os valores por periodo permitindo a soma por agrupador por total (Total do Ano)
  - Agrupadores deverão ter colunas separadas por moeda registrada e com label da moeda.
  

- [ ] **Definir Período:** Quais meses devem ser incluídos?
  - Range: mês inicial até mês final (ex: 2025-01 até 2025-12)

- [ ] **Definir Moedas de Exibição:** Quais moedas devem ser exibidas nas colunas?
  - EUR (padrão), BRL, USD, GBP, etc.
  - Mostrar tanto valor original quanto convertido

---

## Fase 2: Especificação Técnica ⚙️

**Objetivo:** Transformar as escolhas em uma especificação executável.

### 2.1 API de Relatórios Dinâmicos

**Rota:** `POST /api/relatorio_dinamico`

**Parâmetros de Entrada:**
```json
{
  "tabelas": ["despesas_mensais", "receitas_mensais"],
  "campos": ["categoria_final", "valor_eur", "moeda"],
  "agrupador": "categoria_final",
  "mes_inicio": "2025-01",
  "mes_fim": "2025-12",
  "moedas_exibicao": ["EUR", "BRL"]
}
```

**Estrutura de Retorno:**
```json
{
  "agrupadores": [
    {
      "nome": "Alimentação",
      "meses": {
        "2025-01": { "EUR": 150.00, "BRL": 825.00 },
        "2025-02": { "EUR": 180.00, "BRL": 990.00 }
      }
    }
  ],
  "total_por_mes": {
    "2025-01": { "EUR": 5000.00, "BRL": 27500.00 },
    "2025-02": { "EUR": 5200.00, "BRL": 28600.00 }
  }
}
```

### 2.2 Tabela de Configuração de Relatórios

**Tabela:** `relatorios_configurados`
```sql
CREATE TABLE relatorios_configurados (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_email TEXT,
  nome_relatorio TEXT,
  tabelas TEXT, -- JSON array de tabelas
  campos TEXT,  -- JSON array de campos
  agrupador TEXT,
  mes_inicio TEXT,
  mes_fim TEXT,
  moedas TEXT, -- JSON array de moedas
  criado_em TEXT DEFAULT CURRENT_TIMESTAMP
);
```

---

## Fase 3: Interface de Criação do Relatório 🖥️

**Objetivo:** Criar a tela para o usuário configurar e gerar relatórios customizados.

### 3.1 local na UI (App Relatórios)
- Adicionar novo botão "Criar Relatório Dinâmico" na área de Relatórios
- Modal/step-by-step para configuração

### 3.2 Fluxo de Criação

**Step 1: Seleção de Tabelas**
- Checkboxes para cada tabela disponível
- Preview dos campos de cada tabela ao selecionar

**Step 2: Seleção de Campos**
- Listar campos da tabela(s) selecionada(s)
- Permitir selecionar múltiplos campos

**Step 3: Escolha do Agrupador**
- Dropdown com campos que servem para agrupamento
- Garantir que o agrupador faça sentido com as tabelas

**Step 4: Período**
- Seletor de mês inicial e mês final
- Listar meses disponíveis baseado nos dados existentes

**Step 5: Moedas de Exibição**
- Checkboxes para cada moeda (EUR, BRL, USD, GBP, etc.)
- Pelo menos uma moeda deve ser selecionada

**Step 6: Salvar e Gerar**
- Nome do relatório
- Salvar configuração para uso futuro
- Gerar visualização inmediata

---

## Fase 4: Implementação 💻

**Objetivo:** Desenvolver a solução completa.

- [ ] Adicionar tabela `relatorios_configurados` no banco
- [ ] Criar função `get_relatorio_dinamico()` no database.py
- [ ] Criar rota `POST /api/relatorio_dinamico` no app.py
- [ ] Criar seção "Relatório Dinâmico" no HTML
- [ ] Implementar UI de criação step-by-step
- [ ] Implementar visualização em formato de tabela/cards
- [ ] Suporte para múltiplas moedas por coluna mensal

---

## Fase 5: Validação e Ajustes ✅

**Objetivo:** Garantir que o relatório funciona corretamente.

- [ ] Testar com diferentes combinações de tabelas
- [ ] Verificar cálculos de conversão de moedas
- [ ] Validar agrupamentos corretos
- [ ] Testar período com dados existentes
- [ ] Ajustar layout para visualização clara

---

### 🤖 Como usar esta Skill

Para criar um novo relatório dinâmico, inicie a conversa dizendo:

> *"Quero criar um relatório dinâmico. Vou usar a **Skill de Relatório Dinâmico**. Vamos começar definindo as tabelas fonte e os campos que preciso analizar."*