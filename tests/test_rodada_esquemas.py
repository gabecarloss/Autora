"""Esquemas da ideia do post (Conceito) e do plano de edição."""

from __future__ import annotations

import copy
from typing import Any

import pytest
from pydantic import ValidationError

from autora.edicao.plano import (
    DURACAO_MAXIMA_S,
    DURACAO_MINIMA_S,
    PlanoEdicao,
    verificar_contra_clipes,
)
from autora.rodada.esquemas import FORMATOS, Conceito
from tests.conftest import conceito_valido, plano_valido


def _conceito(**mudancas: Any) -> dict[str, Any]:
    d = conceito_valido([1])
    d.update(mudancas)
    return d


def _plano(mutar: Any = None) -> dict[str, Any]:
    d = copy.deepcopy(plano_valido(1, 3.0))
    if mutar:
        mutar(d)
    return d


# --- Conceito ------------------------------------------------------------------
def test_conceito_valido_e_aceito_e_nao_sei_vem_vazio_por_padrao() -> None:
    c = Conceito.model_validate(conceito_valido([1, 2]))
    assert c.ids_escolhidos() == {1, 2}
    d = conceito_valido([1])
    d.pop("nao_sei")
    assert Conceito.model_validate(d).nao_sei == []


def test_formato_fora_da_lista_e_recusado() -> None:
    assert "texto_narrativo" in FORMATOS
    with pytest.raises(ValidationError):
        Conceito.model_validate(_conceito(formato={"valor": "inventado", "motivo": "x" * 12}))


def test_formato_outro_exige_descricao() -> None:
    formato = {"valor": "outro", "motivo": "Nenhum formato da lista serve aqui."}
    with pytest.raises(ValidationError):
        Conceito.model_validate(_conceito(formato=formato))
    ok = Conceito.model_validate(_conceito(formato=formato, descricao_formato="um formato novo"))
    assert ok.descricao_formato == "um formato novo"


def test_elementos_autorais_de_tipo_repetido_sao_recusados() -> None:
    d = conceito_valido([1])
    d["elementos_autorais"][1]["tipo"] = d["elementos_autorais"][0]["tipo"]
    with pytest.raises(ValidationError):
        Conceito.model_validate(d)


def test_menos_de_dois_elementos_autorais_e_recusado() -> None:
    d = conceito_valido([1])
    d["elementos_autorais"] = d["elementos_autorais"][:1]
    with pytest.raises(ValidationError):
        Conceito.model_validate(d)


def test_gancho_igual_a_uma_alternativa_e_recusado() -> None:
    d = conceito_valido([1])
    d["alternativas_gancho"] = ["ELE JUROU QUE DAVA CERTO", "outra opção"]
    with pytest.raises(ValidationError):
        Conceito.model_validate(d)


def test_hashtag_sem_cerquilha_e_recusada() -> None:
    with pytest.raises(ValidationError):
        Conceito.model_validate(_conceito(hashtags=["humor", "#a", "#b"]))


def test_som_com_nome_sem_fonte_e_recusado() -> None:
    som = {"nome": "Faixa X", "funcao_no_video": "fundo leve", "motivo": "Combina com o ritmo."}
    with pytest.raises(ValidationError):
        Conceito.model_validate(_conceito(som=som))


def test_som_com_nome_e_fonte_e_aceito_e_nao_vem_verificado() -> None:
    som = {
        "nome": "Faixa X",
        "fonte": "TikTok, 06/11/2026",
        "funcao_no_video": "fundo leve",
        "motivo": "Combina com o ritmo.",
    }
    c = Conceito.model_validate(_conceito(som=som))
    assert c.som is not None
    assert c.som.verificado is False


def test_campo_desconhecido_e_recusado() -> None:
    with pytest.raises(ValidationError):
        Conceito.model_validate(_conceito(campo_inventado=1))


