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

Início. Nenhuma pergunta da seção 12 do briefing foi respondida ainda;
comece por elas.

<!-- Atualizar ao fim de cada etapa: etapa atual, comandos para rodar,
estrutura de pastas, decisões novas tomadas com o usuário (com data). -->
