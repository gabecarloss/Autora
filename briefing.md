# Autora — Briefing do projeto
Data: 05/11/2026. Consolidação de uma conversa entre o usuário e o Claude.
O Claude que ler isto vai rodar no PC do usuário e construir o sistema.
Decisões não cobertas aqui devem ser perguntadas ao usuário, não assumidas.

---

## 1. Contexto e objetivo

- O usuário já teve mais de uma página de cortes no TikTok. A de humor foi a
  melhor (vídeo de 40 mil+ views). Postava 4 vídeos por dia.
- Parou por dois motivos: a edição manual tomava o dia inteiro, e cortes
  pouco editados (filmes, séries, vídeos de outras pessoas) eram tratados pelo
  TikTok como conteúdo não original.
- Tem ~20.000 vídeos de diversos nichos numa pasta no PC. Já estudou edição e
  entende de corte no ritmo da música.
- Objetivo: voltar a postar com o mínimo de esforço manual, com trabalho
  autoral em todo vídeo, e com cada conta operada por um agente que aprende
  o que funciona e afunila o conteúdo com o tempo.
- Hoje o único usuário é ele; pode vender o software depois. A interface tem
  que ser amigável e sem jargão desde o início.

---

## 2. O que a versão 1 entrega

A publicação é manual. Para cada post, o sistema gera uma pasta
`saida/<perfil>/<data>/<n>/` com:

- `video.mp4`: final, 9:16, 1080x1920, 30fps, H.264. Narração (se houver)
  já mixada. Música NUNCA embutida.
- `post.md`: gancho/título escolhido + 2-4 alternativas; descrição; 3-5
  hashtags; horário sugerido e motivo; som (nome, link, trecho, volume,
  cobertura, motivo, e par "segundo X do som → segundo Y do vídeo" quando
  houver); frame e texto da capa; formato, voz e versão de estilo usados.
- `capa.jpg`: frame da capa com o texto aplicado, para conferência.
- `previa_com_som.mp4` (opcional): só para conferir sincronia no PC.

O usuário posta no TikTok, adiciona o som e a capa. Publicação automática
fica para o futuro (a API oficial exige auditoria; sem ela, posts saem
privados).

---

## 3. Perfis

Cada PERFIL é uma conta do TikTok (um nicho ou vários), operada por um agente
próprio. O agente decide formato, tema, som, voz, ritmo, séries e estratégia
de postagem, e muda conforme aprende. Perfis NÃO compartilham memória: nichos
e idiomas diferentes aprendem coisas diferentes.

Cada perfil vive numa pasta própria e portátil: `config.json`, banco SQLite,
e os arquivos de memória abaixo. Chaves de API ficam em configuração global
do app, fora do perfil.

Arquivos de memória do perfil:
- `preferencias_usuario.md`: o que o usuário disse em conversas e no
  onboarding. PRIORIDADE MÁXIMA: vale acima de qualquer métrica, até o
  usuário mudar. Editável pelo usuário na interface.
- `aprendizados.md`: conclusões do agente sobre o que funciona, com data,
  evidência (quantidade de posts) e nível de confiança.
- `tendencias.md`: resultado dos estudos, cada item com fonte e data.
- `publico.md`: quem é o público, escrito e atualizado pelo agente a partir
  de métricas e comentários (o usuário não precisa saber isso no início).
- `ganchos.md`: catálogo de padrões de gancho com desempenho.
- Histórico de posts (banco): cada post com formato, gancho, duração, tema,
  som, voz, horário, versão de estilo, referência (se adaptação), motivo de
  cada escolha, e métricas.

---

## 4. Indexação da biblioteca

Ao vincular uma pasta, indexar cada vídeo em SQLite, de forma incremental e
em segundo plano (testar em pasta pequena antes dos 20 mil):
- Metadados (duração, resolução, orientação, áudio).
- Hash perceptual: detectar duplicatas e NUNCA repostar o mesmo vídeo ou
  quase igual.
- Transcrição com Whisper (local; GPU se houver).
- Análise por IA (frames + transcrição): assunto, categoria, impacto/humor,
  nota de potencial 0-10, risco de direitos autorais (filme/série/TV = alto).
- Índice de MOMENTOS: os 2 a 5 segundos mais fortes de cada vídeo, com
  timestamp. Compilações e histórias são montadas a partir dos melhores
  momentos, não de vídeos inteiros.

---

## 5. Rodada de geração (ordem obrigatória)

1. Estudo de tendências e estratégia (seção 8.3). SEMPRE primeiro.
2. Seleção de vídeos: automática pela pasta ou manual, conforme o perfil.
   Automática = melhores não usados, variando tema e formato, evitando alto
   risco de direitos.
