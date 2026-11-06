"""Catálogo de fontes para textos, legendas e capa.

PROVISÓRIO: fontes do Windows (sem arquivo de fonte no repositório). O libass recebe as
cópias dos .ttf em `fontsdir` e acha a fonte pelo nome; o Pillow usa o arquivo direto.
Se um arquivo não existir (outra máquina, CI), o libass cai na fonte padrão e o log
avisa; nunca é erro.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Final


@dataclass(frozen=True)
class Fonte:
    chave: str
    nome_ass: str  # nome de família que o libass procura
    negrito: bool
    arquivo: str  # nome do .ttf na pasta de fontes do sistema


FONTES: Final[dict[str, Fonte]] = {
    "impact": Fonte("impact", "Impact", False, "impact.ttf"),
    "arial_black": Fonte("arial_black", "Arial Black", False, "ariblk.ttf"),
    "arial_bold": Fonte("arial_bold", "Arial", True, "arialbd.ttf"),
    "bahnschrift": Fonte("bahnschrift", "Bahnschrift", False, "bahnschrift.ttf"),
    "segoe_bold": Fonte("segoe_bold", "Segoe UI", True, "segoeuib.ttf"),
}
CHAVES: Final[tuple[str, ...]] = tuple(FONTES)


def pasta_fontes_sistema() -> Path:
    return Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"


def arquivo_fonte(chave: str) -> Path | None:
    caminho = pasta_fontes_sistema() / FONTES[chave].arquivo
    return caminho if caminho.is_file() else None


def preparar_pasta_fontes(trabalho: Path, chaves: set[str] | None = None) -> tuple[Path, list[str]]:
    """Copia os .ttf usados para <trabalho>/fontes. Devolve (pasta, chaves sem arquivo)."""
    pasta = trabalho / "fontes"
    pasta.mkdir(parents=True, exist_ok=True)
    faltando: list[str] = []
    for chave in sorted(chaves if chaves is not None else CHAVES):
        origem = arquivo_fonte(chave)
        if origem is None:
            faltando.append(chave)
            continue
        destino = pasta / origem.name
        if not destino.exists():
            shutil.copy(origem, destino)
    return pasta, faltando
