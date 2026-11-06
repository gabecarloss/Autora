"""PreToolUse (Edit|Write|MultiEdit): protege a fonte da verdade e barra segredos.

- BRIEFING.md e qualquer mandato.md: pede confirmação do usuário (CLAUDE.md: o
  briefing não se reinterpreta; o mandato nunca se encurta nem se parafraseia).
- Texto com cara de segredo real: nega (CLAUDE.md: chaves nunca em texto puro em
  disco). Os padrões exigem o tamanho de um segredo de verdade, para que valores falsos
  curtos nos testes (ex.: "sk-ant-oat01-SEGREDO-DE-TESTE-123") continuem permitidos.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Final

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _comum import ESCRITOR_DE_TESTES, RAIZ, agente_da_entrada, decidir, ler_entrada

FONTES_DA_VERDADE: Final = frozenset({"BRIEFING.md", "mandato.md"})
_FONTES_MINUSCULAS: Final = frozenset(nome.lower() for nome in FONTES_DA_VERDADE)

PADROES_SEGREDO: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    ("uma chave ou token da Anthropic", re.compile(r"sk-ant-[a-z]+\d*-[A-Za-z0-9_\-]{80,}")),
    ("uma chave privada", re.compile(r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----")),
    (
        "um token do GitHub",
        re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{60,})\b"),
    ),
    ("uma chave da AWS", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
)


def textos_escritos(entrada_ferramenta: dict[str, Any]) -> Iterator[str]:
    for campo in ("content", "new_string"):
        valor = entrada_ferramenta.get(campo)
        if isinstance(valor, str):
            yield valor
    edicoes = entrada_ferramenta.get("edits")
    if isinstance(edicoes, list):
        for edicao in edicoes:
            if isinstance(edicao, dict) and isinstance(edicao.get("new_string"), str):
                yield edicao["new_string"]


def e_arquivo_de_teste(caminho: str, raiz: Path = RAIZ) -> bool:
    """Só tests/** ou frontend/src/**/*.test.ts(x), dentro do projeto."""
    alvo = Path(caminho)
    if not alvo.is_absolute():
        alvo = raiz / alvo
    try:
        partes = alvo.resolve().relative_to(raiz.resolve()).parts
    except ValueError:
        return False
    if partes[:1] == ("tests",):
        return True
    return partes[:2] == ("frontend", "src") and re.search(r"\.test\.tsx?$", partes[-1]) is not None


def avaliar(
    entrada_ferramenta: dict[str, Any], agente: str | None = None
) -> tuple[str, str] | None:
    """Devolve (decisão, motivo) ou None quando não há nada a dizer."""
    if agente == ESCRITOR_DE_TESTES and not e_arquivo_de_teste(
        str(entrada_ferramenta.get("file_path") or "")
    ):
        return (
            "deny",
            "O escritor de testes só escreve testes (tests/ ou frontend/src/**/*.test.tsx). "
            "Se o teste exige mudar outro arquivo, descreva isso na resposta.",
        )
    for texto in textos_escritos(entrada_ferramenta):
        for nome, padrao in PADROES_SEGREDO:
            if padrao.search(texto):
                return (
                    "deny",
                    f"O texto parece conter {nome}. Segredos nunca vão para arquivos do "
                    "projeto (ficam só no keyring). Em testes, use um valor falso curto.",
                )
    caminho = str(entrada_ferramenta.get("file_path") or "")
    nome_arquivo = Path(caminho.replace("\\", "/")).name
    if nome_arquivo.lower() in _FONTES_MINUSCULAS:
        return (
            "ask",
            f"{nome_arquivo} é fonte da verdade do projeto (CLAUDE.md). Só altere com "
            "pedido explícito do usuário; o mandato nunca é encurtado nem parafraseado.",
        )
    return None


def main() -> None:
    entrada = ler_entrada()
    ferramenta = entrada.get("tool_input")
    if not isinstance(ferramenta, dict):
        return
    resultado = avaliar(ferramenta, agente_da_entrada(entrada))
    if resultado is not None:
        decidir(*resultado)


if __name__ == "__main__":
    main()
