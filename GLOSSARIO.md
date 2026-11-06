# Glossário

Mapeia cada termo interno (código, briefing, logs) para o nome usado na interface
(seção 15.5 do briefing). **A interface só usa a coluna "Na interface".**

Proibido em texto visível: "IA", "modelo", "prompt", "pipeline", "rodada", e
jargão técnico em geral (token, API, endpoint, fallback). A checagem
`tests/test_vocabulario.py` barra esses termos nas telas.

Status: **proposta**. Os nomes marcados com (?) aguardam a confirmação do usuário.

## Agente e operação

| Interno | Na interface | Observação |
|---|---|---|
| agente | agente | Sempre "agente", nunca "IA" ou "modelo". |
| mandato (`mandato.md`) | missão do agente (?) | Texto da seção 3.1. |
| rodada | lote (?) | Uma execução de criação de posts. O briefing já fala em "revisão do lote". |
| rodada automática / modo automático | criação automática | Seção 15.1. |
| modo manual | criação manual | |
| gerar agora | Criar agora | Botão por perfil. Funciona mesmo com o sistema pausado. |
| pausar / ligar o sistema | Pausar / Ligar | Indicador: Ligado / Pausado / Manual. |
| pausar este perfil | Pausar este perfil | |
| proteção contra acúmulo | (alerta) "Criação pausada: há lotes esperando sua revisão" (?) | Seção 15.2. |
| conexão do agente (assinatura) | Assinatura Claude | |
| conexão do agente (chave da API) | Chave de acesso da conta de desenvolvedor Claude | |
| token da assinatura (`setup-token`) | código de acesso da assinatura | |
| nível (Haiku / Sonnet / Opus) | Nível do agente: Rápido / Equilibrado / Máximo / Deixar o agente decidir | Nunca o nome técnico. |
| custo equivalente (`total_cost_usd`) | custo equivalente | Com a assinatura, é o quanto custaria na conta de desenvolvedor. |
| teto de custo | limite de gasto (?) | Seção 7.4. |

## Etapas da rodada (seção 5)

| Interno | Na interface |
|---|---|
| estudo (estudo diário de tendências) | Estudo do dia |
| seleção de material | Escolha do material (?) |
| conceito | Ideia do post |
| plano de edição (JSON) | Roteiro de edição |
| revisor (independente) | Revisor |
| verificações automáticas | Checagens |
| verificações manuais | Suas avaliações (?) |
| pacote de publicação | post pronto (?) |
| tela de revisão | Revisão do lote |
| indexação | Organização da biblioteca |
| índice de momentos | Melhores momentos |

## Memória do perfil (seção 3)

| Interno | Na interface |
|---|---|
| `preferencias_usuario.md` | Suas preferências |
| `aprendizados.md` | O que o agente aprendeu |
| `tendencias.md` | Tendências |
| `publico.md` | Quem é o público |
| `ganchos.md` | Ganchos |
| `testes.md` | Regras de checagem |
| banco de material gerado | Material criado pelo agente |
| fonte de material: livre / só pasta / só geração | Origem do material: Livre / Só da pasta / Só criado pelo agente |
| hipótese | ideia a testar (?) |
| proporção 70/30 (explorar) | Repetir o que funciona / Experimentar |
| versão de estilo | estilo de edição (versão N) |
| painel de dispersão | Foco do agente (?) |
| frase de afunilamento | O que esta conta faz de melhor |
| regime de conta nova | Conta nova |

## Telas técnicas

| Interno | Na interface |
|---|---|
| log / linha do tempo | Linha do tempo |
| tela Bastidores | Bastidores |
| serviço principal / reserva (fallback) | principal / reserva ("o serviço de voz principal falhou e o reserva assumiu") |
| cópia de segurança (backup) | Cópia de segurança |
| exportar / importar perfil | Exportar perfil / Importar perfil |
