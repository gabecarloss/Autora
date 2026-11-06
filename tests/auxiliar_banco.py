"""Ajuda de testes: `Perfil.conectar()` é gerenciador de contexto; aqui vira conexão com close()."""

from __future__ import annotations

from typing import Any

from autora.perfil.perfil import Perfil


class ConexaoAberta:
    def __init__(self, perfil: Perfil) -> None:
        self._cm = perfil.conectar()
        self._con = self._cm.__enter__()

    def __getattr__(self, nome: str) -> Any:
        return getattr(self._con, nome)

    def close(self) -> None:
        self._cm.__exit__(None, None, None)


def abrir(perfil: Perfil) -> Any:
    return ConexaoAberta(perfil)
