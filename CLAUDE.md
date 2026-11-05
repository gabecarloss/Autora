# Autora

Agente local que transforma uma biblioteca de vídeos em conteúdo autoral
para TikTok (e outras redes no futuro). Cada perfil opera uma conta, estuda
tendências diariamente, edita, gera material próprio quando necessário, e
aprende com métricas e com o usuário.

## Antes de qualquer tarefa

Leia `BRIEFING.md` por inteiro. Ele define o projeto, as decisões já
tomadas, o mandato do agente (seção 3.1), a arquitetura, a interface e a
ordem de construção. Tudo que está lá foi decidido com o usuário e não
deve ser reinterpretado.

## Regras de trabalho

- Decisões não cobertas pelo briefing: pergunte ao usuário. Não assuma.
- Siga a ordem de construção da seção 13. O passo 2 (versão mínima com um
  vídeo real postado) vem antes de qualquer sofisticação.
- O mandato (seção 3.1) é a base de toda chamada ao modelo feita pelo
  sistema. Nunca o encurte nem o parafraseie no código; carregue o arquivo
  `mandato.md` do perfil.
- Serviços de voz e legenda são gratuitos (seção 7.3). Não introduza
  serviços pagos sem o usuário habilitar explicitamente.
- Interface sem jargão: "agente", nunca "IA", "modelo" ou "prompt" em
  texto visível ao usuário (seção 9.1).
- Logs desde o primeiro commit: toda etapa, decisão, chamada a serviço e
  erro vai para o log do perfil (seção 9.5). Chaves de API nunca aparecem
  em logs.
- Cada perfil é uma pasta portátil (seção 3). Nada do perfil pode ficar
  preso a caminhos absolutos da máquina ou a configuração global.
- Separe o que é específico do TikTok do que é genérico (seção 1), para
  receber outras plataformas depois.
- Ao concluir uma etapa da seção 13, diga ao usuário o que foi feito, o
  que ficou pendente e qual é o próximo passo.

## Estado do projeto

Início. Nenhuma pergunta da seção 12 do briefing foi respondida ainda;
comece por elas.

<!-- O Claude Code deve atualizar esta seção conforme o projeto avança:
etapa atual, comandos para rodar, estrutura de pastas, decisões novas
tomadas com o usuário (com data). -->
