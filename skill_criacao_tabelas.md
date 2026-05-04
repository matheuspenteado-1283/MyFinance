# Skill: Processo de Criação e Modelagem de Tabelas

**Objetivo:** Estruturar bancos de dados de forma lógica, escalável e segura, garantindo que as informações do sistema sejam armazenadas corretamente, sem redundâncias e prontas para alta performance.

---

## Fase 1: Levantamento de Entidades (O "Que") 🗂️
**Objetivo:** Identificar quais são os "objetos" ou "conceitos" do mundo real que o sistema precisa guardar.
- [ ] **Mapeamento Principal:** Quais são as peças centrais do sistema? (Ex: Usuário, Despesa, Categoria, Conta Bancária).
- [ ] **Escopo de Dados:** O que precisamos saber sobre cada entidade? (Ex: Para "Despesa", precisamos do Valor, Data, Descrição e se foi Paga).
- [ ] **Foco no Essencial:** O que NÃO precisamos armazenar agora? (Evitar criar tabelas ou colunas "para o futuro" sem necessidade imediata).

## Fase 2: Tipagem e Restrições (Colunas) 🔠
**Objetivo:** Definir com exatidão o formato de cada informação para evitar a entrada de dados incorretos ou "sujos".
- [ ] **Chaves Primárias (PK):** Toda tabela deve ter um identificador único de controle (Ex: `id` do tipo Inteiro Auto-incremental ou UUID).
- [ ] **Tipos de Dados Corretos:** 
  - Textos curtos ou longos: `VARCHAR` ou `TEXT`.
  - Números e Valores: `INTEGER` (números inteiros) ou `DECIMAL`/`FLOAT` (dinheiro e valores quebrados).
  - Datas e Horas: `DATE`, `DATETIME` ou `TIMESTAMP`.
  - Verdadeiro/Falso: `BOOLEAN` (Ex: `is_pago`, `ativo`).
- [ ] **Regras (Constraints):**
  - O campo é obrigatório? Adicionar regra de `NOT NULL`.
  - O valor não pode se repetir? Adicionar `UNIQUE` (Ex: E-mail não pode ter duplicidade).
  - Qual o valor se a pessoa não preencher? Adicionar `DEFAULT` (Ex: o padrão de "pago" pode ser "falso").

## Fase 3: Relacionamentos (As "Pontes") 🔗
**Objetivo:** Conectar as tabelas para que os dados do banco conversem entre si de forma estruturada.
- [ ] **Chaves Estrangeiras (FK):** Adicionar colunas que referenciam o ID de outra tabela (Ex: Na tabela `Despesa`, ter a coluna `categoria_id`).
- [ ] **Definição de Cardinalidade:**
  - **1 para 1 (1:1):** (Ex: Um Usuário tem apenas um Perfil_Detalhado).
  - **1 para Muitos (1:N):** (Ex: Uma Categoria possui Várias Despesas. O ID da Categoria vai na tabela da Despesa).
  - **Muitos para Muitos (N:M):** (Ex: Uma Compra pode ter Vários Produtos e um Produto pode estar em Várias Compras. Exige criar uma Tabela Intermediária de ligação).
- [ ] **Ações em Cascata:** O que acontece se o registro principal for deletado? (Ex: Se deletar a Categoria, as despesas dela devem ser deletadas ou ficar "sem categoria"?).

## Fase 4: Normalização e Performance 🧹
**Objetivo:** Otimizar as tabelas para consultas rápidas e evitar informações repetidas atoa.
- [ ] **Eliminar Repetições (Normalização):** Se você está escrevendo a mesma palavra muitas vezes em várias linhas (como "Alimentação"), isso deveria virar uma tabela própria e virar apenas um número de ID.
- [ ] **Criação de Índices:** Quais colunas serão muito usadas nas buscas, filtros ou ordenações? Criar `INDEX` para essas colunas acelera gigantescamente a velocidade do sistema (Ex: Indexar a coluna de `data` e a coluna de `status_pago`).

## Fase 5: Documentação e Script (SQL) 💾
**Objetivo:** Escrever o código real ou diagramar para que o banco seja efetivamente criado.
- [ ] **Revisão Estrutural:** A lógica faz sentido de ponta a ponta? (O Front-end vai conseguir puxar os dados fácil?).
- [ ] **Script de Criação (DDL):** Escrever o código (Ex: `CREATE TABLE...`) seguindo exatamente a modelagem das fases anteriores.
- [ ] **Dados Iniciais (Seeders):** O sistema precisa já nascer com alguns dados? (Ex: Inserir as Categorias de despesas padrões no momento em que a tabela é criada).

---

### 🤖 Como usar esta Skill com a Inteligência Artificial

Sempre que precisar estruturar o banco de dados e as tabelas para um novo módulo ou aplicativo inteiro, use o texto abaixo:

> *"Vou construir a estrutura de dados para um módulo de [NOME DO MÓDULO OU SISTEMA]. Vamos utilizar nossa **Skill de Criação de Tabelas**. Comece pela **Fase 1: Levantamento de Entidades**, me ajudando a mapear o que precisamos armazenar."*
