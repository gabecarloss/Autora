# Autora

Agente local que transforma uma biblioteca de vídeos em conteúdo autoral
para TikTok (e outras redes no futuro). Cada perfil opera uma conta, estuda
tendências diariamente, edita, gera material próprio quando necessário, e
aprende com métricas e com o usuário.

## Quem é quem (leia primeiro)

Há três Claudes neste projeto:
1. O Claude do planejamento: a conversa que gerou o BRIEFING.md. Acabou.
2. Você, o Claude Code: o DESENVOLVEDOR. Você escreve o software. Não é o
   agente de nenhum perfil, não cria conteúdo, não decide ganchos, não
   estuda tendências para postar. O mandato da seção 3.1 do briefing NÃO
   é sobre você; quando o briefing diz "você" ali, está falando com o
   agente do perfil.
3. O agente do perfil: um componente DENTRO do software. É uma chamada ao
   modelo que o software faz, com o mandato.md do perfil como base do
   system prompt mais a memória do perfil. Cada perfil tem o seu. O
   briefing descreve o comportamento DELE. Você o implementa como código.

Regras que decorrem disso:
- Nenhum vídeo é produzido sem passar pelo agente do perfil. Um script
  que escolhe um clipe e põe legenda, sem chamada ao modelo com o
  mandato, não é versão mínima do produto; é só tubulação.
- Se você se pegar decidindo conceito, gancho ou formato de um vídeo,
  pare: isso é trabalho do agente. O caminho certo é implementar a
  chamada que o faz decidir.
- Ferramental de desenvolvimento (subagentes, skills, hooks, CI) só
  cresce quando uma necessidade real aparecer no produto. O produto vem
  antes do processo.

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
- Siga a ordem de construção da seção 13. O passo 2 vem antes de qualquer
  sofisticação, e só está concluído quando: um vídeo real passou pelo
  agente do perfil com o mandato carregado; o agente decidiu conceito,
  formato e gancho com motivo registrado; o padrão mínimo de
  transformação (dois elementos autorais verificáveis) foi cumprido; o
  plano de edição em JSON foi executado pelo motor ffmpeg com legendas
  sincronizadas pelo Whisper; e saiu o pacote completo (video.mp4,
  post.md, capa.jpg). "Um mp4 saiu" não é critério.
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
- `inspetor-video` (haiku): ffprobe + quadros extraídos → laudo visual de um
  `video.mp4` (textos e legendas nos instantes do roteiro, enquadramento).
- `analista-logs` (sonnet, só leitura): logs JSONL + MCP SQLite → linha do tempo de
  uma rodada, chamadas ao agente com tokens e custo, onde falhou.
- Criar no passo 4: `avaliador-agente` (bateria da seção 14).

Skills:
- `/iniciar-passo N` e `/fechar-passo N`: a forma de trabalho acima.
- `chamada-ao-agente`: regras completas e roteiro para código que chama o agente.
- `nova-migracao`, `novo-servico-com-reserva`, `nova-rota-e-tela`: padrões que se
  repetem nos passos.
- `atualizar-dependencias`: Dependabot e auditorias, com espera de 2 semanas.
- Catálogo de bibliotecas candidatas por passo:
  `.claude/skills/iniciar-passo/bibliotecas.md`.
- `ffmpeg`: convenções do motor de edição (duas passagens, ASS, caminhos relativos,
  o que não funciona nesta build). `perfil-de-teste`: perfil com biblioteca sintética
  na pasta de dados. `depurar-rodada`: onde olhar quando uma criação falha.

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

**Passo 2 implementado (06/11/2026), aguardando validação com vídeo real.** O núcleo
está pronto e testado com clipes sintéticos e agente simulado (378 testes): etapas
`conceito` e `plano` do agente com esquema validado e repetição única, rodada com
etapas e decisões no banco, motor ffmpeg em duas passagens (cortes, enquadramento,
velocidade, zoom, textos e legendas por ASS), transcrição Whisper com reserva, post.md
e capa.jpg do TikTok, CLI `autora gerar` e botão "Criar agora". Próximo passo da
seção 13 depois de fechar: **3**, indexação.

