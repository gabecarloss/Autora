"""Clipes sintéticos gerados pelo próprio ffmpeg (lavfi), para testes e para o perfil de
teste quando não há vídeo real na máquina."""

from __future__ import annotations

from pathlib import Path

from autora.edicao.ffmpeg import executar, exigir_ffmpeg


def gerar_clipe_sintetico(
    destino: Path,
    *,
    largura: int = 1080,
    altura: int = 1920,
    duracao_s: float = 3.0,
    fps: int = 30,
    taxa_audio: int = 48000,
    com_audio: bool = True,
    frequencia_hz: int = 440,
    audio_wav: Path | None = None,
) -> Path:
    """Padrão de teste (testsrc2) com um tom, ou com um .wav de fala dado em `audio_wav`."""
    ffmpeg, _ = exigir_ffmpeg()
    destino.parent.mkdir(parents=True, exist_ok=True)
    args: list[str | Path] = [
        ffmpeg, "-y", "-hide_banner", "-nostdin", "-loglevel", "error",
        "-f", "lavfi", "-i", f"testsrc2=size={largura}x{altura}:rate={fps}:duration={duracao_s}",
    ]  # fmt: skip
    if audio_wav is not None:
        args += ["-i", audio_wav]
    elif com_audio:
        args += [
            "-f", "lavfi", "-i",
            f"sine=frequency={frequencia_hz}:sample_rate={taxa_audio}:duration={duracao_s}",
        ]  # fmt: skip
    args += ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "28", "-pix_fmt", "yuv420p"]
    if audio_wav is not None or com_audio:
        args += ["-c:a", "aac", "-shortest"]
    else:
        args += ["-an"]
    args.append(destino)
    executar(args, tempo_limite_s=120)
    return destino
