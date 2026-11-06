"""ffmpeg e ffprobe como programas externos: localizar, executar e sondar vídeos.

Regras: nunca `shell=True`; argumentos sempre em lista; sem janela de console no app
(pywebview); stderr guardado inteiro no erro para o log. Caminhos dentro de filtergraph
são responsabilidade de quem monta o filtro (ver filtros.py: sempre relativos à cwd).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Final, Literal

_SEM_JANELA: Final = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
_PASTAS_CONHECIDAS: Final = (Path(r"C:\ffmpeg\bin"),)

Orientacao = Literal["vertical", "horizontal", "quadrado"]


class FfmpegAusente(RuntimeError):
    def __init__(self) -> None:
        super().__init__("O programa de vídeo (ffmpeg) não está instalado nesta máquina.")


class ErroFfmpeg(RuntimeError):
    def __init__(self, mensagem: str, comando: Sequence[str], saida_erro: str) -> None:
        super().__init__(mensagem)
        self.comando = list(comando)
        self.saida_erro = saida_erro


@dataclass(frozen=True)
class InfoVideo:
    largura: int
    altura: int
    fps: Fraction
    codec_video: str | None
    pix_fmt: str | None
    codec_audio: str | None
    taxa_audio: int | None
    canais: int | None
    duracao_s: float

    @property
    def tem_audio(self) -> bool:
        return self.codec_audio is not None

    @property
    def orientacao(self) -> Orientacao:
        if self.largura < self.altura:
            return "vertical"
        if self.largura > self.altura:
            return "horizontal"
        return "quadrado"


def localizar_ffmpeg() -> tuple[Path, Path] | None:
    """(ffmpeg, ffprobe) ou None. Ordem: AUTORA_FFMPEG, PATH, pastas conhecidas."""
    candidatas: list[Path] = []
    env = os.environ.get("AUTORA_FFMPEG")
    if env:
        candidatas.append(Path(env))
    achado = shutil.which("ffmpeg")
    if achado:
        candidatas.append(Path(achado).parent)
    candidatas.extend(_PASTAS_CONHECIDAS)
    sufixo = ".exe" if sys.platform == "win32" else ""
    for pasta in candidatas:
        ffmpeg, ffprobe = pasta / f"ffmpeg{sufixo}", pasta / f"ffprobe{sufixo}"
        if ffmpeg.is_file() and ffprobe.is_file():
            return ffmpeg, ffprobe
    return None


def exigir_ffmpeg() -> tuple[Path, Path]:
    par = localizar_ffmpeg()
    if par is None:
        raise FfmpegAusente()
    return par


def executar(
    args: Sequence[str | Path], *, cwd: Path | None = None, tempo_limite_s: int = 900
) -> str:
    """Roda ffmpeg/ffprobe e devolve o stdout. Erro vira ErroFfmpeg com o stderr."""
    comando = [str(a) for a in args]
    try:
        proc = subprocess.run(  # noqa: S603 - lista de argumentos, sem shell
            comando,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(cwd) if cwd else None,
            timeout=tempo_limite_s,
            creationflags=_SEM_JANELA,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise ErroFfmpeg(
            f"O processamento de vídeo passou do tempo limite ({tempo_limite_s} s).", comando, ""
        ) from e
    except OSError as e:
        raise ErroFfmpeg("O ffmpeg não pôde ser iniciado.", comando, str(e)) from e
    if proc.returncode != 0:
        raise ErroFfmpeg(
            "O ffmpeg devolveu um erro.", comando, (proc.stderr or proc.stdout or "")[-4000:]
        )
    return proc.stdout


def _fracao(texto: str | None) -> Fraction:
    if not texto or texto in ("0/0", "0"):
        return Fraction(0)
    num, _, den = texto.partition("/")
    return Fraction(int(num), int(den or 1))


def inspecionar(caminho: Path, ffprobe: Path | None = None) -> InfoVideo:
    ffprobe = ffprobe or exigir_ffmpeg()[1]
    saida = executar(
        [ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", caminho],
        tempo_limite_s=120,
    )
    dados: dict[str, Any] = json.loads(saida)
    video = next((s for s in dados.get("streams", []) if s.get("codec_type") == "video"), None)
    audio = next((s for s in dados.get("streams", []) if s.get("codec_type") == "audio"), None)
    if video is None:
        raise ErroFfmpeg("O arquivo não tem trilha de vídeo.", [str(caminho)], "")
    formato = dados.get("format", {})
    duracao = float(formato.get("duration") or video.get("duration") or 0)
    return InfoVideo(
        largura=int(video["width"]),
        altura=int(video["height"]),
        fps=_fracao(video.get("avg_frame_rate") or video.get("r_frame_rate")),
        codec_video=video.get("codec_name"),
        pix_fmt=video.get("pix_fmt"),
        codec_audio=audio.get("codec_name") if audio else None,
        taxa_audio=int(audio["sample_rate"]) if audio and audio.get("sample_rate") else None,
        canais=int(audio["channels"]) if audio and audio.get("channels") else None,
        duracao_s=round(duracao, 3),
    )


def extrair_audio_wav(video: Path, destino: Path, ffmpeg: Path | None = None) -> Path:
    """Áudio mono a 16 kHz (o que o Whisper espera)."""
    ffmpeg = ffmpeg or exigir_ffmpeg()[0]
    destino.parent.mkdir(parents=True, exist_ok=True)
    executar(
        [ffmpeg, "-y", "-hide_banner", "-nostdin", "-loglevel", "error", "-i", video, "-vn",
         "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", destino],
        tempo_limite_s=600,
    )  # fmt: skip
    return destino
