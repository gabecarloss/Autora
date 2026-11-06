"""Servidor MCP de verdade: sobe por stdio, como o Claude Code faz, e responde."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from autora.perfil.perfil import Perfil

RAIZ = Path(__file__).resolve().parents[2]
SERVIDOR = RAIZ / "ferramentas" / "mcp_sqlite_leitura.py"


def _texto(resultado: Any) -> str:
    return "".join(getattr(c, "text", "") for c in resultado.content)


async def _sessao(dados: Path) -> dict[str, Any]:
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVIDOR)],
        env={**os.environ, "AUTORA_DADOS": str(dados)},
    )
    saida: dict[str, Any] = {}
    async with (
        stdio_client(params) as (leitura, escrita),
        ClientSession(leitura, escrita) as sessao,
    ):
        await sessao.initialize()
        saida["ferramentas"] = sorted(t.name for t in (await sessao.list_tools()).tools)
        saida["perfis"] = await sessao.call_tool("listar_perfis", {})
        saida["consulta"] = await sessao.call_tool(
            "consultar", {"perfil": "humor", "sql": "SELECT 7 AS n"}
        )
        saida["escrita"] = await sessao.call_tool(
            "consultar", {"perfil": "humor", "sql": "DELETE FROM rodada"}
        )
    return saida


def test_servidor_responde_por_stdio_e_recusa_escrita(dados: Path) -> None:
    Perfil.criar(dados, "humor", "Humor")
    r = asyncio.run(asyncio.wait_for(_sessao(dados), timeout=60))

    assert r["ferramentas"] == ["consultar", "esquema", "listar_perfis"]
    assert "humor" in _texto(r["perfis"])
    assert not r["consulta"].is_error
    assert json.loads(_texto(r["consulta"]))["linhas"] == [[7]]
    assert r["escrita"].is_error
    assert "leitura" in _texto(r["escrita"])  # o motivo chega ao Claude
