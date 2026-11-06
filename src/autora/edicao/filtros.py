"""Roteiro de edição → argumentos e filtergraph do ffmpeg (funções puras, sem executar).

Passagem 1: corta, enquadra, acelera e concatena, sem texto → base.mp4 + base.wav.
Passagem 2: aplica o ASS (legendas + textos) e codifica o vídeo final.

Convenções (verificadas nesta build do ffmpeg 7.1):
- `setsar=1` em todo ramo, senão o concat falha com SAR diferente;
- fps, taxa de amostragem, canais e formato normalizados em todo ramo antes do concat;
- `-ss`/`-t` antes de cada `-i` (busca na entrada, rápida e exata ao recodificar);
- zoom com `scale … eval=frame` + `crop` fixo (`crop` não aceita `t` em w/h);
- nada de caminho absoluto dentro de filtergraph: o script e o ASS são relativos à cwd.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from autora.edicao.ffmpeg import InfoVideo
from autora.edicao.plano import PlanoEdicao, Trecho
from autora.plataformas.base import EspecificacaoVideo

OPCOES_BASE: Final = ("-y", "-hide_banner", "-nostdin", "-loglevel", "error")
NOME_SCRIPT: Final = "filtros_1.txt"
BASE_VIDEO: Final = "base.mp4"
BASE_AUDIO: Final = "base.wav"
ARQUIVO_ASS: Final = "legendas.ass"
PASTA_FONTES: Final = "fontes"
VIDEO_FINAL: Final = "video.mp4"
# Codificadores por codec da plataforma. PROVISÓRIO: só h264 (libx264) nesta versão.
CODIFICADORES: Final[dict[str, str]] = {"h264": "libx264"}


def codificador(espec: EspecificacaoVideo) -> str:
    try:
        return CODIFICADORES[espec.codec]
    except KeyError:
        raise ValueError(f"codec de vídeo não suportado pelo motor: {espec.codec!r}") from None


@dataclass(frozen=True)
class Passagem1:
    args: list[str]  # argumentos depois do executável
    filtergraph: str  # conteúdo de filtros_1.txt


def _f(x: float) -> str:
    return f"{x:.3f}".rstrip("0").rstrip(".") if x != int(x) else str(int(x))


def _enquadramento(trecho: Trecho, info: InfoVideo, k: int, espec: EspecificacaoVideo) -> str:
    e = trecho.enquadramento
    LARGURA, ALTURA = espec.largura, espec.altura
    if e.modo == "fundo_desfocado":
        alvo = LARGURA / ALTURA
        frente = (
            f"scale={LARGURA}:-2" if info.largura / info.altura >= alvo else f"scale=-2:{ALTURA}"
        )
        return (
            f"split=2[f{k}][g{k}];"
            f"[f{k}]scale={LARGURA}:{ALTURA}:force_original_aspect_ratio=increase,"
            f"crop={LARGURA}:{ALTURA},"
            f"boxblur=luma_radius=24:luma_power=2:chroma_radius=12:chroma_power=2[bg{k}];"
            f"[g{k}]{frente}[fg{k}];"
            f"[bg{k}][fg{k}]overlay=(W-w)/2:(H-h)/2"
        )
    return (
        f"scale={LARGURA}:{ALTURA}:force_original_aspect_ratio=increase,"
        f"crop={LARGURA}:{ALTURA}:(iw-ow)*{_f(e.foco_x)}:(ih-oh)*{_f(e.foco_y)}"
    )


def _zoom(trecho: Trecho, espec: EspecificacaoVideo) -> str:
    z = trecho.zoom
    if z is None:
        return ""
    LARGURA, ALTURA = espec.largura, espec.altura
    dur = max(z.fim_s - z.inicio_s, 0.1)
    progresso = f"clip((t-{_f(z.inicio_s)})/{_f(dur)},0,1)"
    fator = f"(1+{_f(z.fator - 1)}*{progresso})"
    return (
        f",scale=w='{LARGURA}*{fator}':h='{ALTURA}*{fator}':eval=frame,"
        f"crop={LARGURA}:{ALTURA}:(iw-{LARGURA})*0.5:(ih-{ALTURA})*0.5"
    )


def ramo_video(
    entrada: int, trecho: Trecho, info: InfoVideo, k: int, espec: EspecificacaoVideo
) -> str:
    velocidade = f",setpts=PTS/{_f(trecho.velocidade)}" if trecho.velocidade != 1 else ""
    return (
        f"[{entrada}:v]setpts=PTS-STARTPTS,{_enquadramento(trecho, info, k, espec)}"
        f"{velocidade},fps={espec.fps}{_zoom(trecho, espec)},setsar=1,format=yuv420p[v{k}]"
    )


def ramo_audio(entrada: int, trecho: Trecho, k: int, *, silencio: bool) -> str:
    formato = "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo"
    fim = _f(trecho.duracao_final_s)
    if silencio:
        return f"[{entrada}:a]{formato},atrim=end={fim}[a{k}]"
    tempo = f",atempo={_f(trecho.velocidade)}" if trecho.velocidade != 1 else ""
    return f"[{entrada}:a]asetpts=PTS-STARTPTS,{formato}{tempo},apad,atrim=end={fim}[a{k}]"


def argumentos_passagem_1(
    plano: PlanoEdicao,
    clipes: Mapping[int, Path],
    infos: Mapping[int, InfoVideo],
    espec: EspecificacaoVideo,
) -> Passagem1:
    codificador(espec)  # falha cedo se o codec não for suportado
    args: list[str] = list(OPCOES_BASE)
    ramos: list[str] = []
    entrada = 0
    for k, trecho in enumerate(plano.trechos):
        info = infos[trecho.clipe_id]
        args += [
            "-ss",
            _f(trecho.inicio_s),
            "-t",
            _f(trecho.duracao_fonte_s),
            "-i",
            str(clipes[trecho.clipe_id]),
        ]
        ramos.append(ramo_video(entrada, trecho, info, k, espec))
        usa_original = plano.audio.manter_original and info.tem_audio
        if usa_original:
            ramos.append(ramo_audio(entrada, trecho, k, silencio=False))
            entrada += 1
        else:
            entrada += 1
            args += [
                "-f",
                "lavfi",
                "-t",
                _f(trecho.duracao_final_s),
                "-i",
                "anullsrc=r=48000:cl=stereo",
            ]
            ramos.append(ramo_audio(entrada, trecho, k, silencio=True))
            entrada += 1
    pares = "".join(f"[v{k}][a{k}]" for k in range(len(plano.trechos)))
    ramos.append(f"{pares}concat=n={len(plano.trechos)}:v=1:a=1[v][ac]")
    ramos.append(f"[ac]volume={_f(plano.audio.volume)}[a]")
    args += ["-filter_complex_script", NOME_SCRIPT]
    args += ["-map", "[v]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "16",
             "-pix_fmt", "yuv420p", "-r", str(espec.fps), "-an", BASE_VIDEO]  # fmt: skip
    args += ["-map", "[a]", "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", BASE_AUDIO]
    return Passagem1(args, ";\n".join(ramos) + "\n")


def argumentos_passagem_2(*, com_ass: bool, espec: EspecificacaoVideo) -> list[str]:
    filtro = (
        f"[0:v]ass=f={ARQUIVO_ASS}:fontsdir={PASTA_FONTES},format=yuv420p[v]"
        if com_ass
        else "[0:v]format=yuv420p[v]"
    )
    return [
        *OPCOES_BASE, "-i", BASE_VIDEO, "-i", BASE_AUDIO,
        "-filter_complex", filtro, "-map", "[v]", "-map", "1:a",
        "-c:v", codificador(espec), "-preset", "medium", "-crf", "20", "-profile:v", "high",
        "-level", "4.1", "-pix_fmt", "yuv420p", "-r", str(espec.fps), "-g", str(espec.fps * 2),
        "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart", VIDEO_FINAL,
    ]  # fmt: skip


def argumentos_wav_para_whisper(entrada: str = BASE_AUDIO, saida: str = "whisper.wav") -> list[str]:
    return [*OPCOES_BASE, "-i", entrada, "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", saida]