3. Conceito do post (seção 6): formato, história, gancho, som, voz, série.
4. Plano de edição em JSON gerado pelo agente, executado por ffmpeg + Python.
5. Revisor independente: uma segunda chamada à IA, que NÃO viu o plano,
   assiste como espectador: prevê onde a atenção cai, confere legibilidade
   do texto, sincronia da legenda, volume, duração e o padrão mínimo de
   transformação. Só então libera. Quem gera não avalia.
6. Pacote de publicação (seção 2).
7. Tela de revisão (se aprovação estiver ligada): o usuário aprova, descarta
   ou pede refazer com comentário.

- Quantidade de vídeos por rodada: configurada no perfil.
- Dentro de uma rodada, variar formatos de propósito.
- Um vídeo que falha não derruba a rodada; os outros seguem.

---

## 6. Originalidade e formatos (obrigatório)

Padrão mínimo de transformação: todo post tem pelo menos DOIS elementos
autorais verificáveis (ex.: narrativa própria + remontagem; texto que muda o
sentido + ritmo novo; compilação com critério + comentário). "Só legenda e
gancho" não existe como opção, mesmo em vídeo já bom, porque o TikTok pode
tratar como corte não autoral. O revisor checa isso.

O agente tem liberdade total de formato desde o primeiro post:
- Compilação temática com ranking ou progressão.
- Narração que explica, comenta ou contextualiza.
- História/roteiro com os vídeos como fundo (relacionados ou não).
- Texto na tela criando narrativa (perguntas, revelações, "espera o final").
- Reação/comentário em texto. Remontagem com ritmo próprio.
- Adaptação: reproduzir o CONCEITO de um viral de outro país/idioma
  (estrutura, gancho, ritmo), nunca o vídeo, com material da biblioteca.
  Registrar a referência.
- Séries e quadros recorrentes, "parte 2", bordões e identidade da conta.
  Views vêm de vídeos; seguidores vêm de expectativa. O agente cria e mantém
  a identidade, e o usuário pode renomear, pausar ou encerrar séries.
- Vídeos de resposta a comentários.

Risco: cortes de filmes/séries/TV continuam sendo o pior caso mesmo com
edição. Evitar, ou só com transformação pesada.

---

## 7. Produção

### 7.1 Edição
- ffmpeg orquestrado por Python; plano em JSON (cortes, textos, zooms,
  legendas, narração, batidas).
- Legendas a partir do Whisper, palavra por palavra, com timing.
- Horizontal → 9:16 com fundo desfocado ou recorte no ponto de interesse.
- Cada mudança de estilo de edição recebe um número de versão, registrado
  nos posts, para separar efeito do estilo de efeito do assunto/algoritmo.

### 7.2 Trilha sonora
- UMA música da biblioteca do TikTok por post, adicionada pelo usuário no
  app. Nunca embutida no arquivo.
- O agente escolhe o som sozinho a partir do estudo (Creative Center do
  TikTok, listas de sons em alta, notícias), localiza a página do som ou um
  vídeo que o usa, baixa só o áudio com yt-dlp para análise e descarta. A
  conta do usuário não participa.
- Análise: BPM, batidas, tempos fortes, viradas, drops (librosa/madmom).
  Cortes, zooms e textos posicionados nesses pontos quando o formato pedir.
- Preferência por usar o som desde o início (offset zero). Com trecho, o
  post.md diz "segundo X do som → segundo Y do vídeo" e o marco audível.
- Sincronia é desejável e deve ser feita sempre que possível; o quanto pesa
  na retenção é cada perfil que conclui pelo estudo. Regra fixa: nunca
  bloqueia a rodada. Se o áudio não puder ser obtido, o vídeo sai com ritmo
  próprio, o som é indicado mesmo assim e o post.md marca "sem sincronia";
  opção de colar o link para refazer.
- Com narração, o agente indica volume da música para não cobrir a voz.
  Quando o som é o elemento central, o vídeo é cortado no ritmo dele.

### 7.3 Vozes e legendas
- Só serviços gratuitos. Principal: edge-tts. Reserva offline: Kokoro,
  Piper, XTTS. Whisper local para legendas (sem limite).
- Limites: edge-tts não publica limite; usar fila com pausas e, em erro,
  cair para a reserva na hora. API do Claude tem limite por minuto: rodada
  serial, tolerando espera. Nada derruba a rodada inteira.
- O estudo inicial monta, por idioma, lista de vozes ordenada por qualidade.
  O agente varia entre as boas, nunca usa as fracas, e registra a voz de
  cada post. Vozes correspondem ao idioma da conta.

### 7.4 Custo
- Aba "Custo" no app: acumulado por perfil e total, por dia/semana/mês;
  média por post; projeção do mês. Não aparece no post.md nem na revisão.
- Teto mensal configurável por perfil, com aviso ao se aproximar.
- Custos: API do Claude. TTS e Whisper são zero.

---

## 8. Aprendizado do agente

