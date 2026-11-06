"""SessionStart: contexto curto no começo de cada sessão.

O texto impresso no stdout entra no contexto do Claude. Fica em poucas linhas: o estado
detalhado vive no CLAUDE.md e na memória.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _comum import RAIZ, ler_entrada, path_completo


def _git(*args: str) -> str:
    git = shutil.which("git", path=path_completo())
    if git is None:
        return ""
    try:
        r = subprocess.run(  # noqa: S603 - argumentos em lista, sem shell
            [git, *args],
            cwd=RAIZ,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def estado_do_projeto(claude_md: Path) -> str:
    """Primeiro parágrafo da seção "Estado do projeto" do CLAUDE.md, numa linha."""
    try:
        texto = claude_md.read_text(encoding="utf-8")
    except OSError:
        return ""
    m = re.search(r"^## Estado do projeto\s*\n+(.+?)(?:\n\s*\n|\Z)", texto, re.M | re.S)
    if not m:
        return ""
    return " ".join(linha.strip() for linha in m.group(1).splitlines()).replace("**", "")


def montar() -> list[str]:
    linhas = []
    branch = _git("branch", "--show-current") or "?"
    alterados = len(_git("status", "--porcelain").splitlines())
    ultimo = _git("log", "-1", "--format=%h %s (%cr)") or "sem commits"
    linhas.append(
        f"[Autora] branch {branch} · {alterados} arquivo(s) não commitado(s) · "
        f"último commit: {ultimo}"
    )
    estado = estado_do_projeto(RAIZ / "CLAUDE.md")
    if estado:
        linhas.append(f"[Autora] {estado}")
    linhas.append(
        "[Autora] Lembretes: leia BRIEFING.md antes de qualquer tarefa; nunca commite nem "
        "altere o git sem pedido explícito; use /iniciar-passo N e /fechar-passo N."
    )
    return linhas


def main() -> None:
    ler_entrada()
    print("\n".join(montar()))


if __name__ == "__main__":
    main()
