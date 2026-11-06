"""Motor de edição com o ffmpeg real sobre clipes sintéticos (marcador `ffmpeg`)."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import pytest
from PIL import Image

from autora.edicao import renderizador
from autora.edicao.capa import extrair_quadro
from autora.edicao.ffmpeg import inspecionar
from autora.edicao.plano import FORMATO_PADRAO, PlanoEdicao
from autora.plataformas.base import EspecificacaoVideo
from autora.registro.log import Registro
from autora.servicos.cadeia import Resultado, TodosFalharam
from autora.servicos.transcricao import Palavra, Transcricao
from autora.util.tempo import hoje

pytestmark = pytest.mark.ffmpeg

PALAVRAS = (
    Palavra("teste", 0.3, 0.8, 0.9),
    Palavra("de", 0.9, 1.1, 0.9),
    Palavra("legenda", 1.2, 1.9, 0.9),
)


def _plano() -> PlanoEdicao:
    """horizontal 0–2 s (fundo desfocado) + vertical 0,5–2,5 s a 2x com zoom + mudo 0–1 s = 4 s."""
    return PlanoEdicao.model_validate(
        {
            "trechos": [
                {
                    "clipe_id": 2,
                    "inicio_s": 0,
                    "fim_s": 2,
                    "enquadramento": {"modo": "fundo_desfocado"},
                },
                {
                    "clipe_id": 1,
                    "inicio_s": 0.5,
                    "fim_s": 2.5,
                    "velocidade": 2.0,
                    "zoom": {"inicio_s": 0.1, "fim_s": 0.9, "fator": 1.2},
                },
                {"clipe_id": 3, "inicio_s": 0, "fim_s": 1},
            ],
            "textos": [
                {
                    "texto": "TEXTO DE TESTE",
                    "papel": "gancho",
                    "inicio_s": 0.2,
                    "fim_s": 1.8,
                    "posicao": "topo",
                    "estilo": {
                        "cor": "#1E90FF",
                        "cor_contorno": "#1E90FF",
                        "tamanho": 150,
                        "animacao": "nenhuma",
                    },
                }
            ],
            "legendas": {"ativas": True, "modo": "palavra"},
            "capa": {"segundo": 1.0, "texto": "CAPA"},
            "motivos": {
                "ritmo": "Três trechos curtos para cobrir os três casos.",
                "enquadramento": "Horizontal com fundo desfocado, vertical recortado.",
                "textos": "Um texto azul no topo para a checagem visual.",
                "legendas": "Palavra por palavra com transcrição simulada.",
            },
        }
    )


def _transcritor_fixo(wav: Path) -> Resultado[Transcricao]:
    assert wav.is_file()
    return Resultado(Transcricao(PALAVRAS, "pt", "falso"), "falso", False, [])


def _transcritor_quebrado(wav: Path) -> Resultado[Transcricao]:
    raise TodosFalharam("legendas", [("whisper-cpu", RuntimeError("sem modelo"))])


def _pixels_azuis(imagem: Path, faixa: tuple[int, int]) -> int:
    """Pixels perto de #1E90FF (cor do texto), que o padrão testsrc2 não tem."""
    with Image.open(imagem) as im:
        rgb = im.convert("RGB")
        total = 0
        for y in range(faixa[0], faixa[1], 4):
            for x in range(0, rgb.width, 4):
                r, g, b = rgb.getpixel((x, y))  # type: ignore[misc]
                if abs(r - 0x1E) < 40 and abs(g - 0x90) < 40 and b > 215:
                    total += 1
    return total


