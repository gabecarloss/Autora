"""Servidor MCP só leitura: lê os bancos dos perfis e nunca escreve."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from autora.perfil.perfil import Perfil
from ferramentas.mcp_sqlite_leitura import (
    ConsultaRecusada,
    abrir_leitura,
    caminho_banco,
    consultar_em,
    criar_servidor,
    esquema_em,
    listar_perfis_em,
)


@pytest.fixture
def perfil(dados: Path) -> Perfil:
    return Perfil.criar(dados, "humor", "Humor")


def test_lista_os_perfis(dados: Path, perfil: Perfil) -> None:
    assert listar_perfis_em(dados) == ["humor"]


def test_esquema_traz_as_tabelas(dados: Path, perfil: Perfil) -> None:
    tabelas = esquema_em(dados, "humor")
    assert tabelas
    assert all(sql.upper().startswith("CREATE") for sql in tabelas.values())


def test_consulta_de_leitura_funciona_e_respeita_limite(dados: Path, perfil: Perfil) -> None:
    r = consultar_em(
        dados, "humor", "WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM n "
        "WHERE x < 50) SELECT x FROM n;", limite=10
    )  # fmt: skip
    assert r["colunas"] == ["x"]
    assert len(r["linhas"]) == 10
    assert r["truncado"] is True


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM sqlite_master",
        "DROP TABLE x",
        "INSERT INTO x VALUES (1)",
        "UPDATE x SET a = 1",
        "PRAGMA journal_mode = DELETE",
        "ATTACH DATABASE 'outro.db' AS o",
        "SELECT 1; DROP TABLE x",
        "VACUUM",
    ],
)
def test_recusa_qualquer_escrita(dados: Path, perfil: Perfil, sql: str) -> None:
    with pytest.raises(ConsultaRecusada):
        consultar_em(dados, "humor", sql)


def test_with_que_escreve_e_negado_pelo_autorizador(dados: Path, perfil: Perfil) -> None:
    sql = "WITH a AS (SELECT 1) DELETE FROM sqlite_master"
    with pytest.raises(ConsultaRecusada):
        consultar_em(dados, "humor", sql)


def test_conexao_e_somente_leitura_mesmo_sem_validacao(dados: Path, perfil: Perfil) -> None:
    conexao = abrir_leitura(caminho_banco(dados, "humor"))
    try:
        with pytest.raises(sqlite3.DatabaseError):
            conexao.execute("CREATE TABLE invasora (x)")
    finally:
        conexao.close()


@pytest.mark.parametrize("nome", ["../fora", "nao-existe", "C:/Windows"])
def test_recusa_perfil_invalido_ou_inexistente(dados: Path, nome: str) -> None:
    with pytest.raises(ConsultaRecusada):
        consultar_em(dados, nome, "SELECT 1")


def test_servidor_registra_as_tres_ferramentas() -> None:
    servidor = criar_servidor()
    nomes = {f.name for f in servidor._tool_manager.list_tools()}
    assert nomes == {"listar_perfis", "esquema", "consultar"}
