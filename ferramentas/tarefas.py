"""Tarefas do poe que precisam do npm (ver [tool.poe.tasks] no pyproject.toml).

No Windows o npm é um ``npm.cmd``: chamá-lo por aqui (shutil.which resolve o .cmd)
funciona igual no terminal, na CI e nos hooks, sem depender de qual shell está ativo.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
FRONT = RAIZ / "frontend"


def _npm() -> str:
    caminho = shutil.which("npm")
    if caminho is None:
        sys.exit("npm não encontrado no PATH (instale o Node.js).")
    return caminho


def _rodar(*args: str) -> int:
    print(f"$ npm {' '.join(args)}", flush=True)  # noqa: T201 - saída de tarefa de terminal
    return subprocess.run([_npm(), *args], cwd=FRONT, check=False).returncode  # noqa: S603


def npm(*scripts: str) -> None:
    """Roda os scripts do frontend/package.json em ordem, sem parar no primeiro erro."""
    falhas = [s for s in scripts if _rodar("run", s) != 0]
    if falhas:
        sys.exit(f"Falharam no front: {', '.join(falhas)}")


def npm_audit() -> None:
    if _rodar("audit", "--audit-level=high") != 0:
        sys.exit("npm audit encontrou vulnerabilidades altas.")
