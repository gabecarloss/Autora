"""Palavras do Whisper e textos na tela → arquivo ASS (sem ffmpeg)."""

from __future__ import annotations

from itertools import pairwise

from autora.edicao import legendas
from autora.edicao.plano import FORMATO_PADRAO, Legendas, PlanoEdicao, TextoNaTela
from autora.plataformas.base import EspecificacaoVideo
from autora.servicos.transcricao import Palavra
from tests.conftest import plano_valido

ESPEC = FORMATO_PADRAO
PALAVRAS = (
    Palavra("o", 0.10, 0.20, 0.9),
    Palavra("cachorro", 0.25, 0.70, 0.9),
    Palavra("pulou", 0.72, 1.00, 0.8),
    Palavra("o", 1.05, 1.10, 0.9),
    Palavra("muro", 1.12, 1.50, 0.9),
)


def test_tempo_e_cor_no_formato_do_ass() -> None:
    assert legendas.tempo_ass(0) == "0:00:00.00"
    assert legendas.tempo_ass(61.237) == "0:01:01.24"
    assert legendas.tempo_ass(3600.5) == "1:00:00.50"
    assert legendas.cor_ass("#FFD400") == "&H0000D4FF"
    assert legendas.cor_ass("#000000", 0x80) == "&H80000000"


def test_escapar_protege_chaves_e_quebras() -> None:
    assert legendas.escapar("a{b}\nc\r") == r"a(b)\Nc"


def test_modo_palavra_gera_um_evento_por_palavra_sem_sobreposicao() -> None:
    cfg = Legendas(ativas=True, modo="palavra")
    estilos, eventos = legendas.eventos_legenda(PALAVRAS, cfg, 10, ESPEC)
    assert [e.nome for e in estilos] == ["Legenda"]
    assert len(eventos) == 5
    for atual, proximo in pairwise(eventos):
        assert atual.fim_s <= proximo.inicio_s
        curta = atual.fim_s == proximo.inicio_s
        assert curta or atual.fim_s - atual.inicio_s >= legendas.DURACAO_MINIMA_PALAVRA_S - 1e-9
    assert eventos[0].texto.endswith("o") and eventos[1].texto.endswith("cachorro")
    assert all(e.camada == 0 for e in eventos)


def test_modo_grupo_usa_karaoke_e_cor_de_destaque() -> None:
    cfg = Legendas(ativas=True, modo="grupo", palavras_por_grupo=2, cor_destaque="#FF0000")
    estilos, eventos = legendas.eventos_legenda(PALAVRAS, cfg, 10, ESPEC)
    assert len(eventos) == 3  # 2 + 2 + 1
    assert all("\\k" in e.texto for e in eventos)
    assert estilos[0].cor_primaria == legendas.cor_ass("#FF0000")
    assert estilos[0].cor_secundaria == legendas.cor_ass(cfg.estilo.cor)


def test_legendas_desligadas_ou_sem_palavras_nao_geram_eventos() -> None:
    assert legendas.eventos_legenda(PALAVRAS, Legendas(ativas=False), 10, ESPEC) == ([], [])
    assert legendas.eventos_legenda((), Legendas(ativas=True), 10, ESPEC) == ([], [])


def test_palavras_depois_do_fim_do_video_sao_descartadas() -> None:
    _, eventos = legendas.eventos_legenda(PALAVRAS, Legendas(ativas=True), 1.0, ESPEC)
    assert len(eventos) == 3
    assert eventos[-1].fim_s <= 1.0


def test_textos_na_tela_tem_camada_1_animacao_e_posicao_explicita() -> None:
    textos = [
        TextoNaTela(texto="olha isso", papel="gancho", inicio_s=0, fim_s=1, posicao="topo"),
        TextoNaTela(
            texto="a{b}",
            papel="narrativa",
            inicio_s=1,
            fim_s=2,
            y=0.5,
            estilo={"animacao": "pop", "fonte": "arial_bold"},  # type: ignore[arg-type]
        ),
    ]
    estilos, eventos = legendas.eventos_textos(textos, ESPEC)
    assert [e.alinhamento for e in estilos] == [8, 5]
    assert estilos[1].fonte == "Arial" and estilos[1].negrito is True
    assert eventos[0].camada == 1 and r"\fad(150,150)" in eventos[0].texto
    assert r"\pos(540,960)" in eventos[1].texto and r"\fscx80" in eventos[1].texto
    assert eventos[1].texto.endswith("a(b)")


def test_gerar_ass_monta_cabecalho_estilos_e_eventos_em_ordem() -> None:
    plano = PlanoEdicao.model_validate(plano_valido(1, 3.0))
    ass = legendas.gerar_ass(plano, PALAVRAS, ESPEC)
    assert "PlayResX: 1080" in ass and "PlayResY: 1920" in ass
    assert sum(li.startswith("Style: ") for li in ass.splitlines()) == 1 + len(plano.textos)
    assert ass.count("Dialogue: ") == len(PALAVRAS) + len(plano.textos)
    linhas = [li for li in ass.splitlines() if li.startswith("Dialogue: ")]
    inicios = [li.split(",")[1] for li in linhas]
    assert inicios == sorted(inicios)
    assert legendas.tem_eventos(plano, ()) is True  # tem textos
    sem_textos = PlanoEdicao.model_validate({**plano_valido(1, 3.0), "textos": []})
    assert legendas.tem_eventos(sem_textos, ()) is False
    assert legendas.tem_eventos(sem_textos, PALAVRAS) is True


def test_ass_usa_a_resolucao_da_plataforma() -> None:
    espec = EspecificacaoVideo(540, 960, 25, "h264", False)
    plano = PlanoEdicao.model_validate(plano_valido(1, 3.0))
    ass = legendas.gerar_ass(plano, PALAVRAS, espec)
    assert "PlayResX: 540" in ass and "PlayResY: 960" in ass
    textos = [TextoNaTela(texto="x", papel="gancho", inicio_s=0, fim_s=1, posicao="topo", y=0.5)]
    estilos, eventos = legendas.eventos_textos(textos, espec)
    assert r"\pos(270,480)" in eventos[0].texto
    assert estilos[0].margem_v == round(200 / 1920 * 960) and estilos[0].margem_lateral == 30
