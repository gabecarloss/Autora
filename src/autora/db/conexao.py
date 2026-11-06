"""Banco SQLite do perfil: abertura segura e migrações numeradas.

Migrações ficam em autora/db/migracoes/NNNN_nome.sql e são aplicadas em ordem.
A versão aplicada fica em PRAGMA user_version. Só consultas parametrizadas.
"""

from __future__ import annotations

import re
import sqlite3
from importlib import resources
from pathlib import Path

_NOME_MIGRACAO = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")


def abrir(caminho: Path) -> sqlite3.Connection:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(caminho, timeout=30, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    con.execute("PRAGMA synchronous = NORMAL")
    con.execute("PRAGMA busy_timeout = 30000")
    return con


def migracoes_disponiveis() -> list[tuple[int, str, str]]:
    """Lista (número, nome, sql) das migrações empacotadas, em ordem."""
    pasta = resources.files("autora.db") / "migracoes"
    itens: list[tuple[int, str, str]] = []
    for arq in pasta.iterdir():
        m = _NOME_MIGRACAO.match(arq.name)
        if m:
            itens.append((int(m.group(1)), arq.name, arq.read_text(encoding="utf-8")))
    itens.sort()
    numeros = [n for n, _, _ in itens]
    if numeros != list(range(1, len(numeros) + 1)):
        raise RuntimeError(f"migrações com numeração quebrada: {numeros}")
    return itens


def versao(con: sqlite3.Connection) -> int:
    return int(con.execute("PRAGMA user_version").fetchone()[0])


def migrar(con: sqlite3.Connection) -> list[str]:
    """Aplica as migrações pendentes, cada uma numa transação. Devolve as aplicadas."""
    atual = versao(con)
    aplicadas: list[str] = []
    for numero, nome, sql in migracoes_disponiveis():
        if numero <= atual:
            continue
        con.execute("BEGIN")
        try:
            # executescript faria COMMIT implícito; executamos comando a comando.
            for comando in _dividir_sql(sql):
                con.execute(comando)
            con.execute(f"PRAGMA user_version = {numero:d}")
            con.execute("COMMIT")
        except BaseException:
            con.execute("ROLLBACK")
            raise
        aplicadas.append(nome)
    return aplicadas


def _dividir_sql(sql: str) -> list[str]:
    """Divide um script em comandos (as migrações não usam ';' dentro de strings)."""
    sem_comentarios = "\n".join(
        linha for linha in sql.splitlines() if not linha.strip().startswith("--")
    )
    return [c.strip() for c in sem_comentarios.split(";") if c.strip()]


def abrir_migrado(caminho: Path) -> sqlite3.Connection:
    con = abrir(caminho)
    migrar(con)
    return con