def test_renderiza_pacote_completo_no_padrao_da_plataforma(
    clipes_sinteticos: dict[str, Path], tmp_path: Path
) -> None:
    clipes = {
        1: clipes_sinteticos["vertical"],
        2: clipes_sinteticos["horizontal"],
        3: clipes_sinteticos["mudo"],
    }
    registro = Registro(tmp_path / "logs", "t")
    entrega = renderizador.renderizar(
        _plano(), clipes, tmp_path / "saida", espec=FORMATO_PADRAO, registro=registro, idioma="pt",
        pasta_modelos=tmp_path / "modelos", rodada_id=1, post_id=1, manter_trabalho=True,
        transcritor=_transcritor_fixo,
    )  # fmt: skip
    info = inspecionar(entrega.video)
    assert (info.largura, info.altura, info.fps) == (1080, 1920, Fraction(30))
    assert (info.codec_video, info.codec_audio, info.pix_fmt) == ("h264", "aac", "yuv420p")
    assert abs(info.duracao_s - 4.0) < 0.15 and abs(entrega.duracao_s - 4.0) < 0.15
    assert entrega.legendas == "ok" and entrega.transcricao is not None
    with Image.open(entrega.capa) as capa:
        assert capa.size == (1080, 1920)
    trabalho = tmp_path / "saida" / "trabalho"
    assert (trabalho / "legendas.ass").is_file() and (trabalho / "filtros_1.txt").is_file()
    # Checagem visual mínima: o texto azul do topo aparece no quadro de 1 s e não no de 3 s.
    com_texto = extrair_quadro(entrega.video, 1.0, tmp_path / "q1.png")
    sem_texto = extrair_quadro(entrega.video, 3.0, tmp_path / "q3.png")
    assert _pixels_azuis(com_texto, (0, 700)) > 3000
    assert _pixels_azuis(sem_texto, (0, 700)) < 300
    mensagens = [e["mensagem"] for e in registro.ler_dia(hoje())]
    assert any("Cortes e enquadramento" in m for m in mensagens)
    assert any("Vídeo final codificado" in m for m in mensagens)


def test_sem_servico_de_legenda_o_video_sai_sem_legendas_com_aviso(
    clipes_sinteticos: dict[str, Path], tmp_path: Path
) -> None:
    clipes = {
        1: clipes_sinteticos["vertical"],
        2: clipes_sinteticos["horizontal"],
        3: clipes_sinteticos["mudo"],
    }
    registro = Registro(tmp_path / "logs", "t")
    entrega = renderizador.renderizar(
        _plano(), clipes, tmp_path / "saida", espec=FORMATO_PADRAO, registro=registro, idioma=None,
        pasta_modelos=tmp_path / "modelos", transcritor=_transcritor_quebrado,
    )  # fmt: skip
    assert entrega.legendas == "indisponiveis"
    assert any("legenda" in a.lower() for a in entrega.avisos)
    assert entrega.video.is_file() and entrega.capa.is_file()
    assert not (tmp_path / "saida" / "trabalho").exists()  # pasta de trabalho apagada
    assert any(e["tipo"] == "erro" for e in registro.ler_dia(hoje()))


def test_roteiro_fora_do_clipe_e_recusado_antes_de_renderizar(
    clipes_sinteticos: dict[str, Path], tmp_path: Path
) -> None:
    plano = PlanoEdicao.model_validate(
        {
            **_plano().model_dump(),
            "trechos": [{"clipe_id": 3, "inicio_s": 0, "fim_s": 9}],
            "textos": [],
            "capa": {"segundo": 1, "texto": "x"},
        }
    )
    with pytest.raises(renderizador.PlanoInvalido) as info:
        renderizador.renderizar(
            plano, {3: clipes_sinteticos["mudo"]}, tmp_path / "saida",
            espec=FORMATO_PADRAO, registro=Registro(tmp_path / "logs", "t"), idioma=None,
            pasta_modelos=tmp_path,
        )  # fmt: skip
    assert "duração do clipe" in info.value.problemas[0]


def test_motor_segue_a_resolucao_e_o_fps_da_plataforma(
    clipes_sinteticos: dict[str, Path], tmp_path: Path
) -> None:
    espec = EspecificacaoVideo(540, 960, 25, "h264", False)
    plano = PlanoEdicao.model_validate(
        {**_plano().model_dump(), "legendas": {"ativas": False}, "textos": []}
    )
    clipes = {
        1: clipes_sinteticos["vertical"],
        2: clipes_sinteticos["horizontal"],
        3: clipes_sinteticos["mudo"],
    }
    entrega = renderizador.renderizar(
        plano, clipes, tmp_path / "saida", espec=espec, registro=Registro(tmp_path / "logs", "t"),
        idioma=None, pasta_modelos=tmp_path / "modelos",
    )  # fmt: skip
    info = inspecionar(entrega.video)
    assert (info.largura, info.altura, info.fps) == (540, 960, Fraction(25))
    with Image.open(entrega.capa) as capa:
        assert capa.size == (540, 960)