# --- PlanoEdicao ---------------------------------------------------------------
def test_plano_valido_calcula_duracao_e_inicios_dos_trechos() -> None:
    p = PlanoEdicao.model_validate(plano_valido(1, 3.0))
    assert p.duracao_s == pytest.approx(4.5)
    assert p.inicios_dos_trechos() == [0.0, 3.0]
    assert DURACAO_MINIMA_S == 3 and DURACAO_MAXIMA_S == 180


def test_texto_que_termina_depois_do_fim_e_recusado() -> None:
    d = _plano(lambda d: d["textos"][0].update(inicio_s=4.0, fim_s=5.0))
    with pytest.raises(ValidationError):
        PlanoEdicao.model_validate(d)


def test_capa_fora_do_video_e_recusada() -> None:
    d = _plano(lambda d: d["capa"].update(segundo=10.0))
    with pytest.raises(ValidationError):
        PlanoEdicao.model_validate(d)


def test_video_com_menos_de_tres_segundos_e_recusado() -> None:
    def curto(d: dict[str, Any]) -> None:
        d["trechos"] = [d["trechos"][0]]
        d["trechos"][0]["fim_s"] = 2.0
        d["textos"] = []
        d["capa"]["segundo"] = 0.5

    with pytest.raises(ValidationError):
        PlanoEdicao.model_validate(_plano(curto))


def test_trecho_menor_que_0_3_s_e_recusado() -> None:
    d = _plano(lambda d: d["trechos"][0].update(inicio_s=0.0, fim_s=0.2))
    with pytest.raises(ValidationError):
        PlanoEdicao.model_validate(d)


@pytest.mark.parametrize("velocidade", [0.4, 2.5])
def test_velocidade_fora_de_meio_a_dois_e_recusada(velocidade: float) -> None:
    d = _plano(lambda d: d["trechos"][1].update(velocidade=velocidade))
    with pytest.raises(ValidationError):
        PlanoEdicao.model_validate(d)


def test_cor_que_nao_e_hex_e_recusada_e_valida_vira_maiuscula() -> None:
    ruim = _plano(lambda d: d["textos"][0].update(estilo={"cor": "vermelho"}))
    with pytest.raises(ValidationError):
        PlanoEdicao.model_validate(ruim)
    ok = _plano(lambda d: d["textos"][0].update(estilo={"cor": "#ff00aa"}))
    assert PlanoEdicao.model_validate(ok).textos[0].estilo.cor == "#FF00AA"


def test_zoom_que_passa_do_fim_do_trecho_e_recusado() -> None:
    d = _plano(lambda d: d["trechos"][0].update(zoom={"inicio_s": 0.0, "fim_s": 5.0}))
    with pytest.raises(ValidationError):
        PlanoEdicao.model_validate(d)


def test_verificar_contra_clipes_devolve_vazio_quando_tudo_bate() -> None:
    p = PlanoEdicao.model_validate(plano_valido(1, 3.0))
    assert verificar_contra_clipes(p, {1: 3.0}, {1}) == []
    assert verificar_contra_clipes(p, {1: 3.0}, None) == []
    assert verificar_contra_clipes(p, {1: 2.96}, {1}) == []  # tolerância de 0,05


def test_verificar_contra_clipes_acusa_clipe_desconhecido() -> None:
    p = PlanoEdicao.model_validate(plano_valido(1, 3.0))
    assert verificar_contra_clipes(p, {2: 3.0}, None)


def test_verificar_contra_clipes_acusa_clipe_nao_permitido() -> None:
    p = PlanoEdicao.model_validate(plano_valido(1, 3.0))
    assert verificar_contra_clipes(p, {1: 3.0, 2: 3.0}, {2})


def test_verificar_contra_clipes_acusa_fim_maior_que_a_duracao() -> None:
    p = PlanoEdicao.model_validate(plano_valido(1, 3.0))
    assert verificar_contra_clipes(p, {1: 2.5}, {1})
