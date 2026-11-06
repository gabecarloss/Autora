# Autora

Agente local que transforma uma biblioteca de vídeos em conteúdo autoral
para TikTok (e outras redes no futuro). Cada perfil opera uma conta, estuda
tendências diariamente, edita, gera material próprio quando necessário, e
aprende com métricas e com o usuário.

## Antes de qualquer tarefa

Leia `BRIEFING.md` por inteiro. Ele define o projeto, as decisões já
tomadas, o mandato do agente (seção 3.1), a arquitetura, a interface, os
testes e a ordem de construção. Tudo que está lá foi decidido com o
usuário e não deve ser reinterpretado.

## Regras de trabalho

- **Nunca commite nem altere o repositório git por conta própria** (add, commit,
  push, pull, branch, checkout/switch, merge, rebase, tag, stash, restore, reset; e
  `gh pr/release/repo/workflow run`). Só com pedido explícito do usuário, e o pedido
  vale só para aquela operação. Você entrega a mensagem de commit pronta; quem
  commita é o usuário. (Reforçado por permissões e pelo hook `guardar_comandos`.)
- **Testes automatizados, não conferência manual.** Toda função ou comportamento
  novo ou alterado tem teste em `tests/` (ou `*.test.tsx` no front), escrito junto
  com o código. Se você precisou conferir algo à mão (script avulso, simulação,
  chamada de teste, olhar uma saída), transforme essa conferência em teste antes de
  fechar a tarefa. Assim ela roda de graça em toda verificação (`uv run poe
  verificar`, CI, pre-commit) e não gasta contexto de novo. Para testes que
  dependem de algo caro ou externo (agente real, rede), use um marcador
  (`@pytest.mark.agente`) em vez de deixar sem teste.
- Decisões não cobertas pelo briefing: pergunte ao usuário. Não assuma.
- Siga a ordem de construção da seção 13. O passo 2 (versão mínima com um
  vídeo real postado) vem antes de qualquer sofisticação.
- O mandato (seção 3.1) é a base de toda chamada ao modelo feita pelo
  sistema. Nunca o encurte nem o parafraseie no código; carregue o arquivo
  `mandato.md` do perfil.
- Serviços de voz e legenda são gratuitos (seção 7.3). Não introduza
  serviços pagos sem o usuário habilitar explicitamente.
- Interface sem jargão: "agente", nunca "IA", "modelo" ou "prompt" em
  texto visível ao usuário (seção 9.1). Use os nomes de `GLOSSARIO.md`.
- Ao concluir uma etapa da seção 13, diga ao usuário o que foi feito, o
  que ficou pendente e qual é o próximo passo. Atualize a seção "Estado do
  projeto" abaixo.

## Forma de trabalho (decidida com o usuário em 05/11/2026)

- **Um plano por passo** da seção 13: `/iniciar-passo N` (retoma estado e
  pendências, lê o briefing do passo, checa bibliotecas, entra em modo de plano).
  O plano só cobre aquele passo.
- **Ao fim de cada passo**: `/fechar-passo N`. Entrega resumo (feito, pendente,
  como verificar), mensagem de commit pronta, provisórios, memória
  (`passo-N-concluido` + `MEMORY.md`) e "Estado do projeto" atualizados, e o
  próximo passo da seção 13. Quem commita é o usuário.
- Desenvolvimento usa a conta Pro do usuário, sem economia artificial: faça
  chamadas reais ao agente sempre que forem úteis. O agente do app usa
  outra conta (Max), conectada pelo próprio app.
- O briefing é a fonte da verdade. Padrões que você precisar criar onde ele
  não decide ficam marcados como "provisório" no código e são listados ao
  usuário no fechamento do passo.

## Ferramentas do Claude Code

Cada recurso tem um papel. Escolha pelo papel, não pelo hábito:
- **Subagente** (`.claude/agents/`): tarefa isolada com saída longa e resumo curto
  (testes, logs, pesquisa), ou papel de **avaliador independente** (quem gera não
  avalia). Não use para tarefa de uma ou duas ferramentas, nem para decisão de
  arquitetura ou de produto: isso fica no contexto principal, com o usuário.
- **Skill** (`.claude/skills/`): procedimento que se repete ou conhecimento que só
  algumas tarefas precisam. Carrega sob demanda; este arquivo fica curto.
- **Hook** (`.claude/hooks/`, ligado em `.claude/settings.json`): regra que tem de
  valer sempre, sem depender de lembrar. **Não contorne um hook**; se ele atrapalhar,
  explique ao usuário e deixe ele decidir.
- **MCP** (`.mcp.json`): acesso a sistema externo.
- **Criar**: quando a mesma sequência aparecer pela terceira vez (subagente ou
  skill), ou quando o passo indicado abaixo chegar, a partir do primeiro código
  real. Subagente: descrição de quando usar, ferramentas mínimas, modelo mais barato
  que dê conta (`haiku` para tarefa mecânica, `sonnet` para julgamento), resposta
  curta e fixa. Skill: `SKILL.md` com descrição que diga quando usar.

