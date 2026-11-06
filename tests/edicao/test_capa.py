"""capa.jpg: texto desenhado pelo Pillow sobre um quadro (sem ffmpeg)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from autora.edicao.capa import desenhar_capa
from autora.edicao.plano import FORMATO_PADRAO, EstiloTexto


def test_desenhar_capa_gera_jpg_no_tamanho_da_plataforma_com_o_texto(tmp_path: Path) -> None:
    quadro = tmp_path / "quadro.png"
    Image.new("RGB", (540, 960), (0, 0, 0)).save(quadro)  # tamanho errado de propósito
    destino = desenhar_capa(
        quadro,
        "ELE JUROU QUE DAVA CERTO E NÃO DEU",
        EstiloTexto(cor="#FFFFFF", cor_contorno="#000000", tamanho=120),
        tmp_path / "capa.jpg",
        FORMATO_PADRAO,
    )
    with Image.open(destino) as im:
        assert im.size == (1080, 1920) and im.format == "JPEG"
        rgb = im.convert("RGB")
        claros = sum(
            1
            for y in range(700, 1220, 6)
            for x in range(0, 1080, 6)
            if rgb.getpixel((x, y))[0] > 200  # type: ignore[index]
        )
    assert claros > 200  # o texto branco aparece no meio da imagem


def test_fonte_ausente_cai_na_padrao_sem_erro(tmp_path: Path, monkeypatch: object) -> None:
    import pytest

    from autora.edicao import capa as modulo

    mp = pytest.MonkeyPatch()
    mp.setattr(modulo, "arquivo_fonte", lambda chave: None)
    try:
        quadro = tmp_path / "quadro.png"
        Image.new("RGB", (1080, 1920), (10, 10, 10)).save(quadro)
        destino = desenhar_capa(quadro, "OI", EstiloTexto(), tmp_path / "capa.jpg", FORMATO_PADRAO)
        assert destino.is_file()
    finally:
        mp.undo()


def test_capa_sai_na_resolucao_da_plataforma(tmp_path: Path) -> None:
    from autora.plataformas.base import EspecificacaoVideo

    quadro = tmp_path / "quadro.png"
    Image.new("RGB", (1080, 1920), (0, 0, 0)).save(quadro)
    espec = EspecificacaoVideo(540, 960, 25, "h264", False)
    destino = desenhar_capa(quadro, "OI", EstiloTexto(), tmp_path / "capa.jpg", espec)
    with Image.open(destino) as im:
        assert im.size == (540, 960)
