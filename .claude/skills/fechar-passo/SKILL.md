---
name: fechar-passo
description: Fecha um passo da ordem de construção do jeito combinado com o usuário — verificação completa, auditoria de conformidade, revisão, resumo, mensagem de commit pronta, memória e estado do projeto atualizados, próximo passo. Use quando o trabalho de um passo terminar, ou quando o usuário disser "/fechar-passo N" ou "fecha o passo".
argument-hint: "[número do passo]"
---

# Fechar o passo $ARGUMENTS

Regra do usuário: **você nunca commita nem altera o repositório** sem pedido explícito
dele. Aqui você entrega a mensagem de commit pronta; quem commita é o usuário.

## 1. Checagens (em paralelo, como subagentes)
- `verificador`: lint, tipos, camadas, dependências, testes com cobertura, front e
  pre-commit.
- `conformidade`: o diff do passo contra as decisões fixas do CLAUDE.md.
Corrija o que falhar e rode de novo até `TUDO VERDE` e `CONFORME`. Violação que
exigiria mudar uma decisão vai para o usuário, não é "corrigida" por conta própria.

## 2. Revisões prontas do Claude Code
- `/code-review` sobre o diff do passo (bugs).
- `/simplify` (limpeza), aplicando só o que não muda comportamento.
- `/security-review` **obrigatório** se o passo mexeu em segredos, servidor local
  (`api/`), conexão do agente, exportar/importar, ou em qualquer coisa que receba
  dado de fora.

## 3. Levantar pendências
- Provisórios: ferramenta Grep com `provis[oó]rio` (sem diferenciar maiúsculas) em
  `src`, `frontend/src`, `pyproject.toml` e `.claude/` (liste todos, novos e antigos).
- O que o plano previa e não foi feito.
- O que depende do usuário (testes manuais, login, decisões).

## 4. Entregar ao usuário (nesta ordem)
1. **Resumo**: o que foi feito, o que ficou pendente e como verificar (comandos e
   o que olhar no app).
2. **Mensagem de commit pronta**, em bloco de código:
   título curto no imperativo (até ~60 caracteres) + corpo com o que e o porquê +
   linha de coautoria `Co-Authored-By: Claude <noreply@anthropic.com>` (use a
   linha de atribuição indicada pelo sistema, se houver).
3. **Provisórios** listados, para o usuário confirmar ou decidir.
4. **Próximo passo**, segundo a seção 13 do BRIEFING.md.

## 5. Atualizar o estado (arquivos, não o git)
- Memória: crie `passo-N-concluido.md` (tipo project: feito, pendências, Why/How to
  apply) e a linha no `MEMORY.md`.
- `CLAUDE.md` → "Estado do projeto": a linha "Passo N concluído (data). Próximo:
  ..." e o que mudou em Pilha, Comandos e "Onde fica o quê". Mantenha curto.
- Se o passo criou subagente ou skill (ou se uma sequência se repetiu pela terceira
  vez), atualize a lista em "Ferramentas do Claude Code".
- Piso de cobertura (`fail_under` em `[tool.coverage.report]` do `pyproject.toml`):
  suba até a cobertura total atual, arredondada para baixo. **Nunca abaixe** o piso;
  se a cobertura caiu, escreva os testes que faltam.

## 6. Depois do push (só se o usuário pedir ou disser que fez o push)
- `gh run list --limit 3` e `gh run watch <id>` para acompanhar a CI. Se falhar, traga
  só o erro essencial (ou use o `verificador`).
