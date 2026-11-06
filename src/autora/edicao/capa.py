"""capa.jpg (seção 2): quadro do vídeo final com o texto da capa desenhado pelo Pillow."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from autora.edicao.ffmpeg import executar, exigir_ffmpeg
from autora.edicao.fontes import arquivo_fonte
from autora.edicao.plano import Capa, EstiloTexto
from autora.plataformas.base import EspecificacaoVideo

MARGEM = 80  # na tela de referência 1080x1920; escala com a plataforma


def extrair_quadro(video: Path, segundo: float, destino: Path, ffmpeg: Path | None = None) -> Path:
    ffmpeg = ffmpeg or exigir_ffmpeg()[0]
    destino.parent.mkdir(parents=True, exist_ok=True)
    executar(
        [ffmpeg, "-y", "-hide_banner", "-nostdin", "-loglevel", "error", "-ss", f"{segundo:.3f}",
         "-i", video, "-frames:v", "1", "-update", "1", "-q:v", "2", destino],
        tempo_limite_s=120,
    )  # fmt: skip
    return destino


def _fonte(estilo: EstiloTexto, espec: EspecificacaoVideo) -> Any:
    tamanho = max(8, round(estilo.tamanho * espec.altura / 1920))  # tamanhos são na tela 1080x1920
    arquivo = arquivo_fonte(estilo.fonte)
    if arquivo is not None:
        return ImageFont.truetype(str(arquivo), tamanho)
    return ImageFont.load_default(size=tamanho)


def _quebrar(draw: Any, texto: str, fonte: Any, largura_max: int) -> str:
    linhas: list[str] = []
    for paragrafo in texto.split("\n"):
        atual = ""
        for palavra in paragrafo.split():
            tentativa = f"{atual} {palavra}".strip()
            if draw.textlength(tentativa, font=fonte) <= largura_max or not atual:
                atual = tentativa
            else:
                linhas.append(atual)
                atual = palavra
        linhas.append(atual)
    return "\n".join(linhas)


def desenhar_capa(
    quadro: Path, texto: str, estilo: EstiloTexto, destino: Path, espec: EspecificacaoVideo
) -> Path:
    largura, altura = espec.largura, espec.altura
    with Image.open(quadro) as img:
        imagem = img.convert("RGB")
    if imagem.size != (largura, altura):
        imagem = imagem.resize((largura, altura))
    draw = ImageDraw.Draw(imagem)
    fonte = _fonte(estilo, espec)
    margem = round(MARGEM * largura / 1080)
    linhas = _quebrar(draw, texto, fonte, largura - 2 * margem)
    draw.multiline_text(
        (largura // 2, altura // 2),
        linhas,
        font=fonte,
        fill=estilo.cor,
        stroke_width=estilo.contorno + 2,
        stroke_fill=estilo.cor_contorno,
        anchor="mm",
        align="center",
        spacing=12,
    )
    destino.parent.mkdir(parents=True, exist_ok=True)
    imagem.save(destino, "JPEG", quality=92)
    return destino


def gerar_capa(
    video: Path,
    capa: Capa,
    trabalho: Path,
    destino: Path,
    espec: EspecificacaoVideo,
    ffmpeg: Path | None = None,
) -> Path:
    quadro = extrair_quadro(video, capa.segundo, trabalho / "quadro_capa.png", ffmpeg)
    return desenhar_capa(quadro, capa.texto, capa.estilo, destino, espec)