Subagentes:
- `verificador` (haiku): `poe lint`, `poe testar`, `poe front`, pre-commit → só as
  falhas. Após qualquer mudança de código e antes de fechar um passo.
- `conformidade` (sonnet, só leitura): diff contra as decisões fixas e as regras de
  chamada ao agente → `CONFORME` ou violações.
- `pesquisador-tecnico` (sonnet, web + Context7): antes de qualquer dependência
  nova ou especificação de plataforma; fonte e data; não instala nada.
- `escritor-de-testes` (sonnet): testes a partir do plano e das assinaturas, sem
  ler a implementação.
- Prontos do Claude Code: `Explore` (varreduras), `Plan`, `/code-review`,
  `/simplify`, `/security-review` (usados no `/fechar-passo`).
- Criar no passo 2: `inspetor-video` (ffprobe + quadros → checagem visual do
  vídeo) e `analista-logs` (logs JSONL + MCP SQLite → linha do tempo da rodada).
  No passo 4: `avaliador-agente` (bateria da seção 14).

Skills:
- `/iniciar-passo N` e `/fechar-passo N`: a forma de trabalho acima.
- `chamada-ao-agente`: regras completas e roteiro para código que chama o agente.
- `nova-migracao`, `novo-servico-com-reserva`, `nova-rota-e-tela`: padrões que se
  repetem nos passos.
- `atualizar-dependencias`: Dependabot e auditorias, com espera de 2 semanas.
- Catálogo de bibliotecas candidatas por passo:
  `.claude/skills/iniciar-passo/bibliotecas.md`.
- Criar no passo 2: `ffmpeg` (convenções de vídeo), `perfil-de-teste` (perfil com
  biblioteca sintética na pasta de dados) e `depurar-rodada`.

Hooks (scripts Python testados em `tests/hooks/`):
- `proteger_arquivos`: pede confirmação para editar `BRIEFING.md` e `mandato.md`;
  nega texto com cara de segredo real.
- `guardar_comandos`: pede confirmação para git/gh que alteram o repositório (mesmo
  dentro de comando composto); nega push forçado, `reset --hard`, `--no-verify` e
  apagar a pasta de dados real.
- Os dois acima reconhecem o subagente (`agent_type`): o `escritor-de-testes` só
  grava em `tests/` ou `*.test.tsx` e só roda comandos de teste (lista fechada).
- `formatar`: ruff (Python) e prettier (front) no arquivo editado; erro que sobra
  volta para você corrigir na hora.
- `inicio_sessao`: branch, arquivos não commitados, último commit e estado.

MCP:
- `context7`: documentação atual das bibliotecas, por versão.
- `autora-sqlite` (`ferramentas/mcp_sqlite_leitura.py`): leitura dos bancos dos
  perfis; só leitura por construção.

## Código que chama o agente (resumo)

Regras completas e roteiro na skill `chamada-ao-agente`. O inegociável:
- Mandato integral e primeiro (`montar_sistema`); material de fora sempre em
  `dados_externos()`; saída com esquema JSON validado por pydantic.
- Ferramentas só por `FERRAMENTAS_POR_ETAPA`; quem gera não avalia; "não sei" é
  resposta válida; tudo por `chamar_registrando`.
- Mudança no mandato, no método ou no nível passa antes pela bateria da seção 14.

## Desenvolvimento

- Explorar → planejar → implementar → verificar → entregar a mensagem de commit.
- Verifique com o `verificador` antes de declarar pronto.
- Antes de usar uma biblioteca, consulte a documentação da versão instalada
  (Context7), não a memória.
- Mantenha este arquivo curto e atual. Detalhe vai para skills, código, testes ou
  `GLOSSARIO.md`.
- Contexto limpo entre passos: o estado vive aqui e na memória, não no
  histórico da conversa.

## Decisões técnicas fixas

Estas são obrigações, não sugestões.

- Pilha: Python no backend; ffmpeg para vídeo; Whisper local para
  legendas; SQLite por perfil. O resto (interface, bibliotecas) você
  propõe e pergunta antes de fixar.
- Perfil portátil: cada perfil é uma pasta com `config.json`, banco,
  logs e arquivos de memória. Nenhum caminho absoluto da máquina dentro
  do perfil. Exportar e importar a pasta tem que funcionar em outro PC.
- Chaves de API: só na configuração global, nunca dentro de um perfil,
  nunca em texto puro em disco, nunca em logs ou exportações.
- Logs desde o primeiro commit: toda etapa, decisão, chamada a serviço e
  erro vai para o log do perfil (seção 9.5), em arquivos por dia.
- Cópia de segurança automática dos perfis (banco e arquivos de memória),
  diária, com retenção configurável. Padrão sem o usuário precisar ligar.
- Separe o que é específico do TikTok (som, Display API, formato do
  post.md) do que é genérico, para receber outras plataformas depois.
- Falha isolada: um vídeo que falha não derruba a rodada; um serviço que
  falha cai para o reserva. Nenhum erro pontual derruba o sistema.
