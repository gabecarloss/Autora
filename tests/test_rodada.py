"""Rodada de geração: do pedido ao pacote, com agente e motor simulados."""

from __future__ import annotations

import copy
from datetime import date
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from autora.agente.provedor import ErroAgente
from autora.config import global_config
from autora.edicao.ffmpeg import InfoVideo
from autora.edicao.renderizador import Entrega, ErroRender
from autora.perfil.perfil import Perfil, PerfilOcupado
from autora.rodada.executar import codigo_idioma, gerar
from autora.util.tempo import hoje
from tests.auxiliar_banco import abrir
from tests.conftest import (
    ProvedorFalso,
    conceito_valido,
    plano_valido,
    secao_mandato_do_briefing,
)

INFO = InfoVideo(1080, 1920, Fraction(30), "h264", "yuv420p", "aac", 48000, 2, 4.5)


class RenderizadorFalso:
    def __init__(self, erro: Exception | None = None) -> None:
        self.erro = erro
        self.chamadas: list[dict[str, Any]] = []

    def __call__(
        self,
        plano: Any,
        clipes: Any,
        destino: Path,
        *,
        espec: Any,
        registro: Any,
        idioma: Any,
        pasta_modelos: Any,
        rodada_id: Any,
        post_id: Any,
        transcritor: Any = None,
    ) -> Entrega:
        self.chamadas.append(
            {
                "plano": plano,
                "clipes": dict(clipes),
                "destino": destino,
                "espec": espec,
                "idioma": idioma,
                "rodada_id": rodada_id,
                "post_id": post_id,
            }
        )
        if self.erro:
            raise self.erro
        destino.mkdir(parents=True, exist_ok=True)
        (destino / "video.mp4").write_bytes(b"video")
        (destino / "capa.jpg").write_bytes(b"capa")
        return Entrega(
            destino / "video.mp4", destino / "capa.jpg", plano.duracao_s, "sem_fala", None, INFO, []
        )


def _consulta(perfil: Perfil, sql: str, args: tuple[Any, ...] = ()) -> list[Any]:
    con = abrir(perfil)
    try:
        return con.execute(sql, args).fetchall()
    finally:
        con.close()


def _rodar(
    perfil: Perfil, provedor: ProvedorFalso, dados: Path, render: RenderizadorFalso | None = None
) -> Any:
    return gerar(
        perfil,
        provedor,
        dados,
        origem="manual",
        renderizar=render or RenderizadorFalso(),
        transcrever_clipe=lambda caminho: None,
    )


def _programado() -> ProvedorFalso:
    return (
        ProvedorFalso()
        .programar("conceito", conceito_valido([2]))
        .programar("plano", plano_valido(2, 4.0))
    )


def test_rodada_feliz_entrega_o_pacote_e_registra_tudo(
    perfil_com_clipes_falsos: Perfil, dados: Path
) -> None:
    perfil = perfil_com_clipes_falsos
    provedor, render = _programado(), RenderizadorFalso()
    r = _rodar(perfil, provedor, dados, render)

    assert r.ok is True, r.mensagem
    pasta = dados / "saida" / "teste" / date.today().isoformat() / "1"
    assert r.pasta_saida is not None and Path(r.pasta_saida).resolve() == pasta.resolve()
    for nome in ("video.mp4", "capa.jpg", "post.md", "roteiro.json"):
        assert (pasta / nome).exists(), nome
    assert "ele jurou que dava certo" in (pasta / "post.md").read_text(encoding="utf-8")

    rodada = _consulta(perfil, "SELECT estado, videos_entregues FROM rodada")
    assert [tuple(x) for x in rodada] == [("concluida", 1)]
    post = _consulta(perfil, "SELECT estado, pasta_saida FROM post")[0]
    assert post[0] == "aguardando_revisao"
    assert not Path(post[1]).is_absolute()
    assert ":" not in post[1] and str(dados) not in post[1]
    assert {x[0] for x in _consulta(perfil, "SELECT video_id FROM post_video")} == {2}

    etapas = {x[0]: x[1] for x in _consulta(perfil, "SELECT etapa, estado FROM etapa_execucao")}
    for nome in ("estudo", "revisor", "verificacoes"):
        assert etapas[nome] == "pulada"
    for nome in ("selecao", "conceito", "plano", "edicao", "pacote"):
        assert etapas[nome] == "ok"
    ordem = [x[0] for x in _consulta(perfil, "SELECT etapa FROM etapa_execucao ORDER BY id")]
    ok = [e for e in ordem if etapas[e] == "ok"]
    assert ok == ["selecao", "conceito", "plano", "edicao", "pacote"]

    decisoes = _consulta(perfil, "SELECT campo, motivo FROM decisao")
    campos = {x[0] for x in decisoes}
    assert {
        "formato",
        "gancho",
        "horario",
        "capa",
        "clipe",
        "elemento_autoral",
        "ritmo",
        "textos",
    } <= campos
    assert all(x[1].strip() for x in decisoes)

    chamadas = _consulta(perfil, "SELECT etapa FROM chamada_servico ORDER BY id")
    assert [x[0] for x in chamadas] == ["conceito", "plano"]

    tipos = {e.get("tipo") for e in perfil.registro.ler_dia(date.today())}
    assert {"rodada", "etapa", "decisao", "servico"} <= tipos

    assert len(render.chamadas) == 1
    chamada = render.chamadas[0]
    assert list(chamada["clipes"]) == [2]
    assert chamada["clipes"][2].name == "b.mp4" and chamada["clipes"][2].exists()
    assert isinstance(chamada["rodada_id"], int) and isinstance(chamada["post_id"], int)


