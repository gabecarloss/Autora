"""Tradução do roteiro em argumentos e filtergraph do ffmpeg (sem executar nada)."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import pytest

from autora.edicao import filtros
from autora.edicao.ffmpeg import InfoVideo
from autora.edicao.plano import FORMATO_PADRAO, PlanoEdicao
from autora.plataformas.base import EspecificacaoVideo
from tests.conftest import plano_valido

VERTICAL = InfoVideo(1080, 1920, Fraction(30), "h264", "yuv420p", "aac", 48000, 2, 3.0)
HORIZONTAL = InfoVideo(1920, 1080, Fraction(25), "h264", "yuv420p", "aac", 44100, 2, 4.0)
MUDO = InfoVideo(1080, 1920, Fraction(30), "h264", "yuv420p", None, None, None, 2.0)
CLIPES = {1: Path(r"C:\videos\a.mp4"), 2: Path(r"C:\videos\b.mp4"), 3: Path(r"C:\videos\c.mp4")}
INFOS = {1: VERTICAL, 2: HORIZONTAL, 3: MUDO}
ESPEC = FORMATO_PADRAO


def _plano(**extra: object) -> PlanoEdicao:
    base = plano_valido(1, 3.0)
    base.update(extra)
    return PlanoEdicao.model_validate(base)


def test_passagem_1_corta_antes_de_cada_entrada_e_normaliza_todo_ramo() -> None:
    p1 = filtros.argumentos_passagem_1(_plano(), CLIPES, INFOS, ESPEC)
    args = p1.args
    # -ss e -t vêm ANTES do -i (busca na entrada), uma entrada por trecho
    i1 = args.index("-i")
    assert args[i1 - 4 : i1] == ["-ss", "0", "-t", "3"]
    assert args.count("-i") == 2
    assert "-filter_complex_script" in args and filtros.NOME_SCRIPT in args
    assert args[-1] == filtros.BASE_AUDIO and filtros.BASE_VIDEO in args
    assert "C:" not in p1.filtergraph  # nada de caminho absoluto dentro do filtro
    ramos = [r for r in p1.filtergraph.split(";\n") if "[v" in r and r.startswith("[")]
    ramos_video = [r for r in ramos if ":v]" in r]
    assert len(ramos_video) == 2
    for ramo in ramos_video:
        assert "setsar=1" in ramo and "fps=30" in ramo and "format=yuv420p" in ramo
    assert "concat=n=2:v=1:a=1[v][ac]" in p1.filtergraph
    assert "[ac]volume=1[a]" in p1.filtergraph
    assert "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo" in p1.filtergraph


def test_velocidade_vira_setpts_e_atempo_com_duracao_final() -> None:
    p1 = filtros.argumentos_passagem_1(_plano(), CLIPES, INFOS, ESPEC)
    assert "setpts=PTS/2" in p1.filtergraph
    assert "atempo=2" in p1.filtergraph
    assert "atrim=end=1.5" in p1.filtergraph  # 3 s a 2x


def test_clipe_sem_audio_recebe_silencio_e_horizontal_recebe_fundo_desfocado() -> None:
    plano = _plano(
        trechos=[
            {
                "clipe_id": 2,
                "inicio_s": 0,
                "fim_s": 2,
                "enquadramento": {"modo": "fundo_desfocado"},
            },
            {"clipe_id": 3, "inicio_s": 0, "fim_s": 2},
        ],
        textos=[],
        capa={"segundo": 1.0, "texto": "x"},
    )
    p1 = filtros.argumentos_passagem_1(plano, CLIPES, INFOS, ESPEC)
    assert "anullsrc=r=48000:cl=stereo" in p1.args
    assert p1.args.count("-i") == 3  # dois clipes + silêncio
    assert "boxblur" in p1.filtergraph and "overlay=(W-w)/2:(H-h)/2" in p1.filtergraph
    assert "scale=1080:-2" in p1.filtergraph  # frente do horizontal limitada pela largura
    assert "[2:a]aformat" in p1.filtergraph and "atrim=end=2[a1]" in p1.filtergraph


def test_recorte_usa_ponto_de_interesse_e_zoom_usa_scale_por_quadro() -> None:
    plano = _plano(
        trechos=[
            {
                "clipe_id": 2,
                "inicio_s": 0,
                "fim_s": 3,
                "enquadramento": {"modo": "recorte", "foco_x": 0.2, "foco_y": 0.5},
                "zoom": {"inicio_s": 0.5, "fim_s": 2.0, "fator": 1.2},
            }
        ],
        textos=[],
        capa={"segundo": 1.0, "texto": "x"},
    )
    p1 = filtros.argumentos_passagem_1(plano, CLIPES, INFOS, ESPEC)
    assert "crop=1080:1920:(iw-ow)*0.2:(ih-oh)*0.5" in p1.filtergraph
    assert "eval=frame" in p1.filtergraph and "clip((t-0.5)/1.5,0,1)" in p1.filtergraph
    assert ",crop=1080:1920:(iw-1080)*0.5:(ih-1920)*0.5" in p1.filtergraph
    assert "zoompan" not in p1.filtergraph


def test_audio_desligado_usa_silencio_em_todos_os_trechos() -> None:
    plano = _plano(audio={"manter_original": False, "volume": 0.5})
    p1 = filtros.argumentos_passagem_1(plano, CLIPES, INFOS, ESPEC)
    assert p1.args.count("anullsrc=r=48000:cl=stereo") == 2
    assert "atempo" not in p1.filtergraph
    assert "volume=0.5" in p1.filtergraph


def test_passagem_2_aplica_ass_relativo_e_codifica_no_padrao_da_plataforma() -> None:
    com = filtros.argumentos_passagem_2(com_ass=True, espec=ESPEC)
    sem = filtros.argumentos_passagem_2(com_ass=False, espec=ESPEC)
    assert "[0:v]ass=f=legendas.ass:fontsdir=fontes,format=yuv420p[v]" in com
    assert "ass=" not in " ".join(sem)
    for args in (com, sem):
        assert args[-1] == filtros.VIDEO_FINAL
        for esperado in ("libx264", "yuv420p", "aac", "+faststart", "-r", "30"):
            assert esperado in args
        assert "-map" in args and "1:a" in args


def test_wav_para_whisper_e_mono_16k() -> None:
    args = filtros.argumentos_wav_para_whisper()
    assert args[args.index("-ac") : args.index("-ar") + 2] == ["-ac", "1", "-ar", "16000"]


def test_resolucao_fps_e_codec_vem_da_plataforma() -> None:
    espec = EspecificacaoVideo(720, 1280, 25, "h264", False)
    p1 = filtros.argumentos_passagem_1(_plano(), CLIPES, INFOS, espec)
    assert "scale=720:1280" in p1.filtergraph and "fps=25" in p1.filtergraph
    assert "1080" not in p1.filtergraph and "1920" not in p1.filtergraph
    assert p1.args[p1.args.index("-r") + 1] == "25"
    p2 = filtros.argumentos_passagem_2(com_ass=False, espec=espec)
    assert p2[p2.index("-r") + 1] == "25" and p2[p2.index("-g") + 1] == "50"
    assert p2[p2.index("-c:v") + 1] == "libx264"
    with pytest.raises(ValueError, match="codec"):
        filtros.argumentos_passagem_2(
            com_ass=False, espec=EspecificacaoVideo(720, 1280, 25, "vp9", False)
        )
    with pytest.raises(ValueError, match="codec"):
        filtros.argumentos_passagem_1(
            _plano(), CLIPES, INFOS, EspecificacaoVideo(720, 1280, 25, "vp9", False)
        )
