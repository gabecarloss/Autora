"""Servidor local: sessão, host, segredos nunca devolvidos."""

from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from autora.agente import conexao
from autora.agente.provedor import Pedido, Resposta
from autora.api.main import criar_app
from autora.config import global_config, segredos

SESSAO = "token-de-sessao-de-teste"
TOKEN = "sk-ant-oat01-SEGREDO-API-TESTE-0987654321zyxw"


@pytest.fixture
def cliente(dados: Path) -> TestClient:
    app = criar_app(dados, SESSAO, pasta_front=None)
    return TestClient(app, base_url="http://127.0.0.1")


def _h() -> dict[str, str]:
    return {"X-Autora-Sessao": SESSAO}


def test_sem_sessao_e_recusado(cliente: TestClient) -> None:
    assert cliente.get("/api/sistema").status_code == 401
    assert cliente.get("/api/sistema", headers={"X-Autora-Sessao": "errado"}).status_code == 401
    assert cliente.get("/").status_code == 401


def test_host_estranho_e_recusado(dados: Path) -> None:
    c = TestClient(criar_app(dados, SESSAO, pasta_front=None), base_url="http://evil.example")
    assert c.get("/api/sistema", headers=_h()).status_code == 400


def test_entrar_troca_token_por_cookie(cliente: TestClient) -> None:
    r = cliente.get(f"/entrar?s={SESSAO}", follow_redirects=False)
    assert r.status_code == 303
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    assert cliente.get("/api/sistema").status_code == 200  # cookie guardado
    assert cliente.get("/entrar?s=errado", follow_redirects=False).status_code == 401


def test_cabecalhos_de_seguranca_e_docs_desligados(cliente: TestClient) -> None:
    r = cliente.get("/api/sistema", headers=_h())
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["x-content-type-options"] == "nosniff"
    assert cliente.get("/api/docs", headers=_h()).status_code == 404
    assert cliente.get("/api/openapi.json", headers=_h()).status_code == 404


def test_pausar_ligar_e_modo(cliente: TestClient, dados: Path) -> None:
    assert cliente.get("/api/sistema", headers=_h()).json()["estado"] == "ligado"
    assert cliente.post("/api/sistema/pausar", headers=_h()).json()["estado"] == "pausado"
    r = cliente.put("/api/sistema/modo", json={"modo": "manual"}, headers=_h()).json()
    assert r["estado"] == "pausado" and r["modo"] == "manual"  # pausa preserva o modo
    assert cliente.post("/api/sistema/ligar", headers=_h()).json()["estado"] == "manual"
    assert global_config.carregar(dados).modo == "manual"


class ProvedorFalso:
    nome = "falso"

    def chamar(self, pedido: Pedido) -> Resposta:
        return Resposta("Pronto.", None, "m", 1, 1, 0, 0.001, 10)


