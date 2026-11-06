"""Serviço principal → reservas (CLAUDE.md: "um serviço que falha cai para o reserva").

Cada tentativa e cada troca vão para o log em linguagem direta, como pede a tela
Bastidores: "o serviço de voz principal falhou e o reserva assumiu".
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from autora.registro.log import Registro

T = TypeVar("T")


@dataclass(frozen=True)
class Opcao(Generic[T]):
    nome: str  # identificador técnico (ex.: "edge-tts")
    nome_amigavel: str  # texto da interface (ex.: "voz principal")
    executar: Callable[[], T]


class TodosFalharam(RuntimeError):
    def __init__(self, funcao: str, erros: list[tuple[str, BaseException]]) -> None:
        self.erros = erros
        super().__init__(f"Nenhum serviço de {funcao} funcionou ({len(erros)} tentativas).")


@dataclass
class Resultado(Generic[T]):
    valor: T
    usado: str
    reserva: bool
    falhas: list[tuple[str, BaseException]]


def executar_com_reserva(
    funcao: str,
    opcoes: Sequence[Opcao[T]],
    registro: Registro,
    *,
    etapa: str | None = None,
    rodada_id: int | None = None,
    post_id: int | None = None,
) -> Resultado[T]:
    """Tenta cada opção em ordem; a primeira que funcionar vence."""
    if not opcoes:
        raise ValueError("nenhuma opção de serviço")
    falhas: list[tuple[str, BaseException]] = []
    ctx: dict[str, Any] = {"etapa": etapa, "rodada_id": rodada_id, "post_id": post_id}
    for i, opcao in enumerate(opcoes):
        inicio = time.monotonic()
        try:
            valor = opcao.executar()
        except Exception as e:
            falhas.append((opcao.nome, e))
            proxima = opcoes[i + 1].nome_amigavel if i + 1 < len(opcoes) else None
            msg = f"O serviço de {funcao} ({opcao.nome_amigavel}) falhou"
            msg += f" e o {proxima} vai assumir." if proxima else " e não há outro reserva."
            registro.registrar(
                "servico",
                msg,
                detalhe={"servico": opcao.nome, "erro": f"{type(e).__name__}: {e}"},
                duracao_ms=int((time.monotonic() - inicio) * 1000),
                **ctx,
            )
            continue
        registro.registrar(
            "servico",
            f"Serviço de {funcao} ({opcao.nome_amigavel}) funcionou.",
            detalhe={"servico": opcao.nome, "reserva": i > 0},
            duracao_ms=int((time.monotonic() - inicio) * 1000),
            **ctx,
        )
        return Resultado(valor, opcao.nome, i > 0, falhas)
    raise TodosFalharam(funcao, falhas)
