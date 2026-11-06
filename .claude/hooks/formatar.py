"""PostToolUse (Edit|Write|MultiEdit): formata o arquivo que acabou de ser editado.

- .py do projeto: ruff format + ruff check --fix.
- frontend/src (ts, tsx, css, json): prettier --write.
Se sobrar erro que a correção automática não resolve, devolve ao Claude (exit 2) para
ele corrigir na hora, em vez de descobrir só no pre-commit.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Final

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _comum import RAIZ, ler_entrada, path_completo

SUFIXOS_FRONT: Final = frozenset({".ts", ".tsx", ".css", ".json"})
_MAX_LINHAS: Final = 40


def _rodar(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - argumentos em lista, sem shell
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
    )


def _devolver(titulo: str, saida: str) -> None:
    linhas = saida.strip().splitlines()[:_MAX_LINHAS]
    print(titulo, file=sys.stderr)
    print("\n".join(linhas), file=sys.stderr)
    sys.exit(2)


def formatar_python(arquivo: Path) -> None:
    _rodar([sys.executable, "-m", "ruff", "check", "--fix", "--quiet", str(arquivo)], RAIZ)
    _rodar([sys.executable, "-m", "ruff", "format", "--quiet", str(arquivo)], RAIZ)
    r = _rodar(
        [sys.executable, "-m", "ruff", "check", "--fix", "--quiet", "--output-format",
         "concise", str(arquivo)],
        RAIZ,
    )  # fmt: skip
    if r.returncode != 0:
        _devolver("ruff ainda acusa problemas neste arquivo:", r.stdout or r.stderr)


def formatar_front(arquivo: Path) -> None:
    node = shutil.which("node", path=path_completo())
    prettier = RAIZ / "frontend" / "node_modules" / "prettier" / "bin" / "prettier.cjs"
    if node is None or not prettier.exists():
        return
    r = _rodar([node, str(prettier), "--write", "--log-level", "warn", str(arquivo)],
               RAIZ / "frontend")  # fmt: skip
    if r.returncode != 0:
        _devolver("prettier não conseguiu formatar (erro de sintaxe?):", r.stderr or r.stdout)


def main() -> None:
    entrada = ler_entrada()
    ferramenta = entrada.get("tool_input")
    if not isinstance(ferramenta, dict) or not ferramenta.get("file_path"):
        return
    arquivo = Path(str(ferramenta["file_path"]))
    if not arquivo.is_absolute():
        arquivo = RAIZ / arquivo
    arquivo = arquivo.resolve()
    try:
        relativo = arquivo.relative_to(RAIZ)
    except ValueError:
        return  # fora do projeto (ex.: arquivos de memória)
    if not arquivo.is_file():
        return
    if arquivo.suffix == ".py":
        formatar_python(arquivo)
    elif relativo.parts[:2] == ("frontend", "src") and arquivo.suffix in SUFIXOS_FRONT:
        formatar_front(arquivo)


if __name__ == "__main__":
    main()
