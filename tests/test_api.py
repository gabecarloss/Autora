"""Servidor local: sessão, host, segredos nunca devolvidos."""

from __future__ import annotations

from pathlib import Path

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
    assert lista == [{"slug": "humor", "nome": "Humor", "pausado": False, "estado": "ok"}]


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


def test_pedido_com_os_campos_certos_continua_aceito(cliente: TestClient) -> None:
    assert (
        cliente.put("/api/sistema/modo", json={"modo": "manual"}, headers=_h()).status_code == 200
    )
    r = cliente.put("/api/agente/niveis", json={"niveis": {"estudo": "rapido"}}, headers=_h())
    assert r.status_code == 200
    r = cliente.post("/api/perfis", json={"slug": "humor", "nome": "Humor"}, headers=_h())
    assert r.status_code == 201
