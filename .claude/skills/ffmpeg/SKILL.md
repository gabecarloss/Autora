---
name: ffmpeg
description: Convenções do motor de edição (src/autora/edicao) para quem for mudar ou estender a tradução do roteiro em ffmpeg, o ASS de legendas/textos, a capa ou a sondagem por ffprobe. Use ao mexer em filtros.py, legendas.py, renderizador.py, capa.py, ou ao depurar um vídeo que saiu errado.
---

# Motor de edição (ffmpeg)

Fonte: desenho do passo 2, verificado na build gyan 7.1.1 (Windows). Código em
`src/autora/edicao/`; testes em `tests/edicao/` (marcador `ffmpeg`, clipes sintéticos).

## Regras fixas
1. **Duas passagens.** Passagem 1 (`filtros.argumentos_passagem_1`) corta, enquadra,
   acelera e concatena SEM texto → `base.mp4` + `base.wav` (PCM). O Whisper transcreve o
   áudio já cortado (legendas nascem na linha do tempo final). Passagem 2 aplica um
   único ASS (`legendas.gerar_ass`: legendas + textos) com `ass=f=legendas.ass:fontsdir=fontes`
   e codifica `video.mp4` (libx264, crf 20, yuv420p, aac 160k, `+faststart`). Resolução, fps e
   codec vêm de `Plataforma.video` (`EspecificacaoVideo`), nunca de constante fixa; o
   motor recebe `espec` em toda função (filtros, legendas, capa, renderizador).
2. **Nada de caminho absoluto dentro de filtergraph.** `cwd` é a pasta `trabalho/`;
   script (`filtros_1.txt`, via `-filter_complex_script`), ASS e fontes são relativos.
   Os clipes entram por `-i` (argumento normal, fora do filtro).
3. **`setsar=1`, `fps=<fps da plataforma>`, `format=yuv420p` e
   `aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo` em TODO ramo**
   antes do `concat` (SAR diferente quebra o concat; fps/taxas diferentes desalinham).
   Áudio por trecho termina com `apad,atrim=end=<duração final>`; clipe sem áudio ou
   `manter_original=False` recebe uma entrada `anullsrc`.
4. **`-ss X -t D` antes de cada `-i`** (busca na entrada). Um trecho = uma entrada; o
   mesmo arquivo pode entrar várias vezes.
5. **Nunca `drawtext` com fonte por nome**: trava nesta build (fontconfig sem config).
   Texto só por ASS; fontes copiadas de `C:\Windows\Fonts` para `trabalho/fontes`
   (`fontes.preparar_pasta_fontes`); fonte ausente → libass usa a padrão e o log avisa.
6. **Zoom** com `scale=w='…':h='…':eval=frame` + `crop` fixo (`crop` não aceita `t`
   em w/h). `zoompan` fica como alternativa; tende a tremer.
7. **Resultado sempre conferido** com `ffmpeg.inspecionar` (resolução, fps e codec da
   plataforma, aac, duração ± 0,15 s) → `ErroRender` em divergência. Nunca vídeo errado em silêncio.
8. **Falha isolada**: `TodosFalharam` na transcrição → vídeo sem legendas + aviso no
   post.md; `ErroFfmpeg` → `ErroRender` com stderr no log do perfil.

## Depurar um vídeo
- `renderizar(..., manter_trabalho=True)` deixa `trabalho/` com `filtros_1.txt`,
  `base.mp4`, `base.wav`, `legendas.ass`, `fontes/`, `quadro_capa.png`.
- Rode o filtro à mão na pasta `trabalho`: `ffmpeg <args de filtros.argumentos_passagem_1>`;
  o stderr completo do ffmpeg está em `detalhe.ffmpeg` do evento de erro no log.
- Quadro em um instante: `ffmpeg -ss 1.0 -i video.mp4 -frames:v 1 -update 1 q.png`
  (o subagente `inspetor-video` faz isso e descreve o que vê).
- Clipes de teste: `edicao.sintetico.gerar_clipe_sintetico` (testsrc2 + tom); fala em
  português para o Whisper: `tests/edicao/fala.py` (SAPI do Windows).

## Ao mudar o roteiro (`edicao/plano.py`)
Mudança de campo = mudança no esquema que o agente recebe: passa pela regra 13 da skill
`chamada-ao-agente` (bateria da seção 14 antes de fixar). Atualize `rodada/plano.py`
(`_REGRAS`), `rodada/transformacao.py` se afetar o padrão mínimo, e os testes.
