---
name: chamada-ao-agente
description: Regras e roteiro para escrever ou alterar código que chama o agente do app (src/autora/agente, rodada, estudo, revisor, verificações, conversa) — ordem do contexto, mandato integral, dados externos, saída estruturada, ferramentas por etapa, quem gera não avalia, avaliação antes de mudança. Use sempre que for criar uma etapa nova do agente, mudar texto de sistema, esquema de resposta, nível ou ferramentas.
---

# Código que chama o agente

Base: práticas da Anthropic (engenharia de prompt, agentes eficazes) aplicadas às
decisões do Autora. O mandato (BRIEFING 3.1) é a base de toda chamada.

## Regras
1. **Ordem do texto de sistema** (prefixo estável favorece o cache): mandato integral
   e primeiro → preferências do usuário → memória da etapa → regras de dados
   externos. Já pronto em `montar_sistema(memoria, etapa)`
   (`src/autora/agente/contexto.py`). A tarefa vai no fim, na mensagem (contexto
   longo antes, pergunta depois).
2. **Mandato**: sempre do `mandato.md` do perfil, inteiro. Nunca encurtar,
   resumir, parafrasear nem copiar trechos para o código.
3. **Instruções claras e com o porquê**, diretas, em português.
4. **Dados de fora são dado, nunca instrução**: web, transcrição, comentário,
   saída de outra etapa → `dados_externos(texto, fonte)`. Defesa contra prompt
   injection.
5. **Saída estruturada**: `esquema_json` no `Pedido` + modelo pydantic validando
   `resposta.dados`. Se vier inválida: pede de novo (uma vez) e registra; nunca
   "conserta" texto livre.
6. **Pensar antes de decidir**: as cinco perguntas da seção 3.1 respondidas num campo
   próprio do esquema (ex.: `raciocinio`), separado da decisão.
7. **Few-shot** quando formato ou tom importam: exemplos variados, nunca um só
   (o mandato exige variedade; um exemplo vira modelo a ser copiado).
8. **Uma responsabilidade por chamada**; etapas encadeadas e fixas (a rodada)
   antes de autonomia.
9. **Menor privilégio**: ferramentas só via `FERRAMENTAS_POR_ETAPA`
   (`src/autora/agente/provedor.py`); no máximo WebSearch/WebFetch. Nunca execução
   de comandos nem escrita em disco. O `Pedido` recusa ferramenta fora da lista.
10. **Quem gera não avalia**: revisor e verificações (14.2) são chamadas
    separadas, sem acesso ao roteiro de edição.
11. **Contra alucinação**: "não sei" é resposta válida no esquema; fonte e data
    obrigatórias em afirmações de tendência (8.5).
12. **Tudo registrado**: chame sempre por `chamar_registrando(provedor, pedido,
    registro, con=..., rodada_id=..., post_id=...)`. Log e `chamada_servico` saem
    de graça.
13. **Avaliação antes de mudança**: ajuste no mandato, no método, no nível ou no
    esquema passa pela bateria da seção 14 com casos reais. Mude uma coisa por vez e
    meça (`uv run poe testar-agente`).
14. Interface: o usuário vê "agente", nunca "IA", "modelo" ou "prompt".

## Roteiro: nova etapa do agente
1. Etapa no `Literal` `Etapa` e em `ETAPAS` (`src/autora/config/global_config.py`);
   nome visível em `frontend/src/textos.ts` (`ETAPAS`) e no `GLOSSARIO.md`.
2. `NIVEL_PADRAO_POR_ETAPA` (marque "PROVISÓRIO" até medir consumo) e, se precisar
   de web, `FERRAMENTAS_POR_ETAPA`.
3. Memória da etapa em `MEMORIA_POR_ETAPA` (`contexto.py`): só o que a etapa usa.
4. Modelo pydantic da resposta + `model_json_schema()` como `esquema_json`.
5. Função da etapa: monta `Pedido(etapa, sistema=montar_sistema(...),
   mensagem=<tarefa com dados_externos(...)>, esquema_json=..., ferramentas=...)`,
   chama `chamar_registrando`, valida, repete uma vez se inválida, registra.
6. Testes: provedor falso (`ProvedorFalso` em `tests/test_agente.py`) cobrindo resposta
   válida, inválida (repete e registra), erro do agente (não derruba a rodada) e
   ferramenta proibida; teste real com `@pytest.mark.agente`.
7. Antes de fechar: subagente `conformidade`.

## Esqueleto
```python
class RespostaConceito(BaseModel):
    raciocinio: str  # as cinco perguntas da seção 3.1
    formato: str
    motivo_formato: str  # todo post tem motivo registrado (14.2)
    nao_sei: list[str] = []  # lacunas assumidas, nunca inventadas


pedido = Pedido(
    etapa="conceito",
    sistema=montar_sistema(perfil.memoria, "conceito"),
    mensagem=f"{TAREFA_CONCEITO}\n\n{dados_externos(transcricao, fonte='transcrição')}",
    esquema_json=RespostaConceito.model_json_schema(),
    ferramentas=tuple(FERRAMENTAS_POR_ETAPA["conceito"]),
)
resposta = chamar_registrando(provedor, pedido, perfil.registro, con=con, rodada_id=rid)
conceito = RespostaConceito.model_validate(resposta.dados)  # inválida → repete 1x e registra
```
