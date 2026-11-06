---
name: atualizar-dependencias
description: Avalia e aplica atualizações de dependências (PRs do Dependabot, alertas do pip-audit/npm audit, pendências de atualização na memória) com a regra de esperar a versão amadurecer, pesquisa e verificação completa. Use quando o usuário pedir para atualizar dependências, olhar o Dependabot ou resolver uma vulnerabilidade.
---

# Atualizar dependências

Regra registrada no passo 1: **não adotar versão publicada há menos de 2 semanas**, salvo
correção de vulnerabilidade alta com exploração conhecida (aí, perguntar). E nunca
mexer no git sem pedido: PRs do Dependabot são lidos aqui, mas merge/checkout só
com ordem explícita.

## 1. Levantar
- PRs abertos do Dependabot: `gh pr list --author app/dependabot` (leitura).
- Vulnerabilidades: `uv run poe auditar`.
- Pendências registradas na memória (ex.: `minimatch` no passo 1).

## 2. Avaliar cada atualização
- Data de publicação da versão (PyPI / npm). Menos de 2 semanas → adiar e anotar.
- Major (ex.: 2.x → 3.x) ou biblioteca central (fastapi, pydantic, react, vite,
  anthropic): acione o `pesquisador-tecnico` para notas de versão e quebras.
- Licença mudou? Uso comercial continua permitido?

## 3. Aplicar (só o que passou no passo 2, com ok do usuário)
- Python: `uv lock --upgrade-package <pacote>` e `uv sync`.
- Front: editar a versão fixa em `frontend/package.json` (o projeto fixa versões,
  sem `^`) e `npm install` em `frontend/`.
- Rodar o `verificador`. Falhou → reverter aquela atualização e anotar o motivo.

## 4. Entregar
- Tabela curta: pacote, de → para, data da versão, aplicado/adiado e por quê.
- Mensagem de commit pronta (o usuário commita).
- Atualize a memória com o que ficou adiado e quando reavaliar.
