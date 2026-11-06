"""Caminhos absolutos desta máquina (maquina.json).

Perfis são portáteis: guardam pastas da biblioteca como APELIDO + caminho relativo
(ex.: "humor1:sub/video.mp4"). Só este arquivo, que não viaja com o perfil, sabe
onde cada apelido está no disco. Ao importar um perfil em outro PC, o app pede para
reapontar os apelidos.
"""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from autora.config.global_config import pasta_dados
from autora.util.arquivos import gravar_atomico, resolver_dentro

APELIDO_VALIDO = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")


class ApelidoDesconhecido(KeyError):
    pass


class ConfigMaquina(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pastas: dict[str, str] = Field(default_factory=dict)
    """apelido → caminho absoluto da pasta da biblioteca."""
    saida_por_perfil: dict[str, str] = Field(default_factory=dict)
    """slug → pasta de saída personalizada (opcional; padrão: <dados>/saida/<slug>)."""


def _caminho(dados: Path | None) -> Path:
    return (dados or pasta_dados()) / "maquina.json"


def carregar(dados: Path | None = None) -> ConfigMaquina:
    c = _caminho(dados)
    if not c.exists():
        return ConfigMaquina()
    return ConfigMaquina.model_validate_json(c.read_text(encoding="utf-8"))


def salvar(cfg: ConfigMaquina, dados: Path | None = None) -> None:
    gravar_atomico(_caminho(dados), cfg.model_dump_json(indent=2))


def definir_apelido(apelido: str, pasta: Path, dados: Path | None = None) -> None:
    if not APELIDO_VALIDO.match(apelido):
        raise ValueError(f"apelido inválido: {apelido!r} (use letras minúsculas, números, - e _)")
    cfg = carregar(dados)
    cfg.pastas[apelido] = str(pasta.resolve())
    salvar(cfg, dados)


def resolver(referencia: str, dados: Path | None = None) -> Path:
    """Converte "apelido:caminho/relativo" no caminho absoluto desta máquina."""
    apelido, sep, relativo = referencia.partition(":")
    if not sep:
        raise ValueError(f"referência sem apelido: {referencia!r}")
    cfg = carregar(dados)
    if apelido not in cfg.pastas:
        raise ApelidoDesconhecido(apelido)
    return resolver_dentro(Path(cfg.pastas[apelido]), relativo)


def pasta_saida(slug: str, dados: Path | None = None) -> Path:
    raiz = dados or pasta_dados()
    cfg = carregar(dados)
    return (
        Path(cfg.saida_por_perfil[slug]) if slug in cfg.saida_por_perfil else raiz / "saida" / slug
    )
