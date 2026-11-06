"""Fala de teste em português gerada pelo sintetizador do Windows (SAPI), só nos testes.

Sem dependência nova: `System.Speech` via PowerShell. Fora do Windows, ou sem voz, o
teste que precisa disso é pulado.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_POWERSHELL = str(
    Path(os.environ.get("SYSTEMROOT", r"C:\Windows"))
    / "System32"
    / "WindowsPowerShell"
    / "v1.0"
    / "powershell.exe"
)
FRASE = "O cachorro pulou o muro e roubou o pão do vizinho."
PALAVRAS_ESPERADAS = ("cachorro", "muro", "vizinho")


def gerar_fala_wav(destino: Path, texto: str = FRASE) -> Path | None:
    if sys.platform != "win32":
        return None
    script = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "try { $s.SelectVoice('Microsoft Maria Desktop') } catch {}; "
        f"$s.SetOutputToWaveFile('{destino}'); "
        f"$s.Speak('{texto}'); $s.Dispose()"
    )
    try:
        subprocess.run(  # noqa: S603 - texto fixo de teste, sem entrada do usuário
            [_POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", script],
            check=True,
            capture_output=True,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return destino if destino.is_file() and destino.stat().st_size > 1000 else None
