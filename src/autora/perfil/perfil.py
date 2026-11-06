"""Pasta portátil do perfil (seção 3).

perfis/<slug>/
  config.json        esquema em autora.perfil.esquema
  autora.db          banco SQLite (migrado ao abrir)
  memoria/*.md       mandato, preferências, aprendizados... (+ .historico/)
  material/          material gerado pelo agente
  logs/AAAA-MM-DD.jsonl
"""

from __future__ import annotations

import os
import sqlite3
import sys
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import IO, Final

from pydantic import ValidationError

from autora.db.conexao import abrir_migrado
from autora.perfil.esquema import SLUG_VALIDO, ConfigPerfil, Identidade
from autora.perfil.memoria import Memoria
from autora.registro.log import Registro
from autora.util.arquivos import gravar_atomico
from autora.util.tempo import agora

NOME_TRAVA: Final = ".trava"


class PerfilJaExiste(FileExistsError):
    pass


class PerfilNaoEncontrado(FileNotFoundError):
    pass


class PerfilOcupado(RuntimeError):
    """Outra rodada deste perfil já está em andamento (app, CLI ou agendador)."""


class PerfilInvalido(ValueError):
    pass


def pasta_perfis(dados: Path) -> Path:
    return dados / "perfis"


def listar(dados: Path) -> list[str]:
    raiz = pasta_perfis(dados)
    if not raiz.exists():
        return []
    return sorted(p.name for p in raiz.iterdir() if (p / "config.json").exists())


class Perfil:
    def __init__(self, raiz: Path, config: ConfigPerfil) -> None:
        self.raiz = raiz
        self.config = config
        self.memoria = Memoria(raiz / "memoria")
        self.registro = Registro(raiz / "logs", config.slug)

    # --- caminhos -----------------------------------------------------------
    @property
    def slug(self) -> str:
        return self.config.slug

    @property
    def caminho_db(self) -> Path:
        return self.raiz / "autora.db"

    @property
    def pasta_material(self) -> Path:
        return self.raiz / "material"

    @property
    def caminho_config(self) -> Path:
        return self.raiz / "config.json"

    # --- ciclo de vida ------------------------------------------------------
    @classmethod
    def criar(cls, dados: Path, slug: str, nome: str) -> Perfil:
        if not SLUG_VALIDO.match(slug):
            raise PerfilInvalido(
                f"nome interno inválido: {slug!r} (use letras minúsculas, números, - e _)"
            )
        raiz = pasta_perfis(dados) / slug
        if (raiz / "config.json").exists():
            raise PerfilJaExiste(slug)
        config = ConfigPerfil(slug=slug, criado_em=agora(), identidade=Identidade(nome=nome))
        raiz.mkdir(parents=True, exist_ok=True)
        (raiz / "material").mkdir(exist_ok=True)
        perfil = cls(raiz, config)
        perfil.memoria.criar_iniciais()
        with perfil.conectar():
            pass  # cria e migra o banco
        perfil.salvar_config()
        perfil.registro.registrar("sistema", f"Perfil “{nome}” criado.", detalhe={"slug": slug})
        return perfil

    @classmethod
    def abrir(cls, dados: Path, slug: str) -> Perfil:
        raiz = pasta_perfis(dados) / slug
        caminho = raiz / "config.json"
        if not caminho.exists():
            raise PerfilNaoEncontrado(slug)
        try:
            config = ConfigPerfil.model_validate_json(caminho.read_text(encoding="utf-8"))
        except ValidationError as e:
            raise PerfilInvalido(
                f"A configuração do perfil {slug!r} está com problema e não pôde ser lida."
            ) from e
        if config.slug != slug:
            raise PerfilInvalido(f"pasta {slug!r} contém o perfil {config.slug!r}")
        return cls(raiz, config)

    def salvar_config(self) -> None:
        gravar_atomico(self.caminho_config, self.config.model_dump_json(indent=2))

    @contextmanager
    def conectar(self) -> Iterator[sqlite3.Connection]:
        con = abrir_migrado(self.caminho_db)
        try:
            yield con
        finally:
            con.close()

    # --- trava --------------------------------------------------------------
    @contextmanager
    def trava(self) -> Iterator[None]:
        """Impede duas rodadas do mesmo perfil ao mesmo tempo, entre processos.

        Usa trava de arquivo do sistema operacional: se o processo morrer, a trava
        é liberada sozinha (não fica trava "fantasma").
        """
        caminho = self.raiz / NOME_TRAVA
        f = caminho.open("a+b")
        try:
            if not _travar(f):
                raise PerfilOcupado(self.slug)
            try:
                f.seek(0)
                f.truncate()
                f.write(str(os.getpid()).encode())
                f.flush()
                yield
            finally:
                _destravar(f)
        finally:
            f.close()


if sys.platform == "win32":
    import msvcrt

    def _travar(f: IO[bytes]) -> bool:
        f.seek(0)
        try:
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            return False
        return True

    def _destravar(f: IO[bytes]) -> None:
        f.seek(0)
        with suppress(OSError):
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    def _travar(f: IO[bytes]) -> bool:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return False
        return True

    def _destravar(f: IO[bytes]) -> None:
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