def test_segunda_rodada_nao_reusa_o_clipe_ja_usado(
    perfil_com_clipes_falsos: Perfil, dados: Path
) -> None:
    perfil = perfil_com_clipes_falsos
    assert _rodar(perfil, _programado(), dados).ok

    c1 = conceito_valido([1])
    c1["duracao_alvo_s"] = 3
    provedor = (
        ProvedorFalso()
        .programar("conceito", conceito_valido([2]), c1)
        .programar("plano", plano_valido(1, 3.0))
    )
    r = _rodar(perfil, provedor, dados)

    assert r.ok is True, r.mensagem
    assert len(provedor.pedidos) == 3
    assert [p.etapa for p in provedor.pedidos].count("conceito") == 2
    assert [p.etapa for p in provedor.pedidos].count("plano") == 1
    pedidos_conceito = [p for p in provedor.pedidos if p.etapa == "conceito"]
    assert "Problemas da resposta anterior" in pedidos_conceito[1].mensagem
    usados = {x[0] for x in _consulta(perfil, "SELECT video_id FROM post_video WHERE post_id = 2")}
    assert usados == {1}


def test_conceito_invalido_duas_vezes_falha_sem_excecao(
    perfil_com_clipes_falsos: Perfil, dados: Path
) -> None:
    perfil = perfil_com_clipes_falsos
    provedor = ProvedorFalso().programar("conceito", {"a": 1}, {"a": 1})
    r = _rodar(perfil, provedor, dados)

    assert r.ok is False and r.mensagem.strip()
    assert _consulta(perfil, "SELECT estado FROM post")[0][0] == "falhou"
    rodada = _consulta(perfil, "SELECT estado, observacao FROM rodada")[0]
    assert rodada[0] == "falhou" and rodada[1]
    etapas = {x[0]: x[1] for x in _consulta(perfil, "SELECT etapa, estado FROM etapa_execucao")}
    assert etapas["conceito"] == "falhou"


def test_erro_do_agente_vira_mensagem_amigavel(
    perfil_com_clipes_falsos: Perfil, dados: Path
) -> None:
    perfil = perfil_com_clipes_falsos
    r = _rodar(perfil, ProvedorFalso(ErroAgente("O agente caiu.")), dados)
    assert r.ok is False
    assert r.mensagem == "O agente caiu."
    assert _consulta(perfil, "SELECT estado FROM rodada")[0][0] == "falhou"


def test_roteiro_sem_padrao_minimo_e_pedido_de_novo(
    perfil_com_clipes_falsos: Perfil, dados: Path
) -> None:
    perfil = perfil_com_clipes_falsos
    fraco = copy.deepcopy(plano_valido(2, 4.0))
    fraco["trechos"] = [fraco["trechos"][0]]
    fraco["textos"] = []
    fraco["capa"]["segundo"] = 1.0
    provedor = (
        ProvedorFalso()
        .programar("conceito", conceito_valido([2]))
        .programar("plano", fraco, plano_valido(2, 4.0))
    )
    r = _rodar(perfil, provedor, dados)
    assert r.ok is True, r.mensagem
    assert [p.etapa for p in provedor.pedidos].count("plano") == 2


def test_falha_do_motor_de_edicao_nao_grava_pacote(
    perfil_com_clipes_falsos: Perfil, dados: Path
) -> None:
    perfil = perfil_com_clipes_falsos
    r = _rodar(perfil, _programado(), dados, RenderizadorFalso(ErroRender("quebrou")))
    assert r.ok is False and "quebrou" in r.mensagem
    etapas = {x[0]: x[1] for x in _consulta(perfil, "SELECT etapa, estado FROM etapa_execucao")}
    assert etapas["edicao"] == "falhou"
    assert not list((dados / "saida").rglob("post.md"))


def test_sem_material_falha_sem_chamar_o_agente(dados: Path) -> None:
    perfil = Perfil.criar(dados, "vazio", "Vazio")
    provedor = ProvedorFalso()
    r = _rodar(perfil, provedor, dados)
    assert r.ok is False
    assert any(p in r.mensagem.lower() for p in ("vídeo", "video", "pasta"))
    assert _consulta(perfil, "SELECT estado FROM rodada")[0][0] == "falhou"
    assert provedor.pedidos == []


