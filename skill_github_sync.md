# Skill: Sincronização e Backup no GitHub 🚀

**Objetivo:** Garantir que o projeto MyFinance esteja versionado e salvo com segurança no GitHub, permitindo o acompanhamento de mudanças e o backup do código.

---

## Fase 1: Configuração Inicial 🛠️
**Objetivo:** Preparar o ambiente local para se comunicar com o GitHub.
- [ ] **Verificar Git:** Garantir que o Git está instalado executando `git --version` no terminal.
- [ ] **Inicializar Repositório:** Se ainda não foi feito, executar `git init` na pasta raiz do projeto.
- [ ] **Configurar Identidade:** Definir seu nome e e-mail com `git config --global user.name "Seu Nome"` e `git config --global user.email "seu-email@exemplo.com"`.

## Fase 2: Conexão com o GitHub 🔗
**Objetivo:** Criar o repositório online e conectar com o local.
- [ ] **Criar Repositório no GitHub:** Acessar [github.com/new](https://github.com/new) e criar um repositório chamado `MyFinance`.
- [ ] **Adicionar Remote:** Copiar a URL do repositório (ex: `https://github.com/usuario/MyFinance.git`) e executar:
  `git remote add origin https://github.com/usuario/MyFinance.git`
- [ ] **Trocar Branch (Opcional):** Garantir que você está na branch principal com `git branch -M main`.

## Fase 3: Commit e Push (Salvar) 💾
**Objetivo:** Enviar os arquivos para a nuvem.
- [ ] **Verificar Status:** Rodar `git status` para ver o que foi alterado.
- [ ] **Adicionar Arquivos:** Executar `git add .` para preparar todos os arquivos (garanta que o `.gitignore` existe para ignorar pastas como `.venv` e `__pycache__`).
- [ ] **Criar Mensagem (Commit):** Executar `git commit -m "Explicação breve do que foi feito"`.
- [ ] **Enviar (Push):** Executar `git push -u origin main` (na primeira vez) ou apenas `git push` nas próximas.

## Fase 4: Boas Práticas de Versionamento 🌟
- [ ] **Commits Frequentes:** Não espere terminar o projeto inteiro. Salve cada funcionalidade nova concluída.
- [ ] **Mensagens Claras:** Use mensagens como "Fix: Corrigida sobreposição na tabela de revisão" ou "Feat: Adicionado módulo de impostos".
- [ ] **Uso do .gitignore:** Nunca envie o banco de dados local (`extratos.db`) ou arquivos de ambiente virtual para o GitHub se eles contiverem dados sensíveis.

---

### 🤖 Como usar esta Skill com a Inteligência Artificial

Sempre que precisar atualizar o repositório ou resolver conflitos de código, utilize este texto:

> *"Preciso salvar minhas últimas alterações no GitHub. Vamos utilizar nossa **Skill de Sincronização com GitHub**. Me guie pelos passos da **Fase 3** e verifique se há algo que eu deva ignorar no .gitignore."*
