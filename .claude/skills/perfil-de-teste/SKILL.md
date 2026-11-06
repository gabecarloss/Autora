---
name: perfil-de-teste
description: Cria (ou recria) um perfil de teste na pasta de dados do app com uma biblioteca sintética de clipes gerados pelo ffmpeg e descrições em descricoes.json, para rodar a criação de um post de ponta a ponta (CLI ou botão "Criar agora") numa máquina sem vídeos reais. Use quando precisar exercitar a rodada, o motor ou o app sem biblioteca real.
---

# Perfil de teste com biblioteca sintética

Nada aqui toca em perfis reais: o perfil chama-se `teste-sintetico` e a biblioteca
fica em `<dados>/biblioteca_sintetica/`. `<dados>` é `%USERPROFILE%\Autora` ou
`AUTORA_DADOS`.

## Passos
1. Confirme o ffmpeg: `uv run python -c "from autora.edicao.ffmpeg import localizar_ffmpeg; print(localizar_ffmpeg())"`.
2. Gere os clipes e o perfil (script de desenvolvimento, não faz parte do app):
   ```powershell
   uv run python - <<'EOF'
   import json
   from pathlib import Path
   from autora.config.global_config import pasta_dados
   from autora.edicao.sintetico import gerar_clipe_sintetico
   from autora.perfil.perfil import Perfil, PerfilJaExiste
   from autora.biblioteca.ficha import registrar_pasta

   dados = pasta_dados()
   pasta = dados / "biblioteca_sintetica"
   gerar_clipe_sintetico(pasta / "vertical.mp4", largura=1080, altura=1920, duracao_s=6)
   gerar_clipe_sintetico(pasta / "horizontal.mp4", largura=1920, altura=1080, duracao_s=8, fps=25, taxa_audio=44100, frequencia_hz=660)
   gerar_clipe_sintetico(pasta / "mudo.mp4", largura=1080, altura=1920, duracao_s=4, com_audio=False)
   (pasta / "descricoes.json").write_text(json.dumps({
       "vertical.mp4": "Padrão de teste vertical com barras coloridas e um tom contínuo.",
       "horizontal.mp4": "Padrão de teste horizontal com contador de quadros e um tom mais agudo.",
       "mudo.mp4": "Padrão de teste vertical curto, sem som.",
   }, ensure_ascii=False, indent=1), encoding="utf-8")
   try:
       perfil = Perfil.criar(dados, "teste-sintetico", "Perfil de teste")
   except PerfilJaExiste:
       perfil = Perfil.abrir(dados, "teste-sintetico")
   print("pasta vinculada como", registrar_pasta(perfil, dados, pasta))
   EOF
   ```
   Para fala em português (testa o Whisper): gere um wav com `tests/edicao/fala.py`
   (`gerar_fala_wav`) e passe `audio_wav=` ao `gerar_clipe_sintetico`.
3. Com o agente conectado no app (Configurações globais → Agente):
   `uv run autora gerar teste-sintetico --teste` ou o botão "Criar agora" na tela Perfis.
4. Saída em `<dados>/saida/teste-sintetico/<data>/<n>/`: `video.mp4`, `post.md`,
   `capa.jpg`, `roteiro.json`. Linha do tempo: `<dados>/perfis/teste-sintetico/logs/`
   e o MCP `autora-sqlite` (`consultar("teste-sintetico", "SELECT ...")`).
5. Para recomeçar do zero (clipes usados não voltam): apague só a pasta
   `<dados>/perfis/teste-sintetico/` (confirme com o usuário; o hook bloqueia apagar a
   pasta de dados inteira).

As descrições em `descricoes.json` são dado de teste (o que a cena mostra), não decisão
criativa: quem decide gancho, formato e corte é o agente.
