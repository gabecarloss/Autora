"""Servidor MCP só de leitura para os bancos dos perfis (desenvolvimento).

Usado pelo Claude Code (.mcp.json) para inspecionar o banco de um perfil ao depurar
uma rodada. Nunca escreve, por construção, em três camadas:
1. o arquivo é aberto em modo somente leitura (URI ``mode=ro``) e com ``query_only``;
2. um autorizador do SQLite nega qualquer ação que não seja leitura;
3. só se aceita uma única instrução começando com SELECT ou WITH.

O banco do perfil não guarda chaves (elas ficam no keyring), então o que sai daqui não
expõe segredos.

Rodar à mão: ``uv run python -m ferramentas.mcp_sqlite_leitura``.
"""

from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any, Final

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations

from autora.config.global_config import pasta_dados
from autora.perfil.esquema import SLUG_VALIDO
from autora.perfil.perfil import listar, pasta_perfis

LIMITE_PADRAO: Final = 200
LIMITE_MAXIMO: Final = 2000
_INICIO_PERMITIDO: Final = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)
_ACOES_LEITURA: Final = frozenset(
    {
        sqlite3.SQLITE_SELECT,
        sqlite3.SQLITE_READ,
        sqlite3.SQLITE_FUNCTION,
        getattr(sqlite3, "SQLITE_RECURSIVE", 33),
    }
)


class ConsultaRecusada(ToolError):
    """Pedido fora do que este servidor aceita (escrita, perfil inexistente...).

    Herda de ToolError para que o motivo chegue ao Claude; outras exceções viram só
    "Error executing tool".
    """


def caminho_banco(dados: Path, perfil: str) -> Path:
    if not SLUG_VALIDO.match(perfil):
        raise ConsultaRecusada(f"nome de perfil inválido: {perfil!r}")
    caminho = pasta_perfis(dados) / perfil / "autora.db"
    if not caminho.is_file():
        raise ConsultaRecusada(f"perfil {perfil!r} não encontrado em {pasta_perfis(dados)}")
    return caminho


def _autorizador(acao: int, *_: object) -> int:
    return sqlite3.SQLITE_OK if acao in _ACOES_LEITURA else sqlite3.SQLITE_DENY


def abrir_leitura(caminho: Path) -> sqlite3.Connection:
    conexao = sqlite3.connect(f"{caminho.resolve().as_uri()}?mode=ro", uri=True)
    conexao.execute("PRAGMA query_only = ON")
    conexao.set_authorizer(_autorizador)
    return conexao


def _valor(v: object) -> object:
    if isinstance(v, bytes):
        return f"<{len(v)} bytes>"
    return v


def listar_perfis_em(dados: Path) -> list[str]:
    return listar(dados)


def esquema_em(dados: Path, perfil: str) -> dict[str, str]:
    with closing(abrir_leitura(caminho_banco(dados, perfil))) as conexao:
        linhas = conexao.execute(
            "SELECT name, sql FROM sqlite_master "
            "WHERE type IN ('table', 'view', 'index') AND sql IS NOT NULL ORDER BY name"
        ).fetchall()
    return {str(nome): str(sql) for nome, sql in linhas}


def consultar_em(dados: Path, perfil: str, sql: str, limite: int = LIMITE_PADRAO) -> dict[str, Any]:
    instrucao = sql.strip().rstrip(";").strip()
    if not _INICIO_PERMITIDO.match(instrucao):
        raise ConsultaRecusada("Só consultas de leitura (SELECT ou WITH) são aceitas.")
    if ";" in instrucao:
        raise ConsultaRecusada("Envie uma única instrução por vez.")
    limite = max(1, min(limite, LIMITE_MAXIMO))
    with closing(abrir_leitura(caminho_banco(dados, perfil))) as conexao:
        try:
            cursor = conexao.execute(instrucao)
        except sqlite3.DatabaseError as e:
            raise ConsultaRecusada(f"O SQLite recusou a consulta: {e}") from e
        colunas = [d[0] for d in cursor.description or ()]
        linhas = cursor.fetchmany(limite + 1)
    return {
        "colunas": colunas,
        "linhas": [[_valor(v) for v in linha] for linha in linhas[:limite]],
        "truncado": len(linhas) > limite,
    }


def criar_servidor() -> MCPServer[Any]:
    servidor: MCPServer[Any] = MCPServer(
        name="autora-sqlite",
        instructions=(
            "Leitura dos bancos SQLite dos perfis do Autora (pasta de dados do app). "
            "Use listar_perfis, depois esquema, depois consultar com SELECT."
        ),
    )
    so_leitura = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True)

    @servidor.tool(annotations=so_leitura)
    def listar_perfis() -> list[str]:
        """Lista os perfis (nomes internos) que existem na pasta de dados."""
        return listar_perfis_em(pasta_dados())

    @servidor.tool(annotations=so_leitura)
    def esquema(perfil: str) -> dict[str, str]:
        """Tabelas, visões e índices do banco do perfil, com o SQL de criação."""
        return esquema_em(pasta_dados(), perfil)

    @servidor.tool(annotations=so_leitura)
    def consultar(perfil: str, sql: str, limite: int = LIMITE_PADRAO) -> dict[str, Any]:
        """Roda uma consulta de leitura (SELECT/WITH) no banco do perfil.

        Devolve colunas, linhas (no máximo `limite`, até 2000) e se o resultado foi cortado.
        """
        return consultar_em(pasta_dados(), perfil, sql, limite)

    return servidor


def main() -> None:
    criar_servidor().run()


if __name__ == "__main__":
    main()