### Passo 2: pendente para fechar (passagem de bastão para a máquina com GPU)

Esta sessão começa do zero: o que não estiver aqui ou no código, você não sabe. Siga
na ordem. O critério de conclusão continua o do CLAUDE.md: um vídeo REAL passou pelo
agente com o mandato, decisão com motivo, dois elementos autorais verificáveis, pacote
completo, post postado.

**1. Antes de rodar qualquer coisa**
- Tentativa antiga do passo 2 sem commitar nesta máquina: descarte. Critério: qualquer
  código que produza vídeo sem chamar o agente com o `mandato.md` (escolhe clipe, põe
  legenda, monta mp4) é tubulação, não passo 2, e a versão commitada já cobre tudo.
  Quem roda é o usuário (o hook `guardar_comandos` nega `git clean -f` e `reset --hard`):
  `git status --porcelain` para ver; opcional `git stash push -u -m "tentativa antiga
  passo 2"` para guardar uma cópia; depois `git restore --staged --worktree .` (descarta
  o rastreado) e `git clean -fd` (apaga o não rastreado; sem `-x`, `.venv` e
  `node_modules` ficam). Só então `git pull`, `uv sync --locked`, `npm ci` em `frontend/`,
  `uv run poe verificar` (deve ficar verde; testes `ffmpeg` rodam porque há ffmpeg).
- Pasta de amostra FORA do repositório com 20 a 50 vídeos reais (ex.: `D:\amostra`).
  Dentro dela, `descricoes.json` com uma linha por clipe para pelo menos 10 deles:
  `{"nome.mp4": "o que a cena mostra, em uma frase"}` (nome do arquivo ou caminho
  relativo com `/`). O agente ainda não analisa imagem (passo 3): sem descrição, um
  clipe sem fala é invisível para ele. Descrição é dado (o que aparece), não decisão
  criativa.
- Assinatura conectada no app DESTA máquina: `uv run autora-app` → Configurações
  globais → Agente → Assinatura Claude (abre `claude setup-token`, cola o código,
  testa). Sem isso, `autora gerar` para com "O agente ainda não foi conectado".
- Whisper: na primeira rodada o modelo `large-v3` (~3 GB) é baixado para
  `%USERPROFILE%\Autora\modelos\whisper` e usado na GPU; se a GPU falhar (cuBLAS/cuDNN
  ausentes), cai para `small` (~480 MB) na CPU e o log diz "o legendas pelo processador
  vai assumir". Demora: avise o usuário antes da primeira rodada. Os clipes candidatos
  (até 8, `LIMITE_CANDIDATOS`) também são transcritos nessa primeira rodada.