def test_nivel_escolhido_na_tela_chega_ao_pedido(
    perfil_com_clipes_falsos: Perfil, dados: Path
) -> None:
    cfg = global_config.carregar(dados)
    cfg.agente.niveis["conceito"] = "maximo"
    cfg.agente.niveis["plano"] = "rapido"
    global_config.salvar(cfg, dados)

    provedor = _programado()
    assert _rodar(perfil_com_clipes_falsos, provedor, dados).ok
    por_etapa = {p.etapa: p.nivel for p in provedor.pedidos}
    assert por_etapa["conceito"] == "maximo"
    assert por_etapa["plano"] == "rapido"


def test_pedidos_levam_o_mandato_e_dados_externos(
    perfil_com_clipes_falsos: Perfil, dados: Path
) -> None:
    provedor = _programado()
    assert _rodar(perfil_com_clipes_falsos, provedor, dados).ok
    mandato = secao_mandato_do_briefing()
    for p in provedor.pedidos:
        assert mandato in p.sistema
    plano = next(p for p in provedor.pedidos if p.etapa == "plano")
    assert "<dados_externos" in plano.mensagem
    assert "expectativa quebrada" in plano.mensagem or "ele jurou que dava certo" in plano.mensagem


def test_perfil_ocupado_propaga(perfil_com_clipes_falsos: Perfil, dados: Path) -> None:
    perfil = perfil_com_clipes_falsos
    with perfil.trava(), pytest.raises(PerfilOcupado):
        _rodar(perfil, _programado(), dados)


def test_codigo_do_idioma() -> None:
    assert codigo_idioma("pt-BR") == "pt"
    assert codigo_idioma("português") is None
    assert codigo_idioma(None) is None


def test_transcritor_de_clipes_e_falha_isolada(
    perfil_com_clipes_falsos: Perfil, dados: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from autora.edicao.ffmpeg import ErroFfmpeg
    from autora.rodada import executar as mod

    perfil = perfil_com_clipes_falsos
    # sem ffmpeg: devolve None e avisa no log
    monkeypatch.setattr(mod, "localizar_ffmpeg", lambda: None)
    assert mod.transcritor_de_clipes(perfil, dados)(Path("a.mp4")) is None
    # com ffmpeg que falha ao extrair o áudio: devolve None, registra, não levanta
    monkeypatch.setattr(mod, "localizar_ffmpeg", lambda: (Path("ffmpeg"), Path("ffprobe")))

    def extrair_quebrado(video: Path, destino: Path, ffmpeg: Path | None = None) -> Path:
        raise ErroFfmpeg("O ffmpeg devolveu um erro.", ["ffmpeg"], "sem áudio")

    monkeypatch.setattr(mod, "extrair_audio_wav", extrair_quebrado)
    assert mod.transcritor_de_clipes(perfil, dados)(Path("a.mp4")) is None
    eventos = perfil.registro.ler_dia(hoje())
    assert any("sem transcrição" in e["mensagem"] for e in eventos)
    assert any("não está instalado" in e["mensagem"] for e in eventos)


def test_motor_recebe_a_especificacao_da_plataforma_e_a_tela_recebe_pasta_relativa(
    perfil_com_clipes_falsos: Perfil, dados: Path, provedor_falso: Any
) -> None:
    from autora.plataformas.base import obter
    from autora.rodada.executar import pasta_para_tela

    provedor_falso.programar("conceito", conceito_valido([2])).programar(
        "plano", plano_valido(2, 4.0)
    )
    render = RenderizadorFalso()
    r = gerar(
        perfil_com_clipes_falsos,
        provedor_falso,
        dados,
        renderizar=render,
        transcrever_clipe=lambda c: None,
    )
    assert r.ok, r.mensagem
    assert render.chamadas[0]["espec"] == obter("tiktok").video
    assert r.pasta_relativa is not None
    assert r.pasta_relativa.startswith("saida/teste/") and r.pasta_relativa.endswith("/1")
    assert ":" not in r.pasta_relativa and "\\" not in r.pasta_relativa
    # pasta de saída fora da pasta de dados: cai para o caminho relativo à própria saída
    assert pasta_para_tela(Path(r"C:\outro\lugar6-11-06"), dados, "2026-11-06/3") == "2026-11-06/3"


def test_regras_do_roteiro_usam_a_plataforma_do_perfil() -> None:
    from autora.plataformas.base import EspecificacaoVideo
    from autora.rodada.plano import regras_do_roteiro

    texto = regras_do_roteiro(EspecificacaoVideo(720, 1280, 25, "h264", False))
    assert "720x1280, 25 fps" in texto and "1080" not in texto
