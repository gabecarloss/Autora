"""Integração com o agente REAL. Roda só com `uv run pytest -m agente`.

Usa a conexão configurada no app (pasta de dados real). Se o agente não estiver
conectado, o teste é pulado. Os testes com clipes sintéticos precisam de ffmpeg; a rodada
completa também roda o Whisper (baixa o modelo na primeira vez).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from autora.agente import conexao
from autora.agente.provedor import ProvedorAgente
from autora.biblioteca.ficha import fichas_disponiveis
from autora.config.global_config import pasta_dados
from autora.perfil.perfil import Perfil
from autora.plataformas.base import obter
from autora.rodada.conceito import decidir_conceito
from autora.rodada.executar import gerar

pytestmark = pytest.mark.agente

# PROVISÓRIO: lista de aberturas genéricas que o mandato proíbe ("não escreve gancho
# genérico"). A bateria do passo 4 substitui isto pelo detector por idioma (seção 14.2).
GANCHOS_GENERICOS = (
    "você não vai acreditar",
    "espere até o final",
    "assista até o fim",
    "olha isso",
    "isso é incrível",
    "você precisa ver",
    "não acredito",
)


@pytest.fixture(autouse=True)
def cofre() -> None:  # sobrepõe o cofre falso: aqui usamos o cofre real
    return None


@pytest.fixture
def provedor_real() -> ProvedorAgente:
    os.environ.pop("AUTORA_DADOS", None)
    try:
        return conexao.provedor_atual(pasta_dados())
    except conexao.AgenteNaoConectado:
        pytest.skip("agente não conectado no app")


def test_agente_real_responde() -> None:
    os.environ.pop("AUTORA_DADOS", None)
    dados = pasta_dados()
    try:
        conexao.provedor_atual(dados)
    except conexao.AgenteNaoConectado:
        pytest.skip("agente não conectado no app")
    r = conexao.testar(dados)
    assert r.ok, r.mensagem
    assert r.resposta
    assert r.duracao_ms and r.duracao_ms > 0


@pytest.mark.ffmpeg
def test_agente_real_decide_ideia_coerente_com_as_fichas(
    provedor_real: ProvedorAgente, perfil_sintetico: Perfil, dados: Path
) -> None:
    perfil = perfil_sintetico
    perfil.config.identidade.personalidade_adjetivos = ["irônico", "rápido", "observador"]
    perfil.config.conteudo.nichos = [{"nome": "humor"}]  # type: ignore[list-item]
    perfil.config.identidade.idioma_saida = "pt-BR"
    perfil.salvar_config()
    with perfil.conectar() as con:
        fichas = fichas_disponiveis(perfil, dados, con, transcrever=None)
        conceito = decidir_conceito(
            perfil, provedor_real, con, fichas, obter("tiktok"), rodada_id=None, post_id=None
        )
        chamadas = con.execute("SELECT etapa, resultado FROM chamada_servico").fetchall()
    ids = {f.id for f in fichas}
    assert conceito.ids_escolhidos() <= ids
    gancho = conceito.gancho.valor.lower()
    assert not any(g in gancho for g in GANCHOS_GENERICOS), gancho
    assert len({e.tipo for e in conceito.elementos_autorais}) >= 2
    r = conceito.raciocinio
    respostas = [
        r.sei_com_certeza,
        r.estou_supondo,
        r.o_melhor_criador_faria,
        r.pode_dar_errado_e_como_percebo,
        r.motivo_da_escolha,
    ]
    assert len(set(respostas)) == 5 and all(len(x) >= 10 for x in respostas)
    assert all(c.motivo.strip() for c in conceito.clipes_escolhidos)
    assert chamadas and all(c["etapa"] == "conceito" for c in chamadas)
    eventos = perfil.registro.ler_dia(__import__("autora.util.tempo", fromlist=["hoje"]).hoje())
    assert any(e["tipo"] == "servico" and "respondeu" in e["mensagem"] for e in eventos)


@pytest.mark.ffmpeg
@pytest.mark.whisper
def test_agente_real_rodada_completa_com_clipes_sinteticos(
    provedor_real: ProvedorAgente, perfil_sintetico: Perfil, dados: Path
) -> None:
    perfil = perfil_sintetico
    perfil.config.identidade.idioma_saida = "pt-BR"
    perfil.salvar_config()
    resultado = gerar(perfil, provedor_real, dados, origem="teste")
    assert resultado.ok, resultado.mensagem
    assert resultado.pasta_saida is not None
    for nome in ("video.mp4", "post.md", "capa.jpg", "roteiro.json"):
        assert (resultado.pasta_saida / nome).is_file(), nome
    with perfil.conectar() as con:
        post = con.execute(
            "SELECT estado, gancho FROM post WHERE id = ?", (resultado.post_id,)
        ).fetchone()
        decisoes = con.execute(
            "SELECT COUNT(*) FROM decisao WHERE post_id = ?", (resultado.post_id,)
        ).fetchone()[0]
        custo = con.execute(
            "SELECT SUM(tokens_entrada), SUM(tokens_saida), SUM(custo_usd) FROM chamada_servico"
        ).fetchone()
    assert post["estado"] == "aguardando_revisao" and post["gancho"]
    assert decisoes >= 8
    assert post["gancho"] in (resultado.pasta_saida / "post.md").read_text(encoding="utf-8")
    # Medição de consumo (provisório do passo 2): fica no log do teste para o fechamento.
    perfil.registro.registrar(
        "teste",
        "Consumo da rodada de teste com o agente real.",
        detalhe={"tokens_entrada": custo[0], "tokens_saida": custo[1], "custo_usd": custo[2]},
    )