def test_conectar_nunca_devolve_nem_grava_o_segredo(
    cliente: TestClient, dados: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(conexao, "ProvedorChave", lambda chave: ProvedorFalso())
    r = cliente.post("/api/agente/conectar/chave", json={"chave": TOKEN}, headers=_h())
    assert r.status_code == 200 and r.json()["ok"] is True
    assert TOKEN not in r.text
    estado = cliente.get("/api/agente", headers=_h())
    assert estado.json()["tipo"] == "chave"
    assert TOKEN not in estado.text
    assert segredos.obter("agente_chave_api") == TOKEN  # só no cofre
    # Nenhum arquivo da pasta de dados contém o segredo.
    for arq in dados.rglob("*"):
        if arq.is_file():
            assert TOKEN.encode() not in arq.read_bytes(), arq


def test_conectar_assinatura_pela_rota(
    cliente: TestClient, dados: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    exe = tmp_path / "claude.exe"
    exe.write_text("")
    monkeypatch.setattr(conexao, "localizar_claude", lambda: exe)
    monkeypatch.setattr(conexao, "ProvedorAssinatura", lambda exe, tok, pasta: ProvedorFalso())
    r = cliente.post("/api/agente/conectar/assinatura", json={"token": TOKEN}, headers=_h())
    assert r.status_code == 200 and r.json()["ok"] is True
    assert TOKEN not in r.text
    estado = cliente.get("/api/agente", headers=_h())
    assert estado.json()["tipo"] == "assinatura"
    assert TOKEN not in estado.text
    assert segredos.obter("agente_token_assinatura") == TOKEN
    assert segredos.obter("agente_chave_api") is None


def test_conexao_que_falha_no_teste_nao_e_guardada(
    cliente: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from autora.agente.provedor import AgenteNaoConectado

    class Recusa(ProvedorFalso):
        def chamar(self, pedido: Pedido) -> Resposta:
            raise AgenteNaoConectado("A chave da API não foi aceita.")

    monkeypatch.setattr(conexao, "ProvedorChave", lambda chave: Recusa())
    r = cliente.post("/api/agente/conectar/chave", json={"chave": TOKEN}, headers=_h()).json()
    assert r["ok"] is False
    assert segredos.obter("agente_chave_api") is None


def test_erro_de_validacao_nao_ecoa_o_valor(cliente: TestClient) -> None:
    r = cliente.post("/api/agente/desconectar", json={"confirmar": TOKEN}, headers=_h())
    assert r.status_code == 422
    assert TOKEN not in r.text


def test_desconectar_exige_confirmacao_e_apaga(
    cliente: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(conexao, "ProvedorChave", lambda chave: ProvedorFalso())
    cliente.post("/api/agente/conectar/chave", json={"chave": TOKEN}, headers=_h())
    assert cliente.post("/api/agente/desconectar", json={}, headers=_h()).status_code == 422
    r = cliente.post("/api/agente/desconectar", json={"confirmar": True}, headers=_h())
    assert r.json()["tipo"] == "nenhuma"
    assert segredos.obter("agente_chave_api") is None


def test_criar_e_listar_perfis(cliente: TestClient) -> None:
    r = cliente.post("/api/perfis", json={"slug": "humor", "nome": "Humor"}, headers=_h())
    assert r.status_code == 201
    assert (
        cliente.post("/api/perfis", json={"slug": "humor", "nome": "x"}, headers=_h()).status_code
        == 409
    )
    assert (
        cliente.post("/api/perfis", json={"slug": "../x", "nome": "x"}, headers=_h()).status_code
        == 422
    )
    lista = cliente.get("/api/perfis", headers=_h()).json()
    assert len(lista) == 1
    assert {k: lista[0][k] for k in ("slug", "nome", "pausado", "estado")} == {
        "slug": "humor",
        "nome": "Humor",
        "pausado": False,
        "estado": "ok",
    }
    assert lista[0]["criacao"]["estado"] == "ocioso"


@pytest.mark.parametrize(
    ("metodo", "rota", "corpo"),
    [
        ("put", "/api/sistema/modo", {"modo": "manual"}),
        ("post", "/api/perfis", {"slug": "humor", "nome": "Humor"}),
        ("put", "/api/agente/niveis", {"niveis": {"estudo": "rapido"}}),
        ("post", "/api/agente/desconectar", {"confirmar": True}),
        ("post", "/api/agente/conectar/chave", {"chave": TOKEN}),
    ],
)
def test_campo_desconhecido_no_pedido_e_recusado(
    cliente: TestClient, metodo: str, rota: str, corpo: dict[str, object]
) -> None:
    r = cliente.request(metodo, rota, json={**corpo, "inesperado": 1}, headers=_h())
    assert r.status_code == 422
    assert TOKEN not in r.text  # o erro de validação não ecoa o segredo


@pytest.fixture(autouse=True)
def _isolar_criacao() -> Iterator[None]:
    from autora.rodada import estado

    estado.limpar()
    yield
    estado.limpar()


def _conectar_falso(cliente: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(conexao, "ProvedorChave", lambda chave: ProvedorFalso())
    r = cliente.post("/api/agente/conectar/chave", json={"chave": TOKEN}, headers=_h())
    assert r.json()["ok"] is True


def _criar_humor(cliente: TestClient) -> None:
    r = cliente.post("/api/perfis", json={"slug": "humor", "nome": "Humor"}, headers=_h())
    assert r.status_code == 201


def _criacao_do_humor(cliente: TestClient) -> dict[str, Any]:
    lista = cliente.get("/api/perfis", headers=_h()).json()
    return next(p for p in lista if p["slug"] == "humor")["criacao"]


def _esperar_estado(cliente: TestClient, estado: str) -> dict[str, Any]:
    fim = time.monotonic() + 5
    criacao = _criacao_do_humor(cliente)
    while criacao["estado"] != estado and time.monotonic() < fim:
        time.sleep(0.05)
        criacao = _criacao_do_humor(cliente)
    return criacao


def _gerar_falso(monkeypatch: pytest.MonkeyPatch, pasta: Path, espera_s: float = 0.0) -> None:
    from autora.api.rotas import perfis as rotas_perfis
    from autora.rodada.executar import ResultadoRodada

    def _falso(*args: Any, **kwargs: Any) -> ResultadoRodada:
        time.sleep(espera_s)
        return ResultadoRodada(
            True, "Post pronto para revisão.", 1, 1, pasta, "saida/humor/2026-11-06/1"
        )

    monkeypatch.setattr(rotas_perfis, "gerar", _falso)


def test_criar_agora_sem_agente_conectado_responde_400(cliente: TestClient) -> None:
    _criar_humor(cliente)
    r = cliente.post("/api/perfis/humor/criar-agora", headers=_h())
    assert r.status_code == 400
    assert str(r.json()["detail"]).strip()


def test_criar_agora_perfil_inexistente_e_slug_invalido(cliente: TestClient) -> None:
    assert cliente.post("/api/perfis/nao-existe/criar-agora", headers=_h()).status_code == 404
    assert cliente.post("/api/perfis/A B/criar-agora", headers=_h()).status_code == 422


def test_criar_agora_comeca_em_segundo_plano_e_termina_pronto(
    cliente: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _criar_humor(cliente)
    assert _criacao_do_humor(cliente)["estado"] == "ocioso"
    _conectar_falso(cliente, monkeypatch)
    _gerar_falso(monkeypatch, tmp_path / "saida" / "humor" / "1", espera_s=0.3)
    r = cliente.post("/api/perfis/humor/criar-agora", headers=_h())
    assert r.status_code == 202
    assert r.json()["estado"] == "criando"
    criacao = _esperar_estado(cliente, "pronto")
    assert criacao["estado"] == "pronto"
    assert criacao["pasta_saida"] == "saida/humor/2026-11-06/1"  # relativa, nunca da máquina
    assert ":" not in criacao["pasta_saida"] and "\\" not in criacao["pasta_saida"]


def test_criar_agora_recusa_segundo_pedido_enquanto_cria(
    cliente: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _criar_humor(cliente)
    _conectar_falso(cliente, monkeypatch)
    _gerar_falso(monkeypatch, tmp_path / "p", espera_s=0.3)
    assert cliente.post("/api/perfis/humor/criar-agora", headers=_h()).status_code == 202
    assert cliente.post("/api/perfis/humor/criar-agora", headers=_h()).status_code == 409
    assert _esperar_estado(cliente, "pronto")["estado"] == "pronto"


def test_criar_agora_funciona_com_o_sistema_pausado(
    cliente: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _criar_humor(cliente)
    _conectar_falso(cliente, monkeypatch)
    _gerar_falso(monkeypatch, tmp_path / "p")
    assert cliente.post("/api/sistema/pausar", headers=_h()).json()["estado"] == "pausado"
    assert cliente.post("/api/perfis/humor/criar-agora", headers=_h()).status_code == 202
    assert _esperar_estado(cliente, "pronto")["estado"] == "pronto"


def test_pedido_com_os_campos_certos_continua_aceito(cliente: TestClient) -> None:
    assert (
        cliente.put("/api/sistema/modo", json={"modo": "manual"}, headers=_h()).status_code == 200
    )
    r = cliente.put("/api/agente/niveis", json={"niveis": {"estudo": "rapido"}}, headers=_h())
    assert r.status_code == 200
    r = cliente.post("/api/perfis", json={"slug": "humor", "nome": "Humor"}, headers=_h())
    assert r.status_code == 201
