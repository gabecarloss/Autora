"""Chamada ao agente com esquema: validação, repetição única e nível por etapa."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel, Field

from autora.agente.provedor import ErroAgente, RespostaInvalida
from autora.config import global_config
from autora.perfil.perfil import Perfil
from autora.rodada.chamada import chamar_com_esquema, esquema_para_agente, nivel_configurado
from autora.util.tempo import hoje
from tests.auxiliar_banco import abrir
from tests.conftest import ProvedorFalso, secao_mandato_do_briefing


class R(BaseModel):
    a: int


def _chamar(provedor: ProvedorFalso, perfil: Perfil, **kw: object) -> R:
    con = abrir(perfil)
    try:
        return chamar_com_esquema(
            provedor,
            perfil,
            con,
            etapa="conceito",
            mensagem="faça",
            modelo=R,
            rodada_id=None,
            post_id=None,
            **kw,  # type: ignore[arg-type]
        )
    finally:
        con.close()


@pytest.fixture
def perfil(dados: Path) -> Perfil:
    return Perfil.criar(dados, "humor", "Humor")


def test_resposta_valida_na_primeira_devolve_objeto_com_mandato_primeiro(
    perfil: Perfil, provedor_falso: ProvedorFalso
) -> None:
    provedor_falso.programar("conceito", {"a": 1})
    r = _chamar(provedor_falso, perfil)
    assert r.a == 1
    assert len(provedor_falso.pedidos) == 1
    pedido = provedor_falso.pedidos[0]
    mandato = secao_mandato_do_briefing().strip()
    assert mandato in pedido.sistema
    assert pedido.sistema.index(mandato) < pedido.sistema.index("# Regras sobre dados externos")
    assert pedido.esquema_json is not None
    assert pedido.esquema_json["additionalProperties"] is False


def test_resposta_invalida_pede_de_novo_uma_vez_com_problemas_e_registra(
    perfil: Perfil, provedor_falso: ProvedorFalso
) -> None:
    provedor_falso.programar("conceito", {"a": "texto"}, {"a": 2})
    r = _chamar(provedor_falso, perfil)
    assert r.a == 2
    assert len(provedor_falso.pedidos) == 2
    assert "Problemas da resposta anterior" in provedor_falso.pedidos[1].mensagem
    assert "Problemas da resposta anterior" not in provedor_falso.pedidos[0].mensagem
    eventos = perfil.registro.ler_dia(hoje())
    etapas = [e for e in eventos if e.get("tipo") == "etapa" and "problemas" in str(e)]
    assert etapas
    assert any(isinstance(e.get("detalhe"), dict) and e["detalhe"].get("problemas") for e in etapas)


def test_duas_respostas_invalidas_levantam_resposta_invalida(
    perfil: Perfil, provedor_falso: ProvedorFalso
) -> None:
    provedor_falso.programar("conceito", {"a": "x"}, {"b": 1})
    with pytest.raises(RespostaInvalida):
        _chamar(provedor_falso, perfil)
    assert len(provedor_falso.pedidos) == 2


def test_conferencia_com_problemas_conta_como_invalida_e_repete_uma_vez(
    perfil: Perfil, provedor_falso: ProvedorFalso
) -> None:
    provedor_falso.programar("conceito", {"a": 1}, {"a": 5})
    r = _chamar(
        provedor_falso, perfil, conferir=lambda o: ["a precisa ser maior"] if o.a < 5 else []
    )
    assert r.a == 5
    assert len(provedor_falso.pedidos) == 2
    assert "a precisa ser maior" in provedor_falso.pedidos[1].mensagem


def test_conferencia_que_nunca_passa_levanta_resposta_invalida(
    perfil: Perfil, provedor_falso: ProvedorFalso
) -> None:
    provedor_falso.programar("conceito", {"a": 1}, {"a": 1})
    with pytest.raises(RespostaInvalida):
        _chamar(provedor_falso, perfil, conferir=lambda o: ["sempre ruim"])
    assert len(provedor_falso.pedidos) == 2


def test_erro_do_agente_propaga_sem_repetir(perfil: Perfil) -> None:
    provedor = ProvedorFalso(erro=ErroAgente("caiu"))
    with pytest.raises(ErroAgente):
        _chamar(provedor, perfil)
    assert len(provedor.pedidos) == 1


def test_nivel_informado_chega_ao_pedido(perfil: Perfil, provedor_falso: ProvedorFalso) -> None:
    provedor_falso.programar("conceito", {"a": 1})
    _chamar(provedor_falso, perfil, nivel="maximo")
    assert provedor_falso.pedidos[0].nivel == "maximo"


def test_esquema_para_agente_move_restricoes_para_a_descricao() -> None:
    class M(BaseModel):
        nome: str = Field(min_length=3)

    esquema = esquema_para_agente(M)
    assert esquema["additionalProperties"] is False
    assert "minLength" not in esquema["properties"]["nome"]
    assert "3" in esquema["properties"]["nome"]["description"]


def test_nivel_configurado_padrao_e_valor_gravado(dados: Path) -> None:
    assert nivel_configurado(dados, "conceito") == "automatico"
    cfg = global_config.carregar(dados)
    cfg.agente.niveis["conceito"] = "maximo"
    global_config.salvar(cfg, dados)
    assert nivel_configurado(dados, "conceito") == "maximo"
