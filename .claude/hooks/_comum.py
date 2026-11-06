"""Utilidades dos hooks do Claude Code no Autora. Só biblioteca padrão.

Os hooks rodam com o Python do .venv (ver .claude/settings.json) e conversam com o
Claude Code por JSON no stdin/stdout. Documentação: https://code.claude.com/docs/en/hooks
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, NoReturn

# resolve() devolve a grafia real do Windows ("C:\..."). Com "c:\..." minúsculo no cwd,
# o ruff deixa de aplicar as per-file-ignores do pyproject.
RAIZ = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).parents[2]).resolve()


def _utf8() -> None:
    for fluxo in (sys.stdin, sys.stdout, sys.stderr):
        reconfigurar = getattr(fluxo, "reconfigure", None)
        if reconfigurar is not None:
            reconfigurar(encoding="utf-8")


def ler_entrada() -> dict[str, Any]:
    """JSON que o Claude Code manda no stdin. Entrada estranha vira dicionário vazio."""
    _utf8()
    try:
        dados = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return dados if isinstance(dados, dict) else {}


ESCRITOR_DE_TESTES = "escritor-de-testes"


def agente_da_entrada(entrada: dict[str, Any]) -> str | None:
    """Nome do subagente que está agindo (campo `agent_type`), ou None na sessão principal."""
    valor = entrada.get("agent_type")
    return valor if isinstance(valor, str) and valor else None


def decidir(decisao: str, motivo: str) -> NoReturn:
    """Resposta de um PreToolUse: "allow", "ask" ou "deny", com o motivo."""
    saida = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decisao,
            "permissionDecisionReason": motivo,
        }
    }
    json.dump(saida, sys.stdout, ensure_ascii=False)
    sys.exit(0)


def path_completo() -> str:
    """PATH do processo + o da máquina e do usuário.

    O processo do Claude Code pode ter sido aberto antes de um programa ser instalado
    (uv, node, gh) e herdar um PATH antigo.
    """
    partes = [os.environ.get("PATH", "")]
    if sys.platform == "win32":
        import winreg

        chaves = (
            (
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
            ),
            (winreg.HKEY_CURRENT_USER, "Environment"),
        )
        for raiz, chave in chaves:
            try:
                with winreg.OpenKey(raiz, chave) as k:
                    valor, _ = winreg.QueryValueEx(k, "Path")
            except OSError:
                continue
            partes.append(os.path.expandvars(str(valor)))
    return os.pathsep.join(p for p in partes if p)
