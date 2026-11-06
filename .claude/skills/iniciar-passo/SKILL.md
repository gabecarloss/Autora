---
name: iniciar-passo
description: Começa um passo da ordem de construção (BRIEFING.md seção 13) do jeito combinado com o usuário — retoma estado e pendências, lê as seções do briefing do passo, checa bibliotecas e entra em modo de plano. Use quando o usuário disser "vamos ao passo N", "/iniciar-passo N" ou pedir para começar o próximo passo.
argument-hint: "[número do passo]"
---

# Iniciar o passo $ARGUMENTS

Forma de trabalho decidida com o usuário: **um plano por passo**, e o plano cobre só
aquele passo. Nada de código antes do plano aprovado.

## 1. Retomar o estado
- Leia a seção "Estado do projeto" do `CLAUDE.md`.
- Leia a memória do passo anterior (`passo-<N-1>-concluido`), em especial as
  **pendências**: elas vêm antes do passo novo, ou entram no plano.
- Se o número não foi informado, use o "Próximo" do estado do projeto e confirme.
- Confira se o passo anterior foi commitado: `git status` e `git log -3 --oneline`
  (só leitura). Se houver muito trabalho não commitado, avise o usuário antes de
  seguir; quem commita é ele.

## 2. Ler o que o passo exige
- `BRIEFING.md`: a seção 13 (o passo e os vizinhos) e todas as seções que o passo
  cita ou implica. Leia por inteiro as seções relevantes; não resuma de memória.
- `GLOSSARIO.md` se o passo tiver interface.
- Para varreduras amplas no código, use o subagente `Explore`.

## 3. Bibliotecas e especificações
- Abra `bibliotecas.md` (nesta pasta) e veja as candidatas do passo.
- Para cada dependência nova que o passo pede (inclusive as do catálogo), acione o
  subagente `pesquisador-tecnico` **antes** de propor no plano. Ele checa
  manutenção, licença para uso comercial, Windows/Python 3.11 e custo. Pode rodar
  vários em paralelo.
- Toda dependência nova é **perguntada ao usuário** (briefing 15.4), com o resumo
  do pesquisador. Serviço pago só se o usuário habilitar (CLAUDE.md).

## 4. Ferramentas que o passo vai precisar
- Veja em `CLAUDE.md` → "Ferramentas do Claude Code" se há subagente ou skill
  marcada "criar no passo N". Se houver, ela entra no plano (criada a partir do
  primeiro código real do passo).

## 5. Planejar
- Entre em modo de plano. O plano tem: contexto, o que entra e o que fica de fora,
  arquivos, testes (quem escreve: considere o subagente `escritor-de-testes`),
  pontos "provisório" e como verificar.
- Decisões que o briefing não cobre: pergunte ao usuário (AskUserQuestion), não
  assuma.
