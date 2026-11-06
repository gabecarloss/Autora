---
name: nova-migracao
description: Cria uma migração SQL numerada para o banco do perfil (src/autora/db/migracoes) com teste. Use sempre que um passo precisar de tabela, coluna ou índice novo no SQLite do perfil.
argument-hint: "[nome_curto_da_migracao]"
---

# Nova migração: $ARGUMENTS

Como funciona (`src/autora/db/conexao.py`): arquivos `NNNN_nome.sql` em
`src/autora/db/migracoes/`, aplicados em ordem, cada um numa transação; a versão
fica em `PRAGMA user_version`. A numeração precisa ser contínua (1, 2, 3...), senão
`migracoes_disponiveis()` falha de propósito.

## Passos
1. Próximo número: liste `src/autora/db/migracoes/` e some 1 ao maior. Nome em
   minúsculas com `_` (regex `^\d{4}_[a-z0-9_]+\.sql$`).
2. Cabeçalho em comentário: `-- Migração NNNN: <o quê> (passo N).` e o porquê.
3. Regras do SQL:
   - **Nunca** edite uma migração já existente (perfis reais já a aplicaram); corrija
     com outra migração.
   - Sem `;` dentro de strings ou triggers (o divisor é simples, ver `_dividir_sql`).
     Se precisar de trigger, ajuste o divisor antes, com teste.
   - `CHECK` para estados e origens (padrão de `0001_base.sql`), `NOT NULL` onde
     faz sentido, datas em `TEXT` ISO 8601 (`agora_iso()`), chaves estrangeiras
     explícitas.
   - **Nenhum caminho absoluto** em coluna (perfil portátil): use caminho relativo
     ao perfil ou apelido de pasta, como `video.caminho_relativo`.
   - Nenhuma coluna para segredo.
   - `ALTER TABLE ... ADD COLUMN` com `DEFAULT` para não quebrar linhas antigas.
4. Teste (em `tests/test_perfil.py` ou no teste do módulo que usa a tabela):
   - perfil criado do zero chega na versão nova;
   - banco na versão anterior com dados migra sem perder linhas
     (crie com as migrações até N-1, insira, rode `migrar`, confira);
   - migração idempotente (abrir de novo não reaplica): já coberto por
     `test_migracao_e_idempotente`; rode-o.
5. Se a tabela guarda algo que aparece na tela Bastidores ou entra no backup/exportação,
   confira se `backup/` e `perfil/exportar.py` continuam corretos (eles copiam o
   banco inteiro; normalmente não precisam mudar).
6. `uv run poe testar` e, no fechamento do passo, o `verificador`.
