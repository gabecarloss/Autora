"""Etapa de conceito: mensagem ao agente, conferência contra os clipes e decisão."""

from __future__ import annotations

from pathlib import Path

from autora.biblioteca.ficha import fichas_disponiveis
from autora.perfil.perfil import Perfil
from autora.plataformas.base import obter
from autora.rodada.conceito import (
    LIMITES_DESTA_VERSAO,
    conferir_conceito,
    decidir_conceito,
    descrever_perfil,
    descrever_plataforma,
    mensagem_conceito,
)
from autora.rodada.esquemas import Conceito
from tests.auxiliar_banco import abrir
from tests.conftest import ProvedorFalso, conceito_valido, secao_mandato_do_briefing


def _id_b(fichas) -> int:  # type: ignore[no-untyped-def]
    """b.mp4 dura 4 s, o que comporta a duração alvo (4 s) do conceito de exemplo."""
    return next(f.id for f in fichas if f.nome_arquivo == "b.mp4")


def _fichas(perfil: Perfil, dados: Path):  # type: ignore[no-untyped-def]
    con = abrir(perfil)
    try:
        return fichas_disponiveis(perfil, dados, con)
    finally:
        con.close()


def test_mensagem_tem_secoes_clipes_e_nenhum_caminho_absoluto(
    perfil_com_clipes_falsos: Perfil, dados: Path, tmp_path: Path
) -> None:
    fichas = _fichas(perfil_com_clipes_falsos, dados)
    msg = mensagem_conceito(perfil_com_clipes_falsos, obter("tiktok"), fichas)
    for secao in (
        "# Perfil",
        "# Plataforma",
        "# Limites desta versão",
        "# Padrão mínimo",
        "# Tarefa",
    ):
        assert secao in msg
    assert "<dados_externos" in msg
    for nome in ("a.mp4", "b.mp4", "c.mp4", "Cena A", "Cena B", "Cena C"):
        assert nome in msg
    assert str(tmp_path) not in msg
    assert "narração" in msg.lower()
    assert LIMITES_DESTA_VERSAO.strip() in msg


def test_descricoes_de_perfil_e_plataforma_nao_ficam_vazias(
    perfil_com_clipes_falsos: Perfil,
) -> None:
    assert descrever_perfil(perfil_com_clipes_falsos.config).strip()
    texto = descrever_plataforma(obter("tiktok"))
    assert "TikTok" in texto


def test_decidir_conceito_devolve_conceito_com_mandato_memoria_e_ferramentas(
    perfil_com_clipes_falsos: Perfil, dados: Path, provedor_falso: ProvedorFalso
) -> None:
    perfil = perfil_com_clipes_falsos
    fichas = _fichas(perfil, dados)
    provedor_falso.programar("conceito", conceito_valido([_id_b(fichas)]))
    con = abrir(perfil)
    c = decidir_conceito(
        perfil, provedor_falso, con, fichas, obter("tiktok"), rodada_id=None, post_id=None
    )
    con.close()
    assert isinstance(c, Conceito)
    pedido = provedor_falso.pedidos[0]
    assert pedido.etapa == "conceito"
    assert tuple(sorted(pedido.ferramentas)) == ("WebFetch", "WebSearch")
    mandato = secao_mandato_do_briefing().strip()
    assert mandato in pedido.sistema
    assert pedido.sistema.index(mandato) < pedido.sistema.index("Memória: ganchos.md")
    assert "Memória: ganchos.md" in pedido.sistema


def test_conceito_com_clipe_inexistente_e_acusado(
    perfil_com_clipes_falsos: Perfil, dados: Path
) -> None:
    fichas = _fichas(perfil_com_clipes_falsos, dados)
    ruim = Conceito.model_validate(conceito_valido([999]))
    assert conferir_conceito(ruim, fichas)
    bom = Conceito.model_validate(conceito_valido([_id_b(fichas)]))
    assert conferir_conceito(bom, fichas) == []


def test_decidir_conceito_pede_de_novo_quando_escolhe_clipe_inexistente(
    perfil_com_clipes_falsos: Perfil, dados: Path, provedor_falso: ProvedorFalso
) -> None:
    perfil = perfil_com_clipes_falsos
    fichas = _fichas(perfil, dados)
    provedor_falso.programar("conceito", conceito_valido([999]), conceito_valido([_id_b(fichas)]))
    con = abrir(perfil)
    c = decidir_conceito(
        perfil, provedor_falso, con, fichas, obter("tiktok"), rodada_id=None, post_id=None
    )
    con.close()
    assert c.ids_escolhidos() == {_id_b(fichas)}
    assert len(provedor_falso.pedidos) == 2


def test_nivel_chega_ao_pedido(
    perfil_com_clipes_falsos: Perfil, dados: Path, provedor_falso: ProvedorFalso
) -> None:
    perfil = perfil_com_clipes_falsos
    fichas = _fichas(perfil, dados)
    provedor_falso.programar("conceito", conceito_valido([_id_b(fichas)]))
    con = abrir(perfil)
    decidir_conceito(
        perfil,
        provedor_falso,
        con,
        fichas,
        obter("tiktok"),
        rodada_id=None,
        post_id=None,
        nivel="maximo",
    )
    con.close()
    assert provedor_falso.pedidos[0].nivel == "maximo"
