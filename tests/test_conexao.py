"""Escolha e troca do provedor do agente, sem chamar o agente real.

Decisão de 06/11/2026: a assinatura é o caminho principal e a chave da API é a
alternativa opcional. Trocar de provedor acontece só dentro de `autora.agente`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from autora.agente import conexao
from autora.agente.claude_api import ProvedorChave
from autora.agente.claude_assinatura import ProvedorAssinatura
from autora.agente.provedor import AgenteNaoConectado, Pedido, Resposta
from autora.config import global_config, segredos

TOKEN = "sk-ant-oat01-TOKEN-DE-TESTE-1234567890abcdef"
CHAVE = "sk-ant-api03-CHAVE-DE-TESTE-1234567890abcdef"


class ProvedorFalso:
    nome = "falso"

    def chamar(self, pedido: Pedido) -> Resposta:
        return Resposta("Pronto.", None, "m", 1, 1, 0, 0.001, 10)


@pytest.fixture
def claude_instalado(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    exe = tmp_path / "claude.exe"
    exe.write_text("")
    monkeypatch.setattr(conexao, "localizar_claude", lambda: exe)
    return exe


def _definir_tipo(dados: Path, tipo: str) -> None:
    cfg = global_config.carregar(dados)
    cfg.agente.tipo = tipo  # type: ignore[assignment]
    global_config.salvar(cfg, dados)


def test_padrao_e_nenhuma_conexao_e_assinatura_vem_primeiro(dados: Path) -> None:
    assert global_config.carregar(dados).agente.tipo == "nenhuma"
    with pytest.raises(AgenteNaoConectado):
        conexao.provedor_atual(dados)
    # A assinatura é o caminho principal: é o primeiro tipo real da enumeração.
    assert segredos.NOMES[0] == "agente_token_assinatura"


def test_provedor_atual_escolhe_pelo_tipo_configurado(dados: Path, claude_instalado: Path) -> None:
    _definir_tipo(dados, "assinatura")
    with pytest.raises(AgenteNaoConectado):  # tipo escolhido, mas sem token no cofre
        conexao.provedor_atual(dados)
    segredos.definir("agente_token_assinatura", TOKEN)
    p = conexao.provedor_atual(dados)
    assert isinstance(p, ProvedorAssinatura)
    assert p.executavel == claude_instalado
    assert p.pasta_isolada == conexao.pasta_isolada(dados)

    _definir_tipo(dados, "chave")
    with pytest.raises(AgenteNaoConectado):
        conexao.provedor_atual(dados)
    segredos.definir("agente_chave_api", CHAVE)
    assert isinstance(conexao.provedor_atual(dados), ProvedorChave)


def test_assinatura_exige_programa_instalado(dados: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(conexao, "localizar_claude", lambda: None)
    _definir_tipo(dados, "assinatura")
    segredos.definir("agente_token_assinatura", TOKEN)
    with pytest.raises(AgenteNaoConectado):
        conexao.provedor_atual(dados)
    r = conexao.conectar_assinatura(dados, TOKEN)
    assert r.ok is False and "não está instalado" in r.mensagem


def test_trocar_de_provedor_apaga_o_segredo_antigo(
    dados: Path, claude_instalado: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(conexao, "ProvedorChave", lambda chave: ProvedorFalso())
    monkeypatch.setattr(conexao, "ProvedorAssinatura", lambda exe, tok, pasta: ProvedorFalso())

    assert conexao.conectar_chave(dados, CHAVE).ok
    assert global_config.carregar(dados).agente.tipo == "chave"
    assert segredos.obter("agente_chave_api") == CHAVE

    assert conexao.conectar_assinatura(dados, TOKEN).ok
    cfg = global_config.carregar(dados).agente
    assert cfg.tipo == "assinatura" and cfg.ultimo_resultado == "ok"
    assert segredos.obter("agente_token_assinatura") == TOKEN
    assert segredos.obter("agente_chave_api") is None

    assert conexao.conectar_chave(dados, CHAVE).ok
    assert global_config.carregar(dados).agente.tipo == "chave"
    assert segredos.obter("agente_token_assinatura") is None

    conexao.desconectar(dados)
    assert global_config.carregar(dados).agente.tipo == "nenhuma"
    assert all(segredos.obter(n) is None for n in segredos.NOMES)


def test_codigo_com_formato_errado_nao_chama_o_agente(dados: Path, claude_instalado: Path) -> None:
    assert conexao.conectar_assinatura(dados, "abc").ok is False
    assert conexao.conectar_chave(dados, "abc").ok is False
    assert global_config.carregar(dados).agente.tipo == "nenhuma"
