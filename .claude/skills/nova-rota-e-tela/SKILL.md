---
name: nova-rota-e-tela
description: Roteiro para uma funcionalidade de ponta a ponta na interface — rota FastAPI com pydantic, tipos e chamada em frontend/src/api.ts, tela React com TanStack Query, textos pelo GLOSSARIO e testes dos dois lados. Use ao criar ou mudar qualquer tela, aba, botão que fala com o servidor ou rota da API.
---

# Rota + tela

## Servidor (`src/autora/api/`)
1. Rota em `src/autora/api/rotas/<assunto>.py` (veja `perfis.py` e `agente.py`
   como padrão), registrada em `api/main.py`. Prefixo `/api/<assunto>`.
2. Entrada e saída com modelos pydantic. Todo modelo de entrada herda de
   `PedidoEstrito` (`src/autora/api/esquemas.py`): campo desconhecido vira 422.
   Teste isso em `test_campo_desconhecido_no_pedido_e_recusado`
   (`tests/test_api.py`), acrescentando a rota nova. Nunca devolver segredo,
   caminho absoluto do perfil ou detalhe técnico cru.
3. Segurança: as rotas exigem a sessão do servidor local (`api/seguranca.py`); não
   crie rota sem ela. Dado vindo do usuário é validado; caminhos passam por
   `resolver_dentro` (`util/arquivos.py`).
4. Erros: mensagem amigável e sem jargão no `detail` (ela aparece na tela); o
   detalhe técnico vai para o log.
5. Ações longas (rodada, estudo) não bloqueiam a requisição: disparam e a tela
   consulta o estado.

## Front (`frontend/src/`)
1. Tipos e função em `api.ts`, espelhando o modelo pydantic. (Se o
   `openapi-typescript` for adotado no passo 5, gere em vez de escrever.)
2. Tela em `telas/` ou componente em `componentes/`, com `useQuery`/`useMutation`
   do TanStack Query; invalidar as consultas afetadas após mutação.
3. **Todo texto visível em `textos.ts`**, com os nomes do `GLOSSARIO.md`. Nunca
   "IA", "modelo", "prompt" nem termo técnico (o teste `test_vocabulario.py`
   varre as telas). Se o termo não existe no glossário, pergunte ao usuário.
4. Rota da tela no `App.tsx` e item na `BarraLateral` se for tela nova.
5. Estados: carregando, erro (mensagem do servidor) e vazio.

## Testes
- Servidor: `tests/test_api.py` como padrão (TestClient com sessão), incluindo
  acesso sem sessão recusado e entrada inválida.
- Front: `*.test.tsx` com vitest + Testing Library (padrão em `App.test.tsx`).
- `uv run poe testar` e `uv run poe front`; se a tela mudou, abra o app
  (`/run` ou `uv run poe dev` + `npm run dev`) e confira no navegador.
