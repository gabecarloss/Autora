---
name: novo-servico-com-reserva
description: Roteiro para integrar um serviço externo ou local com principal e reserva (voz, legenda, download de som, transcrição, qualquer coisa que pode falhar) usando executar_com_reserva, log em linguagem direta e falha isolada. Use ao adicionar edge-tts, Kokoro, Piper, XTTS, Whisper, yt-dlp ou outro serviço.
---

# Serviço com reserva

Decisões fixas (CLAUDE.md): falha isolada (um serviço que falha cai para o reserva;
nenhum erro pontual derruba a rodada); voz e legenda **só gratuitos** (7.3); serviço
pago só se o usuário habilitar; logs de toda chamada a serviço.

## Peças que já existem
- `executar_com_reserva(funcao, opcoes, registro, etapa=..., rodada_id=...,
  post_id=...)` em `src/autora/servicos/cadeia.py`: tenta cada `Opcao(nome,
  nome_amigavel, executar)` em ordem, registra cada falha e cada sucesso
  (ex.: "O serviço de voz (voz principal) falhou e o voz reserva vai assumir."), devolve
  `Resultado(valor, usado, reserva, falhas)` ou levanta `TodosFalharam`.
- `Registro` do perfil (`src/autora/registro/log.py`) mascara segredos.

## Passos
1. Antes: `pesquisador-tecnico` para a biblioteca (licença comercial, Windows,
   gratuito) e pergunta ao usuário.
2. Código genérico em `src/autora/servicos/<funcao>.py` (ex.: `voz.py`): uma função
   por implementação, com a mesma assinatura, devolvendo o mesmo tipo (ex.: caminho
   relativo do arquivo gerado). Nada de TikTok aqui; o que for específico de
   plataforma vai em `autora/plataformas/tiktok/`.
3. Monte a cadeia: `[Opcao("edge-tts", "voz principal", ...), Opcao("kokoro", "voz
   reserva", ...)]`. O `nome` é técnico (log); o `nome_amigavel` é o texto da tela
   Bastidores (sem jargão, nomes do GLOSSARIO).
4. Limites e esperas: nova tentativa com espera curta **dentro** da opção (se
   `tenacity` tiver sido adotada; ver catálogo) e só depois cair para a reserva.
   Fila com pausas para serviço sem limite publicado (edge-tts, 7.3).
5. Quem chama trata `TodosFalharam` sem derrubar a rodada: o vídeo vai para
   "falhou" com motivo registrado e a rodada segue.
6. Registre a escolha no post quando o briefing pede (ex.: voz usada, 7.3).
7. Dependência pesada ou opcional (modelos locais): import tardio dentro da
   função, para o app abrir mesmo sem ela instalada; ausência vira falha da opção
   (cai para a próxima), não erro de importação.
8. Testes (sem rede): principal ok; principal falha → reserva assume (confira no log
   "... falhou e o <nome_amigavel da reserva> vai assumir."); todos falham → `TodosFalharam` e a rodada continua;
   nenhum segredo no log. Teste com serviço real só com marcador próprio.
