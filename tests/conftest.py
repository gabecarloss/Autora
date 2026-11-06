from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import keyring
import pytest
from keyring.backend import KeyringBackend

from autora.config import segredos


class CofreEmMemoria(KeyringBackend):
    """Substitui o Cofre de Credenciais do Windows nos testes."""

    priority = 1  # type: ignore[assignment]

    def __init__(self) -> None:
        super().__init__()
        self.itens: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self.itens.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self.itens[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        if (service, username) not in self.itens:
            raise keyring.errors.PasswordDeleteError(username)
        del self.itens[(service, username)]


@pytest.fixture(autouse=True)
def cofre() -> Iterator[CofreEmMemoria]:
    anterior = keyring.get_keyring()
    c = CofreEmMemoria()
    keyring.set_keyring(c)
    segredos._invalidar_cache()
    yield c
    keyring.set_keyring(anterior)
    segredos._invalidar_cache()


@pytest.fixture
def dados(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    raiz = tmp_path / "dados"
    raiz.mkdir()
    monkeypatch.setenv("AUTORA_DADOS", str(raiz))
    return raiz


RAIZ_REPO = Path(__file__).resolve().parents[1]


def secao_mandato_do_briefing() -> str:
    txt = (RAIZ_REPO / "BRIEFING.md").read_text(encoding="utf-8")
    ini = txt.index("### 3.1 O agente: mandato")
    fim = txt.index("\n---", ini)
    return txt[ini:fim].split("\n", 1)[1].strip("\n") + "\n"
