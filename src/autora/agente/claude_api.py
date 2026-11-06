"""Conexão por chave da API do Claude, via SDK oficial `anthropic`.

Obrigatória se o produto for vendido (a assinatura é pessoal). A chave vem do
keyring e só existe em memória durante a chamada.

- Texto de base com cache (economiza nas chamadas seguidas do mesmo perfil).
- Fallback do lado do servidor (`fallbacks="default"`) ligado nos níveis
  equilibrado e máximo: se o modelo recusar por política, outro assume na mesma chamada.
- Pesquisa e leitura na web pelas ferramentas de servidor, só nas etapas permitidas.
- Custo calculado pelo uso devolvido e pela tabela de preços abaixo.
"""

from __future__ import annotations

import json
import time
from typing import Any, Final

import anthropic

from autora.agente.provedor import (
    MODELO_POR_NIVEL_API,
    AgenteNaoConectado,
    ErroAgente,
    LimiteDeUso,
    Pedido,
    Resposta,
    RespostaInvalida,
    resolver_nivel,
)

# US$ por milhão de tokens: (entrada, saída, leitura de cache). Escrita de cache = 1,25 x entrada.
# Fonte: referência da API (cache de 2026-10-06). O valor de leitura de cache do Haiku 5.5
# não constava; usamos 10% da entrada como estimativa.
PRECOS: Final[dict[str, tuple[float, float, float]]] = {
    "claude-opus-5-5": (4.00, 20.00, 0.20),
    "claude-sonnet-5-5": (2.00, 10.00, 0.20),
    "claude-haiku-5-5": (0.10, 0.50, 0.01),
}
PRECO_PESQUISA_WEB: Final = 10.00 / 1000  # US$ por pesquisa
COM_FALLBACK: Final = {"claude-opus-5-5", "claude-sonnet-5-5"}
FERRAMENTAS_SERVIDOR: Final[dict[str, dict[str, str]]] = {
    "WebSearch": {"type": "web_search_20260209", "name": "web_search"},
    "WebFetch": {"type": "web_fetch_20260209", "name": "web_fetch"},
}
MAX_CONTINUACOES: Final = 8


def calcular_custo(modelo: str, uso: Any) -> float | None:
    if modelo not in PRECOS:
        return None
    p_in, p_out, p_cache = PRECOS[modelo]
    entrada = getattr(uso, "input_tokens", 0) or 0
    escrita = getattr(uso, "cache_creation_input_tokens", 0) or 0
    leitura = getattr(uso, "cache_read_input_tokens", 0) or 0
    saida = getattr(uso, "output_tokens", 0) or 0
    custo = (entrada * p_in + escrita * p_in * 1.25 + leitura * p_cache + saida * p_out) / 1e6
    servidor = getattr(uso, "server_tool_use", None)
    pesquisas = getattr(servidor, "web_search_requests", 0) or 0
    return round(custo + pesquisas * PRECO_PESQUISA_WEB, 6)


class ProvedorChave:
    nome = "chave"

    def __init__(self, chave: str) -> None:
        self._chave = chave

    def chamar(self, pedido: Pedido) -> Resposta:
        modelo = MODELO_POR_NIVEL_API[resolver_nivel(pedido.etapa, pedido.nivel)]
        cliente = anthropic.Anthropic(
            api_key=self._chave, max_retries=2, timeout=float(pedido.tempo_limite_s)
        )
        mensagens: list[dict[str, Any]] = [{"role": "user", "content": pedido.mensagem}]
        params: dict[str, Any] = {
            "model": modelo,
            "max_tokens": 16000,
            "system": [
                {"type": "text", "text": pedido.sistema, "cache_control": {"type": "ephemeral"}}
            ],
        }
        if pedido.ferramentas:
            params["tools"] = [FERRAMENTAS_SERVIDOR[f] for f in pedido.ferramentas]
        if pedido.esquema_json is not None:
            params["output_config"] = {
                "format": {"type": "json_schema", "schema": pedido.esquema_json}
            }

        inicio = time.monotonic()
        tok_in = tok_out = tok_cache = 0
        custo = 0.0
        resposta: Any = None
        try:
            for _ in range(MAX_CONTINUACOES):
                if modelo in COM_FALLBACK:
                    resposta = cliente.beta.messages.create(
                        betas=["server-side-fallback-2026-07-01"],
                        fallbacks="default",
                        messages=mensagens,  # type: ignore[arg-type]
                        **params,
                    )
                else:
                    resposta = cliente.messages.create(messages=mensagens, **params)  # type: ignore[arg-type]
                uso = resposta.usage
                tok_in += (uso.input_tokens or 0) + (uso.cache_creation_input_tokens or 0)
                tok_out += uso.output_tokens or 0
                tok_cache += uso.cache_read_input_tokens or 0
                custo += calcular_custo(resposta.model, uso) or 0.0
                if resposta.stop_reason != "pause_turn":
                    break
                # Ferramenta de servidor pausou; reenviar para continuar.
                mensagens.append({"role": "assistant", "content": resposta.content})
        except anthropic.AuthenticationError as e:
            raise AgenteNaoConectado("A chave da API não foi aceita.", str(e)) from e
        except anthropic.PermissionDeniedError as e:
            raise AgenteNaoConectado("A chave da API não tem permissão.", str(e)) from e
        except anthropic.RateLimitError as e:
            espera = e.response.headers.get("retry-after")
            raise LimiteDeUso(
                "O limite de uso da API foi atingido.",
                str(e),
                int(espera) if espera and espera.isdigit() else None,
            ) from e
        except anthropic.APIStatusError as e:
            raise ErroAgente("O serviço do agente devolveu um erro.", str(e)) from e
        except anthropic.APIConnectionError as e:
            raise ErroAgente("Sem conexão com o serviço do agente.", str(e)) from e

        if resposta.stop_reason == "refusal":
            raise ErroAgente(
                "O agente se recusou a responder este pedido.", str(resposta.stop_details)
            )
        texto = "".join(b.text for b in resposta.content if b.type == "text")
        dados: Any | None = None
        if pedido.esquema_json is not None:
            try:
                dados = json.loads(texto)
            except json.JSONDecodeError as e:
                raise RespostaInvalida(
                    "O agente não devolveu os dados no formato pedido.", texto[:2000]
                ) from e
        return Resposta(
            texto=texto,
            dados=dados,
            modelo=resposta.model,
            tokens_entrada=tok_in,
            tokens_saida=tok_out,
            tokens_cache=tok_cache,
            custo_usd=round(custo, 6),
            duracao_ms=int((time.monotonic() - inicio) * 1000),
        )
