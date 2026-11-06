"""Interface única para chamar o agente, qualquer que seja a conexão.

Duas conexões na v1 (configuradas pelo app, tela Configurações globais → Agente):
- assinatura Claude, via Claude Code em modo não interativo (claude_assinatura.py);
- chave da API do Claude, via SDK oficial (claude_api.py).
Outros provedores entram implementando ProvedorAgente.

Toda chamada passa por `chamar_registrando`, que grava o log e, quando há perfil,
a linha em chamada_servico (base da aba Custo e da tela Bastidores).
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass, field
from typing import Any, Final, Protocol

from autora.config.global_config import Etapa, Nivel
from autora.registro.log import Registro
from autora.util.tempo import agora_iso

NivelConcreto = str  # "rapido" | "equilibrado" | "maximo"

# Nomes usados por cada conexão para cada nível. Na interface aparece só "nível".
MODELO_POR_NIVEL_ASSINATURA: Final = {"rapido": "haiku", "equilibrado": "sonnet", "maximo": "opus"}
MODELO_POR_NIVEL_API: Final = {
    "rapido": "claude-haiku-5-5",
    "equilibrado": "claude-sonnet-5-5",
    "maximo": "claude-opus-5-5",
}

# PROVISÓRIO: o nível padrão de cada etapa será fixado no passo 2, depois de medir
# o consumo real (decisão registrada no plano do passo 1).
NIVEL_PADRAO_POR_ETAPA: Final[dict[str, NivelConcreto]] = {
    "estudo": "equilibrado",
    "conceito": "maximo",
    "plano": "equilibrado",
    "revisor": "maximo",
    "verificacoes": "equilibrado",
    "indexacao": "rapido",
    "teste": "rapido",
}

# Ferramentas que o agente pode usar em cada etapa. Nunca Bash, Edit, Write etc.
FERRAMENTAS_PERMITIDAS: Final = frozenset({"WebSearch", "WebFetch"})
FERRAMENTAS_POR_ETAPA: Final[dict[str, frozenset[str]]] = {
    "estudo": FERRAMENTAS_PERMITIDAS,
    "conceito": FERRAMENTAS_PERMITIDAS,  # localizar o som (seção 7.2)
}


def resolver_nivel(etapa: Etapa, nivel: Nivel) -> NivelConcreto:
    return NIVEL_PADRAO_POR_ETAPA[etapa] if nivel == "automatico" else nivel


@dataclass(frozen=True)
class Pedido:
    etapa: Etapa
    sistema: str
    mensagem: str
    ferramentas: tuple[str, ...] = ()
    esquema_json: dict[str, Any] | None = None
    nivel: Nivel = "automatico"
    tempo_limite_s: int = 900

    def __post_init__(self) -> None:
        permitidas = FERRAMENTAS_POR_ETAPA.get(self.etapa, frozenset())
        proibidas = set(self.ferramentas) - permitidas
        if proibidas:
            raise ValueError(
                f"ferramentas não permitidas na etapa {self.etapa}: {sorted(proibidas)}"
            )


@dataclass
class Resposta:
    texto: str
    dados: Any | None
    modelo: str
    tokens_entrada: int
    tokens_saida: int
    tokens_cache: int
    custo_usd: float | None
    duracao_ms: int
    extras: dict[str, Any] = field(default_factory=dict)


class ErroAgente(RuntimeError):
    """Falha ao chamar o agente. `mensagem_amigavel` vai para a interface."""

    def __init__(self, mensagem_amigavel: str, detalhe: str | None = None) -> None:
        super().__init__(mensagem_amigavel)
        self.mensagem_amigavel = mensagem_amigavel
        self.detalhe = detalhe


class AgenteNaoConectado(ErroAgente):
    pass


class LimiteDeUso(ErroAgente):
    def __init__(self, mensagem: str, detalhe: str | None = None, espera_s: int | None = None):
        super().__init__(mensagem, detalhe)
        self.espera_s = espera_s


class RespostaInvalida(ErroAgente):
    pass


class ProvedorAgente(Protocol):
    nome: str

    def chamar(self, pedido: Pedido) -> Resposta: ...


def chamar_registrando(
    provedor: ProvedorAgente,
    pedido: Pedido,
    registro: Registro,
    *,
    con: sqlite3.Connection | None = None,
    rodada_id: int | None = None,
    post_id: int | None = None,
) -> Resposta:
    """Chama o agente e registra tudo (log + chamada_servico quando há perfil)."""
    nivel = resolver_nivel(pedido.etapa, pedido.nivel)
    inicio = time.monotonic()
    ctx: dict[str, Any] = {"etapa": pedido.etapa, "rodada_id": rodada_id, "post_id": post_id}
    try:
        resp = provedor.chamar(pedido)
    except ErroAgente as e:
        ms = int((time.monotonic() - inicio) * 1000)
        registro.registrar(
            "servico",
            f"O agente não respondeu: {e.mensagem_amigavel}",
            detalhe={"provedor": provedor.nome, "nivel": nivel, "erro": e.detalhe},
            duracao_ms=ms,
            **ctx,
        )
        if con is not None:
            _gravar(con, provedor.nome, nivel, None, ms, "falhou", e.mensagem_amigavel, ctx)
        raise
    registro.registrar(
        "servico",
        "O agente respondeu.",
        detalhe={
            "provedor": provedor.nome,
            "nivel": nivel,
            "modelo": resp.modelo,
            "tokens_entrada": resp.tokens_entrada,
            "tokens_saida": resp.tokens_saida,
            "tokens_cache": resp.tokens_cache,
        },
        duracao_ms=resp.duracao_ms,
        custo_usd=resp.custo_usd,
        **ctx,
    )
    if con is not None:
        _gravar(con, provedor.nome, nivel, resp, resp.duracao_ms, "ok", None, ctx)
    return resp


def _gravar(
    con: sqlite3.Connection,
    provedor: str,
    nivel: str,
    resp: Resposta | None,
    duracao_ms: int,
    resultado: str,
    erro: str | None,
    ctx: dict[str, Any],
) -> None:
    con.execute(
        """INSERT INTO chamada_servico
           (rodada_id, post_id, etapa, servico, provedor, nivel, tokens_entrada, tokens_saida,
            tokens_cache, custo_usd, duracao_ms, resultado, erro, criada_em)
           VALUES (?, ?, ?, 'agente', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            ctx["rodada_id"],
            ctx["post_id"],
            ctx["etapa"],
            provedor,
            nivel,
            resp.tokens_entrada if resp else None,
            resp.tokens_saida if resp else None,
            resp.tokens_cache if resp else None,
            resp.custo_usd if resp else None,
            duracao_ms,
            resultado,
            erro,
            agora_iso(),
        ),
    )