### 8.1 Métricas (duas opções, coexistem)
- Automática: conta TikTok vinculada via Login Kit + Display API (escopos
  user.info.basic, user.info.stats, video.list; só leitura). Diariamente:
  views, likes, comentários, shares por vídeo e seguidores. Casar cada vídeo
  com o pacote que o gerou.
- Manual: CSV do TikTok Studio ou prints (analytics, curva de retenção,
  comentários). O sistema extrai, mostra o que leu para confirmação, e casa
  com o post (ou pergunta).
- CURVA DE RETENÇÃO é o dado principal: o agente mapeia cada queda para o
  segundo exato do vídeo e descobre a causa. É o único jeito de aprender o
  porquê. No pedido semanal, a curva dos melhores e dos piores é o item mais
  importante. Retenção tem peso maior que views.
- Comentários (via print): o agente extrai o que o público pediu, achou
  graça ou criticou, e transforma em pautas e vídeos de resposta.
- Lembrete semanal: o agente pede a atualização de métricas em dia e hora
  configurados, junto com o relatório da semana (8.4).

### 8.2 Experimentos e análise
- Fila de hipóteses por perfil; testar UMA variável por vez ("esta semana,
  gancho em pergunta vs. afirmação, resto igual"). Padrão: 70% dos posts no
  que já funciona, 30% explorando (ajustável no perfil).
- Periodicamente (semanal ou ~20 posts): o que os melhores e os piores têm
  em comum (formato, gancho, duração, tema, som, voz, horário, versão).
  Conclusões em `aprendizados.md`.
- Catálogo de ganchos (`ganchos.md`): padrões, não textos ("revelação
  adiada", "pergunta direta", "contagem regressiva"), com desempenho.

### 8.3 Estudo de tendências e estratégia
- Primeira etapa de toda rodada. Por nicho, SEM restringir idioma ou país:
  o que viralizou em outros idiomas é fonte de conceitos a adaptar.
- Cobre: formatos e ganchos em alta, sons em alta (no idioma da conta e
  fora), assuntos do momento, mudanças de regras do TikTok.
- Lista de contas do nicho que o agente acompanha (gerida por ele; o usuário
  vê e pode remover). Varredura semanal dos posts mais fortes delas,
  extraindo o conceito, nunca o vídeo.
- Estratégia de postagem: horários com mais alcance para o nicho e público,
  frequência e espaçamento, dias da semana, ordem de publicação, primeiro
  post do dia ser o mais forte, momentos a evitar. Registrada em
  `aprendizados.md`; o horário de cada post.md vem dela, com motivo.
- Resultado com data em `tendencias.md`; rodadas no mesmo dia reaproveitam e
  complementam. O agente deve estar SEMPRE se atualizando.

### 8.4 Relatório semanal
Junto com o pedido de métricas: o que aprendeu, o que vai mudar, o que quer
testar, e onde está incerto. É como o usuário acompanha o rumo da conta e
intervém pela conversa.

### 8.5 Anti-alucinação (regras estruturais)
- Toda afirmação em `tendencias.md` precisa de fonte e data; sem isso não
  entra.
- Conclusões em `aprendizados.md` precisam de mínimo de posts (padrão 8) e
  vêm com nível de confiança.
- O agente pode e deve escrever "não sei ainda" ou "evidência fraca".
- Separar sempre fato pesquisado de inferência própria.

### 8.6 Conversa com o agente
- Aba própria do perfil, sempre acessível. O usuário sugere temas, estilos,
  reclama do rumo, pede ajustes.
- Cada conversa é destilada em `preferencias_usuario.md`, com data, e o
  usuário vê o que o agente entendeu. Preferências do usuário têm prioridade
  sobre aprendizados automáticos.

---

## 9. Interface

### 9.1 Princípios
- Chamar de "agente", nunca "IA", "modelo" ou "prompt". Verbos do usuário:
  "o agente vai escolher", "você aprova". Sem "pipeline" ou "rodada" na
  interface (nomes amigáveis a decidir, ex.: "lote do dia").
- Cada tela responde no topo: o que é isso, por que importa, o que acontece
  se eu mudar.
- Padrão "deixar o agente decidir" na maioria dos campos.
- Onboarding e configurações são a MESMA coisa: o onboarding é as
  configurações em sequência, uma pergunta por tela, na primeira vez.
  Depois, tudo fica nas abas. Uma única fonte.
- Mudanças sensíveis pedem confirmação explícita, com uma frase explicando
  o que vai acontecer.
- v1 sem login nem múltiplos usuários, mas nada construído de um jeito que
  impeça isso depois.

### 9.2 Onboarding (perguntas)
Nome do perfil; personalidade (3 adjetivos + uma frase); objetivos (quantos
quiser, em ordem de prioridade); nicho(s) e proporção opcional; idioma dos
vídeos de origem; idioma de saída; pasta(s) de vídeos; seleção automática ou
manual; quantidade por rodada; aprovação ligada ou não. NÃO perguntar
público-alvo (trabalho do agente), contas de referência nem "o que não quer"
(atrapalham o aprendizado). O agente escreve a primeira versão de
`preferencias_usuario.md` e da identidade; o usuário aprova.

### 9.3 Configurações do perfil (nove abas)
1. Identidade: nome, @, personalidade, objetivos, idioma de saída, séries e
   quadros (agente cria; usuário renomeia/pausa/encerra).
2. Conteúdo: nichos e proporção, idioma de origem, pastas e estado da
   indexação, seleção automática/manual, quantidade por rodada, padrão
   mínimo de transformação (informativo, não desligável).
3. Produção: vozes por idioma (amostra, ativar/desativar, ordem de
   qualidade), legendas/capa/ritmo/sincronia ("agente decide" com ajuste
   opcional), serviço de voz principal e reserva com estado.
4. Publicação: aprovação (sensível), horários (agente ou fixos), fuso,
   horário da rodada automática, pasta de saída.
5. Métricas: conta TikTok vinculada (conectar/desconectar, última
   sincronização), envio manual de CSV/prints, dia e hora do lembrete.
6. Aprendizado: proporção explorar/explorar (70/30), fila de hipóteses,
   contas acompanhadas, versão do estilo e histórico.
7. Preferências do usuário: `preferencias_usuario.md` editável, com aviso de
   prioridade; histórico das destilações de conversas.
8. Memória do agente (leitura, botão "corrigir pela conversa"):
   `aprendizados.md`, `tendencias.md`, `publico.md`, `ganchos.md`.
9. Avançado: teto de custo e aviso; exportar/importar perfil; zona de risco
   com confirmação dupla (resetar aprendizados, apagar memória, apagar
   perfil).

Mudanças sensíveis (confirmação): desligar aprovação; trocar pastas de
origem; mudar nichos ou idioma de perfil com histórico (o agente avisa que
parte dos aprendizados pode deixar de valer); editar preferências em ponto
que contradiz um aprendizado forte (o agente mostra o conflito); desconectar
a conta; tudo na zona de risco.

### 9.4 Outras telas
Lista de perfis; indexação (progresso); revisão do lote; conversa com o
agente; relatório semanal; custo (global e por perfil); configurações
globais do app (chaves de API, serviços).

---

## 10. Estudo inicial (antes de fechar o motor de edição)
Feito com o usuário, amplo e profundo, gravado como base de
`aprendizados.md` e `tendencias.md`:
- O que mais funciona hoje em edição e retenção, por nicho.
- Estratégias de postagem atuais por nicho.
- Teste e ranking das vozes gratuitas por idioma.
- Verificação de que a obtenção de sons (yt-dlp) funciona no PC; plano B.
- Padrões de partida a validar: gancho nos primeiros 1-2s com texto grande;
  cortar tempo morto; legenda grande centralizada palavra por palavra com
  destaque; zoom em momentos-chave; final em loop; humor em 15-45s; capa com
  frame forte do próprio vídeo, sem quadro estático no início.

---

## 11. Escopo: v1 e v2
v1 (obrigatório): tudo das seções 2 a 7; métricas (8.1); experimentos com
uma variável por vez (8.2); curva de retenção; revisor independente;
relatório semanal; anti-alucinação; conversa com o agente; configurações
completas; estudo inicial.
v2: índice de momentos (4); catálogo de ganchos (8.2); comentários como
pauta (8.1); contas acompanhadas (8.3); versionamento de estilo (7.1) pode
entrar na v1 se for barato.
Descartado: aprendizado compartilhado entre perfis; perguntas de público,
referências e exclusões no onboarding; publicação automática por enquanto.

---

## 12. Perguntas em aberto (perguntar logo no início)
- Sistema operacional e se há GPU NVIDIA.
- Idiomas e nichos dos primeiros perfis.
- Chave da API do Claude e teto inicial de custo.

---

## 13. Ordem de construção
1. Perguntas da seção 12. Estrutura do projeto, pasta de perfil, SQLite.
2. Indexação, testada em pasta pequena.
3. Estudo inicial (seção 10).
4. Perfis (backend), onboarding, arquivos de memória, preferências.
5. Rotina de tendências e estratégia.
6. Motor de edição: plano JSON → ffmpeg; legendas; narração; batidas.
7. Revisor independente e padrão mínimo de transformação.
8. Pacote de publicação e tela de revisão.
9. Métricas (Display API + CSV/print), curva de retenção, experimentos,
   relatório semanal, lembrete.
10. Conversa com o agente e destilação de preferências.
11. Custo e teto.
12. Rodada automática (Agendador de Tarefas / cron).
13. Interface completa, com o usuário.