**2. Primeiro pacote com vídeo real, nesta ordem**
```
uv run autora perfil criar humor --nome "Humor"        # se o perfil ainda não existir
uv run autora gerar humor --pasta "D:\amostra"         # registra a pasta (apelido em maquina.json,
                                                        # só o apelido no perfil) e já cria o post
uv run autora gerar humor                               # rodadas seguintes
```
Saída: `%USERPROFILE%\Autora\saida\humor\<AAAA-MM-DD>\<n>\` com `video.mp4`, `post.md`,
`capa.jpg`, `roteiro.json`. A tela Perfis (botão "Criar agora") faz o mesmo em segundo
plano; o CLI é mais fácil de acompanhar.
- Conferir o vídeo: subagente `inspetor-video` com o caminho do `video.mp4` (ele lê o
  `roteiro.json` da mesma pasta, extrai quadros nos instantes dos textos e dá o laudo).
- Abrir `post.md` (gancho, alternativas, descrição, hashtags, som "a escolher no app",
  capa, elementos autorais, motivos, avisos) e `roteiro.json` (`ideia` = resposta do
  agente na etapa conceito com `raciocinio` das cinco perguntas; `roteiro` = cortes,
  textos, legendas; `entrega` = duração, estado das legendas, transcrição usada).
- Conferir que o agente decidiu e registrou, no log e no banco:
  - log: `%USERPROFILE%\Autora\perfis\humor\logs\<AAAA-MM-DD>.jsonl`; eventos `decisao`
    (etapa `conceito`: `detalhe.raciocinio`, `gancho`, `elementos_autorais`; etapa
    `plano`: o roteiro), `servico` ("O agente respondeu." com tokens), `etapa`. O
    subagente `analista-logs` monta a linha do tempo da rodada.
  - banco (MCP `autora-sqlite`, só leitura): `listar_perfis()`, depois
    `consultar("humor", "SELECT campo, escolha, motivo FROM decisao WHERE post_id = 1
    ORDER BY id")` — precisa ter `formato`, `tema`, `gancho`, `horario`, `capa`, um
    `clipe` por clipe escolhido, DOIS `elemento_autoral` de tipos distintos, e `ritmo`,
    `enquadramento`, `textos`, `legendas` do roteiro, todos com `motivo` específico;
    `consultar("humor", "SELECT etapa, estado, erro FROM etapa_execucao WHERE rodada_id
    = 1 ORDER BY id")` (estudo, revisor e verificacoes `pulada`; o resto `ok`);
    `consultar("humor", "SELECT etapa, nivel, modelo, tokens_entrada, tokens_saida,
    tokens_cache, custo_usd, duracao_ms, resultado FROM chamada_servico")` (uma linha
    por chamada ao agente; é a medição de consumo do item 5);
    `consultar("humor", "SELECT estado, gancho, pasta_saida FROM post")`
    (`aguardando_revisao`, pasta relativa).

**3. Se o vídeo real sair errado (skill `depurar-rodada`)**
Para olhar os intermediários, rode o motor de novo com a pasta de trabalho mantida:
```
uv run python -c "import json,pathlib; from autora.edicao.plano import PlanoEdicao; from autora.edicao.renderizador import renderizar; from autora.plataformas.tiktok import TikTok; from autora.registro.log import Registro; from autora.biblioteca.ficha import caminhos_dos_clipes, fichas_disponiveis; from autora.perfil.perfil import Perfil; from autora.config.global_config import pasta_dados; d=pasta_dados(); p=Perfil.abrir(d,'humor'); r=json.loads(pathlib.Path(r'<pasta do post>/roteiro.json').read_text(encoding='utf-8')); plano=PlanoEdicao.model_validate(r['roteiro']); con=p.conectar().__enter__(); ids={t.clipe_id for t in plano.trechos}; fichas=[f for f in fichas_disponiveis(p,d,con,limite=50) if f.id in ids]; renderizar(plano, caminhos_dos_clipes(fichas,d), pathlib.Path('depuracao'), espec=TikTok.video, registro=Registro(pathlib.Path('depuracao/logs'),'dep'), idioma='pt', pasta_modelos=d/'modelos'/'whisper', manter_trabalho=True)"
```
(Clipes já usados não voltam em `fichas_disponiveis`; para reprocessar um post, apague
as linhas dele em `post_video` ou monte `clipes={id: caminho}` à mão.) `depuracao/trabalho/`
fica com `filtros_1.txt`, `base.mp4`, `base.wav`, `whisper.wav`, `legendas.ass`, `fontes/`.
- **Sem legenda**: `post.md` → "Legendas:". "sem fala" com clipe falado: ouça
  `trabalho/whisper.wav`; confira `idioma_saida` do perfil (`pt-BR` → `pt`) e os eventos
  `servico` de "legendas" no log. "indisponíveis": as duas opções do Whisper falharam;
  o log tem o erro (CUDA sem DLL → instale cuBLAS/cuDNN ou aceite `small` na CPU; modelo
  não baixado → rede). Legenda existe mas não aparece: `legendas.ass` tem eventos?
  `fontes/` tem os `.ttf`? (fonte ausente usa a padrão e avisa no log.)
- **Sem áudio**: `inspetor-video` mostra `codec_audio`; `roteiro.json` →
  `audio.manter_original`; `filtros_1.txt` → se há entrada `anullsrc` para o trecho, a
  ficha do clipe disse `tem_audio = 0` (confira `SELECT id, caminho_relativo, tem_audio
  FROM video`); `trabalho/base.wav` mudo = problema na passagem 1 (stderr do ffmpeg
  está em `detalhe.ffmpeg` do evento `erro` do log, se houve erro).
- **Texto fora da zona segura**: `roteiro.json` → `textos[].posicao`/`y`;
  `legendas.ass` → `MarginV` (topo 200/1920 e base 430/1920 da altura, em
  `src/autora/edicao/legendas.py`, `_ALINHAMENTO`, provisório) e `\pos` dos textos com
  `y`. Ajuste as frações e re-renderize; registre a mudança como provisório do passo 2.
- **Duração divergente**: o log tem `erro` "O vídeo final saiu diferente do esperado"
  com o que divergiu. Compare `roteiro.json` → soma de (fim−início)/velocidade dos
  trechos com `entrega.duracao_s`; em `filtros_1.txt`, `atrim=end=` e os `-t` dos `-i`.
  Causas comuns: `fim_s` passando da duração real do clipe (tolerância 0,05 s em
  `verificar_contra_clipes`), clipe de taxa variável (o `fps=30` normaliza; confira com
  `ffprobe`), áudio mais curto que o vídeo (o `apad` cobre; se faltou, veja o stderr).
  Rode a passagem 1 à mão dentro de `trabalho/`: `ffmpeg <args de
  filtros.argumentos_passagem_1>` (skill `ffmpeg`).

**4. Postar de verdade e só depois fechar**
Critério para postar: o usuário responde "sim" a "Eu postaria isso?" (seção 14.3);
`inspetor-video` deu OK; os dois elementos autorais estão VISÍVEIS no vídeo, não só
declarados; legendas sincronizadas quando há fala; gancho, descrição e hashtags do
`post.md` sem cara de máquina; capa legível. O usuário posta no TikTok com o som e a
capa indicados no `post.md` e anota o link no fim do `post.md` (métricas e estado
`publicado` entram no passo 10). Se não postaria: `uv run autora gerar humor` de novo
(o agente nunca repete clipe) e registre o motivo na memória; três pacotes seguidos
reprovados = problema de método (texto da tarefa em `rodada/conceito.py`/`rodada/plano.py`
ou esquema), não do mandato (seção 14.5).
Então `/fechar-passo 2`, que inclui: fixar `NIVEL_PADRAO_POR_ETAPA` em
`src/autora/agente/provedor.py` com o consumo medido (`SELECT etapa, nivel, modelo,
SUM(tokens_entrada), SUM(tokens_saida), SUM(custo_usd), AVG(duracao_ms) FROM
chamada_servico GROUP BY etapa, nivel, modelo` em todas as rodadas), decidido com o
usuário; tirar o "PROVISÓRIO" dali; memória `passo-2-concluido`; "Estado do projeto"
apontando para o passo 3 (indexação).

**5. O que NÃO fazer nesta sessão**
Nenhum ferramental novo (subagente, skill, hook, MCP). Nada do passo 3 em diante
(indexação, hash perceptual, análise por IA dos clipes, estudo diário, revisor,
verificações, som, narração, tela de revisão) antes do pacote real conferido e
postado. Nenhuma dependência nova. Nenhuma mudança no `mandato.md`. Mudança no motor
só para corrigir o que o vídeo real mostrar, com teste. Nenhum commit sem o usuário
pedir.

Decisões do passo 2 (06/11/2026): sem narração (edge-tts fica no passo 7); disparo
por CLI e botão mínimo (sem tela de revisão, passo 9); testes com agente real usam a
conexão feita no app. Provisórios do passo 2 estão marcados "PROVISÓRIO" no código:
limites desta versão na mensagem do agente, tipos de elemento autoral e a checagem por
código do padrão mínimo (até o revisor do passo 8), `LIMITE_CANDIDATOS` e
`descricoes.json` (até a indexação do passo 3), modelos Whisper `large-v3`/`small` em
`maquina.json`, fontes do Windows, limites de duração/zona segura, níveis por etapa até
medir o consumo, sem few-shot, lista de ganchos genéricos do teste real, etapas
`estudo`/`revisor`/`verificacoes` puladas, testes `ffmpeg` pulando no CI.

Ferramentas do Claude Code (subagentes, skills, hooks, MCP, poe) montadas em
06/11/2026, fora da ordem da seção 13. Adiado pelo usuário: branch `production`,
promoção pelo Actions e release (memória `ideia-futura-producao`).

### Respostas da seção 12 e decisões (05/11/2026)
- Máquina: Windows 10, i9-9900K, 16 GB RAM, RTX 2080 Ti 11 GB. O Whisper
  vê a GPU; o ffmpeg tem libx264 e h264_nvenc.
- Primeiro perfil: humor, em português.
- Agente: conexão pela assinatura Claude do usuário, feita dentro do app
  (Configurações globais → Agente). É o caminho principal, inclusive
  para o produto. A chave da API pelo SDK `anthropic` fica como
  alternativa opcional no mesmo lugar, para quem preferir. Trocar de
  provedor não pode exigir mudança fora do módulo `agente/`, e os testes
  com agente simulado cobrem os dois. (Decisão do usuário em 06/11/2026.)
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
- CLI: `uv run autora perfil criar|listar`, `uv run autora backup`,
  `uv run autora gerar <perfil> [--pasta <vídeos>] [--teste]` (cria um post agora).
- Testes: `uv run poe testar` (agente simulado, com cobertura; testes `ffmpeg` pulam
  sem ffmpeg); `uv run poe testar-agente` (agente real, inclui rodada completa com
  Whisper); `uv run poe testar-whisper` (transcrição real, baixa o modelo).
- Checagens: `uv run poe lint` (ruff, mypy, camadas, dependências) ·
  `uv run poe front` · `uv run poe auditar` · `uv run poe formatar`.
- Tudo de uma vez: `uv run poe verificar` ou o subagente `verificador`.
- CI depois do push: `gh run list` / `gh run watch`.

### Onde fica o quê
- `src/autora/`: `config/` (global, máquina, segredos) · `perfil/` (pasta
  portátil, esquema único do onboarding e das configurações, memória com
  histórico, exportar/importar) · `db/` (conexão e migrações) · `registro/`
  (logs JSONL com máscara de segredos) · `backup/` · `agente/` (provedores,
  contexto, conexão pelo app) · `servicos/` (`cadeia.py` principal → reserva;
  `transcricao.py` Whisper GPU → CPU) · `plataformas/` (interface genérica;
  `tiktok/` com especificação do vídeo e `post_md.py`) · `api/` (servidor local;
  rota "criar agora") · `rodada/` (`executar.py` a rodada; `conceito.py` e `plano.py`
  as duas chamadas ao agente; `chamada.py` chamada com esquema e repetição única;
  `esquemas.py` o que o agente devolve na ideia; `transformacao.py` padrão mínimo;
  `pacote.py` pasta de saída; `estado.py` criação em segundo plano) · `edicao/`
  (`plano.py` roteiro de edição; `filtros.py` → ffmpeg; `legendas.py` → ASS;
  `renderizador.py` duas passagens; `capa.py`; `ffmpeg.py` sondagem; `fontes.py`;
  `sintetico.py` clipes de teste) · `biblioteca/ficha.py` (ficha dos clipes,
  tabela `video`, clipes usados nunca voltam).
- Saída: `<dados>/saida/<perfil>/<data>/<n>/` com `video.mp4`, `post.md`, `capa.jpg`,
  `roteiro.json`.
- `frontend/`: barra lateral, Perfis (mínimo), Configurações globais
  (agente, nível por etapa, modo de criação).
- `ferramentas/`: só desenvolvimento (servidor MCP de leitura, tarefas do poe).
- `.claude/`: subagentes, skills, hooks e `settings.json` (ver "Ferramentas do
  Claude Code"); `.mcp.json` na raiz.
- Dados fora do repositório: `%USERPROFILE%\Autora\` (ou `AUTORA_DADOS`).

<!-- Atualizar ao fim de cada etapa: etapa atual, comandos para rodar,
estrutura de pastas, decisões novas tomadas com o usuário (com data). -->
