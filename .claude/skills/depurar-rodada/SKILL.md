---
name: depurar-rodada
description: Roteiro para entender por que uma criação de post (rodada) falhou ou saiu estranha, a partir do log JSONL do perfil, do banco (MCP autora-sqlite), do roteiro.json e da pasta de trabalho do ffmpeg. Use quando a CLI ou o botão "Criar agora" devolver "Falhou", quando o post.md vier com avisos, ou quando o vídeo não bater com o roteiro.
---

# Depurar uma rodada

## 1. Onde olhar, nesta ordem
1. **Log do perfil**: `<dados>/perfis/<slug>/logs/<AAAA-MM-DD>.jsonl`. Filtre por
   `rodada_id`. Tipos: `rodada` (início/fim), `etapa` (iniciada/concluída/pulada),
   `decisao` (ideia do post e roteiro completos em `detalhe`), `servico` (cada chamada
   ao agente com tokens, e cada tentativa de legenda com reserva), `erro` (traceback
   e, para o ffmpeg, `detalhe.ffmpeg` com o stderr). O subagente `analista-logs` monta
   a linha do tempo por você.
2. **Banco** (MCP `autora-sqlite`, só leitura): `rodada` (estado, observação),
   `etapa_execucao` (qual etapa falhou e o erro), `post` (estado, pasta_saida),
   `decisao` (campo, escolha, motivo), `chamada_servico` (tokens, custo, resultado).
3. **Pacote**: `<dados>/saida/<slug>/<data>/<n>/roteiro.json` tem a ideia, o roteiro e
   a transcrição usada nas legendas; `post.md` tem a seção "Avisos".
4. **Pasta de trabalho do ffmpeg**: só existe se a rodada rodou com
   `manter_trabalho=True` (chame `renderizar` à mão) — ver skill `ffmpeg`.

## 2. Falhas típicas e o que significam
- "O agente não devolveu uma resposta válida depois de duas tentativas": veja os dois
  eventos `etapa` com `detalhe.problemas` (validação pydantic, clipe inexistente, ou
  padrão mínimo não comprovado no roteiro). Se o problema for recorrente, é método
  (texto da tarefa ou esquema), não o mandato (seção 14.5).
- "A assinatura não está conectada" / limite de uso: conexão do agente no app.
- "Nenhum vídeo disponível nas pastas do perfil": pastas não apontadas nesta máquina
  (`maquina.json`) ou todos os clipes já usados (`post_video`).
- "A montagem dos cortes falhou no ffmpeg": stderr em `detalhe.ffmpeg`; reproduza na
  pasta de trabalho (skill `ffmpeg`).
- "O vídeo final saiu diferente do esperado": `inspecionar` divergiu (duração, fps,
  tamanho); quase sempre um trecho cujo `-t` passou do clipe ou áudio mais curto.
- Legendas "indisponíveis": as duas opções do Whisper falharam (modelo não baixado,
  CUDA sem DLLs); o vídeo sai mesmo assim. Veja os eventos `servico` de "legendas".

## 3. Reproduzir sem gastar o agente
`tests/test_rodada.py` mostra como rodar `gerar()` com `ProvedorFalso` programado com
uma ideia e um roteiro fixos e com um renderizador falso. Para reproduzir só o motor,
`tests/edicao/test_renderizador.py` com clipes sintéticos. Para o caso real, salve a
`detalhe` do evento `decisao` da etapa `plano` como JSON e passe a `renderizar`.
