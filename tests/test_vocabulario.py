"""Interface sem jargão (seção 9.1): nunca "IA", "modelo", "prompt", "pipeline" ou "rodada"
em texto visível. Varre as telas (frontend/src, arquivos .tsx e textos.ts), ignorando
comentários, e as mensagens da CLI (literais de string de src/autora/cli.py). Os nomes
amigáveis vêm do GLOSSARIO.md.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from tests.conftest import RAIZ_REPO

PROIBIDAS = [
    re.compile(r"\bIA\b"),
    re.compile(r"(?i)\b(modelos?|prompts?|pipelines?|rodadas?)\b"),
]
COMENTARIO = re.compile(r"//[^\n]*|/\*.*?\*/|\{/\*.*?\*/\}", re.DOTALL)

ARQUIVOS = sorted(
    [*(RAIZ_REPO / "frontend" / "src").rglob("*.tsx"), RAIZ_REPO / "frontend" / "src" / "textos.ts"]
)


@pytest.mark.parametrize("arquivo", ARQUIVOS, ids=lambda p: p.name)
def test_telas_sem_jargao(arquivo: Path) -> None:
    texto = COMENTARIO.sub("", arquivo.read_text(encoding="utf-8"))
    achados = [m.group(0) for p in PROIBIDAS for m in p.finditer(texto)]
    assert not achados, f"{arquivo.name} usa termos proibidos na interface: {achados}"


def test_mensagens_da_cli_sem_jargao() -> None:
    arvore = ast.parse((RAIZ_REPO / "src" / "autora" / "cli.py").read_text(encoding="utf-8"))
    literais = [
        no.value
        for no in ast.walk(arvore)
        if isinstance(no, ast.Constant) and isinstance(no.value, str)
    ]
    achados = [m.group(0) for s in literais for p in PROIBIDAS for m in p.finditer(s)]
    assert not achados, f"cli.py usa termos proibidos em texto visível: {achados}"


def test_glossario_existe_e_cobre_os_termos_principais() -> None:
    g = (RAIZ_REPO / "GLOSSARIO.md").read_text(encoding="utf-8")
    for termo in ("rodada", "pacote", "revisor", "mandato", "estudo", "verificações", "Bastidores"):
        assert termo in g, termo
    assert "(?)" not in g, "nomes do glossário confirmados em 06/11/2026: nada fica pendente"
