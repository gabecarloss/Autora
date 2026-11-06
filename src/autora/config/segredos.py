"""Segredos do app no Cofre de Credenciais do Windows (via keyring).

Regra do briefing (15.6): chaves nunca dentro de um perfil, nunca em texto puro em
disco, nunca em logs ou exportações. Este é o ÚNICO lugar que lê ou grava segredos.
"""

from __future__ import annotations

import contextlib
import re
import threading
from typing import Final, Literal

import keyring
import keyring.errors

SERVICO: Final = "Autora"

NomeSegredo = Literal["agente_token_assinatura", "agente_chave_api"]
NOMES: Final[tuple[NomeSegredo, ...]] = ("agente_token_assinatura", "agente_chave_api")

_lock = threading.Lock()
_cache_valores: list[str] | None = None

# Padrões conhecidos de credenciais, mascarados mesmo que não estejam no keyring.
PADROES_SEGREDO: Final = (
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{16,}"),
    re.compile(r"(?i)(api[_-]?key|token|secret|senha)(\"?\s*[:=]\s*\"?)[A-Za-z0-9._\-]{16,}"),
)


def definir(nome: NomeSegredo, valor: str) -> None:
    if not valor:
        raise ValueError("segredo vazio")
    keyring.set_password(SERVICO, nome, valor)
    _invalidar_cache()


def obter(nome: NomeSegredo) -> str | None:
    return keyring.get_password(SERVICO, nome)


def apagar(nome: NomeSegredo) -> None:
    with contextlib.suppress(keyring.errors.PasswordDeleteError):
        keyring.delete_password(SERVICO, nome)
    _invalidar_cache()


def _invalidar_cache() -> None:
    global _cache_valores
    with _lock:
        _cache_valores = None


def valores_conhecidos() -> list[str]:
    """Valores atuais dos segredos, para a máscara dos logs. Em cache até mudar."""
    global _cache_valores
    with _lock:
        if _cache_valores is None:
            valores: list[str] = []
            for nome in NOMES:
                try:
                    v = keyring.get_password(SERVICO, nome)
                except keyring.errors.KeyringError:
                    v = None
                if v and len(v) >= 6:
                    valores.append(v)
            _cache_valores = valores
        return list(_cache_valores)


def mascarar_texto(texto: str) -> str:
    """Remove qualquer segredo conhecido ou com cara de segredo de um texto."""
    for v in valores_conhecidos():
        texto = texto.replace(v, "***")
    for padrao in PADROES_SEGREDO:
        if padrao.groups >= 2:
            texto = padrao.sub(lambda m: f"{m.group(1)}{m.group(2)}***", texto)
        else:
            texto = padrao.sub("***", texto)
    return texto