- Modo de geração (seção 15.1): "automático" roda as rodadas no horário
  de cada perfil; "manual" não roda nada sozinho. "Pausar" é diferente de
  "manual": pausar é temporário, preserva todas as configurações, e ao
  religar o sistema NÃO tenta recuperar rodadas perdidas. Com o sistema
  pausado, o botão "gerar agora" de cada perfil continua funcionando.
  Enquanto pausado, o estudo diário também não roda.
- Proteção contra acúmulo (seção 15.2): no modo automático com aprovação
  ligada, mais de duas rodadas aguardando revisão pausa a geração daquele
  perfil e avisa.
- Verificações automáticas (seção 14.2) rodam em toda rodada, após o
  revisor e antes do pacote. Quem gera não avalia: revisor e verificações
  são chamadas separadas, sem acesso ao plano de edição.
- O agente nunca publica nada e nunca age na conta do usuário. A obtenção
  de sons para análise (yt-dlp) não usa a conta do usuário.

## Estado do projeto

**Passo 1 concluído (06/11/2026).** Próximo: **passo 2**, versão mínima
ponta a ponta (um vídeo, um post.md, postado de verdade).

Ferramentas do Claude Code (subagentes, skills, hooks, MCP, poe) montadas em
06/11/2026, fora da ordem da seção 13. Adiado pelo usuário: branch `production`,
promoção pelo Actions e release (memória `ideia-futura-producao`).

### Respostas da seção 12 e decisões (05/11/2026)
- Máquina: Windows 10, i9-9900K, 16 GB RAM, RTX 2080 Ti 11 GB. O Whisper
  vê a GPU; o ffmpeg tem libx264 e h264_nvenc.
- Primeiro perfil: humor, em português.
- Agente: assinatura Claude (Max quando o sistema estiver pronto),
  conectada **dentro do app** (Configurações globais → Agente). A chave da
  API é a alternativa, obrigatória se o produto for vendido.
- Teto de custo: configurável no app. O padrão sai da medição de consumo
  no passo 2.
- Vídeo por modelo pago: desligado.
- Interface: FastAPI + React/TypeScript (Vite) numa janela pywebview.
- Pendente de confirmação: nomes do `GLOSSARIO.md` marcados "(?)";
  retenção de backups de 30 dias; pasta de dados `%USERPROFILE%\Autora`.

### Pilha
Python 3.11 (uv) · pydantic · FastAPI/uvicorn · pywebview · SQLite com
migrações SQL numeradas · keyring (Cofre de Credenciais do Windows) · typer ·
faster-whisper · ffmpeg · Claude Code headless (`claude -p`) ou SDK
`anthropic` · React 19 + TanStack Query + React Router · Vite · vitest ·
pytest (+ pytest-cov) · ruff · mypy strict · import-linter · deptry ·
poethepoet · eslint · prettier · pre-commit com gitleaks · CI no GitHub Actions ·
Dependabot · gh (GitHub CLI).

### Comandos
Tarefas em `[tool.poe.tasks]` do `pyproject.toml` (equivalente aos scripts do
npm); `uv run poe` lista todas. CI, pre-commit e `verificador` usam as mesmas.
- Abrir o app: `uv run autora-app` (desenvolvimento: `uv run poe dev`
  + `npm run dev` em `frontend/`).
- CLI: `uv run autora perfil criar|listar`, `uv run autora backup`.
- Testes: `uv run poe testar` (agente simulado, com cobertura);
  `uv run poe testar-agente` (agente real).
- Checagens: `uv run poe lint` (ruff, mypy, camadas, dependências) ·
  `uv run poe front` · `uv run poe auditar` · `uv run poe formatar`.
- Tudo de uma vez: `uv run poe verificar` ou o subagente `verificador`.
- CI depois do push: `gh run list` / `gh run watch`.

### Onde fica o quê
- `src/autora/`: `config/` (global, máquina, segredos) · `perfil/` (pasta
  portátil, esquema único do onboarding e das configurações, memória com
  histórico, exportar/importar) · `db/` (conexão e migrações) · `registro/`
  (logs JSONL com máscara de segredos) · `backup/` · `agente/` (provedores,
  contexto, conexão pelo app) · `servicos/cadeia.py` (principal → reserva) ·
  `plataformas/` (interface genérica; `tiktok/` vazio até o passo 2) ·
  `api/` (servidor local) · `rodada/`, `edicao/`, `biblioteca/` (vazios).
- `frontend/`: barra lateral, Perfis (mínimo), Configurações globais
  (agente, nível por etapa, modo de criação).
- `ferramentas/`: só desenvolvimento (servidor MCP de leitura, tarefas do poe).
- `.claude/`: subagentes, skills, hooks e `settings.json` (ver "Ferramentas do
  Claude Code"); `.mcp.json` na raiz.
- Dados fora do repositório: `%USERPROFILE%\Autora\` (ou `AUTORA_DADOS`).

<!-- Atualizar ao fim de cada etapa: etapa atual, comandos para rodar,
estrutura de pastas, decisões novas tomadas com o usuário (com data). -->
