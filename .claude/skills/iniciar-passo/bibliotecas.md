# Catálogo de bibliotecas candidatas, por passo

Lista viva, montada em 06/11/2026. **Nada aqui está aprovado.** Cada item passa pelo
subagente `pesquisador-tecnico` e pela pergunta ao usuário no passo em que entrar
(briefing 15.4). Ao adotar ou descartar, atualize a linha (status e motivo).

Legenda: (B) citada no briefing · (D) só desenvolvimento/testes.

## Já adotadas
- Pilha do passo 1: ver `CLAUDE.md` → "Pilha".
- (D) poethepoet, import-linter, deptry, pytest-cov, mcp: adotadas em 06/11/2026
  (ferramentas do Claude Code).

## Passo 2: versão mínima ponta a ponta
- (B) `edge-tts`: voz principal (seção 7.3).
- `tenacity`: nova tentativa com espera antes de cair para o reserva em
  `servicos/cadeia.py` (ex.: edge-tts sem limite publicado, seção 7.3).
- (D) `syrupy`: teste de snapshot do `post.md` e da lista de argumentos do ffmpeg.

## Passo 3: indexação
- `scenedetect` (PySceneDetect): cortes de cena.
- `opencv-python-headless`: quadros, nitidez, rosto simples.
- Já declaradas: `faster-whisper`, `imagehash`, `pillow`.

## Passo 5: perfis e onboarding (front)
- `react-hook-form` + `zod`: formulários do onboarding e das nove abas.
- (D) `openapi-typescript`: tipos do front gerados pela API do FastAPI (sem
  divergência entre pydantic e `api.ts`).
- (D) `msw`: simular a API nos testes do front.

## Passo 6: estudo diário
- (B) `yt-dlp`: só o áudio do som, para análise; nunca com a conta do usuário.
- `trafilatura`: texto limpo de páginas (notícias, artigos).
- `feedparser`: notícias por RSS.

## Passo 7: motor de edição
- (B) `librosa`: BPM, batidas e tempos fortes. **Atenção:** `madmom` (citada no
  briefing) está sem manutenção e é difícil de instalar no Windows com Python 3.11;
  avaliar `beat_this` como alternativa.
- `stable-ts`: tempo das palavras mais preciso sobre o Whisper.
- `mediapipe`: rosto e pose, para o recorte 9:16 no ponto de interesse.
- (D) `hypothesis`: testes de propriedade (plano JSON → argumentos do ffmpeg).
- Vozes reserva (B): `kokoro`, `piper-tts`, XTTS (`coqui-tts`). **Alerta:** a
  licença dos pesos do XTTS (Coqui Public Model License) não permite uso comercial.
  Pesa se o produto for vendido.

## Passo 10: métricas
- (D) `respx`: simular a TikTok Display API (sobre httpx) nos testes.

## Passos 12 e 14: custo, Bastidores, Comparar perfis (front)
- `recharts`: gráficos.

## Passo 13: rodada automática
- (D) `time-machine`: testes de horário, pausa e retenção.
- Agendador de Tarefas: via `schtasks` (biblioteca padrão), sem dependência nova.
