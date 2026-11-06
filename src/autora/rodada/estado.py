"""Estado da criação em segundo plano, por perfil (botão "Criar agora").

Vive só em memória do processo do app; a trava do perfil (arquivo) é quem impede duas
criações ao mesmo tempo entre processos.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any, Literal

from autora.util.tempo import agora_iso

_log = logging.getLogger("autora")
MENSAGEM_ERRO_GENERICA = "Algo deu errado ao criar o post. Veja a linha do tempo em Bastidores."
Situacao = Literal["ocioso", "criando", "pronto", "falhou"]


@dataclass(frozen=True)
class EstadoCriacao:
    estado: Situacao = "ocioso"
    mensagem: str | None = None
    pasta_saida: str | None = None
    iniciado_em: str | None = None
    terminado_em: str | None = None

    def para_api(self) -> dict[str, Any]:
        return asdict(self)


_estados: dict[str, EstadoCriacao] = {}
_lock = threading.Lock()


def consultar(slug: str) -> EstadoCriacao:
    with _lock:
        return _estados.get(slug, EstadoCriacao())


def _iniciar(slug: str) -> bool:
    with _lock:
        if _estados.get(slug, EstadoCriacao()).estado == "criando":
            return False
        _estados[slug] = EstadoCriacao("criando", "Criando o post…", None, agora_iso(), None)
        return True


def _concluir(slug: str, ok: bool, mensagem: str, pasta_saida: str | None) -> None:
    with _lock:
        atual = _estados.get(slug, EstadoCriacao())
        _estados[slug] = EstadoCriacao(
            "pronto" if ok else "falhou", mensagem, pasta_saida, atual.iniciado_em, agora_iso()
        )


def iniciar_em_segundo_plano(
    slug: str, trabalho: Callable[[], tuple[bool, str, str | None]]
) -> bool:
    """Roda `trabalho()` numa thread. False se já há criação em andamento para o perfil."""
    if not _iniciar(slug):
        return False

    def _rodar() -> None:
        try:
            ok, mensagem, pasta = trabalho()
        except Exception as e:
            ok, mensagem, pasta = False, MENSAGEM_ERRO_GENERICA, None
            _log.exception("criação em segundo plano falhou: %s", e)
        _concluir(slug, ok, mensagem, pasta)

    threading.Thread(target=_rodar, name=f"criacao-{slug}", daemon=True).start()
    return True


def limpar() -> None:
    """Só para testes."""
    with _lock:
        _estados.clear()
