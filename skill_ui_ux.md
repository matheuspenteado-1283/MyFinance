# Skill: Processo de Design de UI/UX

**Objetivo:** Criar interfaces de usuário (UI) visualmente impressionantes e experiências (UX) fluidas, focando na usabilidade, facilidade de navegação e em um design premium.

---

## Fase 1: Empatia e Pesquisa (UX) 🔍
**Objetivo:** Entender profundamente o usuário e o contexto de uso antes de desenhar a primeira linha.
- [ ] **Definição do Usuário Final:** Quem vai utilizar a tela? (Ex: Administrador do sistema, cliente final no celular, equipe de vendas).
- [ ] **Mapeamento de Tarefas:** Quais são as 3 ações essenciais que o usuário precisa fazer nesta interface?
- [ ] **Busca de Referências:** Coletar ideias visuais e funcionais de outros sistemas modernos e bem desenhados.
- [ ] **Identificação de Fricções:** O que geralmente irrita o usuário em sistemas semelhantes? (Ex: formulários confusos, falta de feedback claro).

## Fase 2: Arquitetura e Wireframes 🏗️
**Objetivo:** Estruturar a lógica da informação e o fluxo, priorizando a organização antes da estética.
- [ ] **Fluxo de Navegação (User Flow):** Mapear o passo a passo (Ex: Login -> Dashboard -> Modal de Cadastro -> Mensagem de Sucesso).
- [ ] **Esqueleto da Tela (Wireframe):** Desenhar blocos simples determinando onde ficam menus, títulos, botões principais e listas.
- [ ] **Hierarquia Visual:** Definir qual é a informação mais importante e garantir que ela tenha maior destaque visual (tamanho, posição no topo).

## Fase 3: Design de Interface - UI Visual 🎨
**Objetivo:** Aplicar identidade visual, estética moderna e coerência para criar uma experiência premium.
- [ ] **Paleta de Cores:** Definir Cores Primárias (ações principais), Cores de Feedback (Verde/Sucesso, Vermelho/Erro) e Cores Neutras (tons de cinza para fundos e textos).
- [ ] **Tipografia:** Escolher fontes limpas e legíveis (ex: Inter, Roboto). Criar uma escala de tamanhos para Títulos (H1, H2) e parágrafos normais.
- [ ] **Padronização de Componentes:** Definir o visual padrão para Botões (Principal, Secundário, Texto), Campos de Formulário (Inputs) e Cards.
- [ ] **Respiro Visual (White Space):** Aplicar margens e espaçamentos (paddings) generosos e padronizados para evitar que a tela fique poluída e confusa.

- **Padrões de Botões:** Criar padrão de botões com a following características:
    - Botão de Ação Principal (Azul, com texto branco, arredondado)
    - Botão de Ação Secundária (Branco, com texto azul, arredondado)
    - Botão de Ação Terciária (Azul claro, com texto branco, arredondado)
    - Botão de Ação Quaternária (Azul escuro, com texto branco, arredondado) - Tamanho médio. Nunca ocupar a tela inteira
    - Botão de Ação Quintanária (Branco com texto azul, arredondado) - Tamanho médio. Nunca ocupar a tela inteira
    - Aplicar espaço entre botões para não ficarem colados.
    - Tamanho do botão:
 - Classe: btn-sm
- min-width: 140px
- padding: 10px 20px
- font-size: 14px
- border-radius: 8px
    

- **Padrões de Inputs:** Criar padrão de inputs com a following características:
    - Input Padrão (Azul, com texto branco, arredondado)
    - Input Secundário (Branco, com texto azul, arredondado)
    - Input Terciário (Azul claro, com texto branco, arredondado)
    - Input Quaternário (Azul escuro, com texto branco, arredondado) - Tamanho médio. Nunca ocupar a tela inteira
    - Input Quintanário (Branco com texto azul, arredondado) - Tamanho médio. Nunca ocupar a tela inteira
    - Formularios alinhados 
    
## Fase 4: Interações e Dinamismo ✨
**Objetivo:** Tornar a interface viva, oferecendo feedback constante para o usuário.
- [ ] **Estados Interativos:** Definir visualmente o que acontece quando o mouse passa sobre um botão (Hover), quando ele é clicado (Active) ou quando um campo está focado (Focus).
- [ ] **Micro-animações:** Adicionar transições suaves (ex: um modal que sobe suavemente ao invés de aparecer de forma brusca).
- [ ] **Feedback de Sistema:** Criar alertas visuais claros (Ex: "Salvando...", "Cadastro realizado com sucesso!", "Erro na senha").
- [ ] **Responsividade:** Garantir que o design se adapte perfeitamente e os elementos não quebrem em telas de celular, tablet e desktop.

## Fase 5: Teste e Validação 🧪
**Objetivo:** Confirmar se o design atinge o objetivo de forma fácil e intuitiva.
- [ ] **Teste de Navegação Real:** Clicar pelo fluxo imaginando ser o usuário. Há algo confuso ou escondido?
- [ ] **Contraste e Acessibilidade:** As cores do texto em relação ao fundo têm bom contraste para leitura?
- [ ] **Alinhamento e Padronização:** Os botões estão todos do mesmo tamanho? Os alinhamentos estão corretos?
- [ ] **Refinamento Final:** Ajustar os detalhes finais com base na auto-revisão antes de entregar para desenvolvimento em código (HTML/CSS).

---

### 🤖 Como usar esta Skill com a Inteligência Artificial

Sempre que precisar idealizar o design de uma nova tela, atualizar o visual de algo existente ou pensar em regras de experiência do usuário, use este texto:

> *"Preciso criar a interface visual e o fluxo para um(a) [NOME DA TELA/SISTEMA]. Vamos utilizar nossa **Skill de UI/UX**. Comece pela **Fase 1**, me ajudando a definir quem é o usuário e qual será a estrutura básica."*
