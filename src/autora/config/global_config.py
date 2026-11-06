"""Configuração global do app (global.json). Nunca contém segredos.

A pasta de dados fica fora do repositório. Padrão: %USERPROFILE%\\Autora.
Pode ser trocada pela variável de ambiente AUTORA_DADOS.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from autora.util.arquivos import gravar_atomico

ModoGeracao = Literal["automatico", "manual"]
TipoConexao = Literal["nenhuma", "assinatura", "chave"]
Etapa = Literal["estudo", "conceito", "plano", "revisor", "verificacoes", "indexacao", "teste"]
Nivel = Literal["automatico", "rapido", "equilibrado", "maximo"]

ETAPAS: tuple[Etapa, ...] = (
    "estudo",
    "conceito",
    "plano",
    "revisor",
    "verificacoes",
    "indexacao",
    "teste",
)


def pasta_dados() -> Path:
    """Raiz dos dados do app (perfis, backups, saída, logs globais)."""
    env = os.environ.get("AUTORA_DADOS")
    raiz = Path(env) if env else Path.home() / "Autora"
    raiz.mkdir(parents=True, exist_ok=True)
    return raiz


def _niveis_padrao() -> dict[Etapa, Nivel]:
    automatico: Nivel = "automatico"
    return dict.fromkeys(ETAPAS, automatico)


class ConexaoAgente(BaseModel):
    """Como o agente está conectado. O token/chave em si fica só no keyring."""

    model_config = ConfigDict(extra="forbid")

    tipo: TipoConexao = "nenhuma"
    conectado_em: datetime | None = None
    ultima_verificacao: datetime | None = None
    ultimo_resultado: Literal["ok", "falhou"] | None = None
    ultimo_erro: str | None = None
    niveis: dict[Etapa, Nivel] = Field(default_factory=lambda: _niveis_padrao())


class ConfigGlobal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    versao_esquema: int = 1
    modo: ModoGeracao = "automatico"
    pausado: bool = False
    retencao_logs_dias: int = Field(default=90, ge=7, le=3650)
    # Padrão provisório (não definido no briefing): 30 dias. Confirmar com o usuário.
    retencao_backups_dias: int = Field(default=30, ge=1, le=3650)
    agente: ConexaoAgente = Field(default_factory=ConexaoAgente)

    @property
    def estado_sistema(self) -> Literal["ligado", "pausado", "manual"]:
        """Indicador da barra lateral (seção 15.1). Pausado tem prioridade sobre o modo."""
        if self.pausado:
            return "pausado"
        return "manual" if self.modo == "manual" else "ligado"


class ConfigInvalida(Exception):
    """Arquivo de configuração existe mas não passou na validação."""


def caminho_global(dados: Path | None = None) -> Path:
    return (dados or pasta_dados()) / "global.json"


def carregar(dados: Path | None = None) -> ConfigGlobal:
    caminho = caminho_global(dados)
    if not caminho.exists():
        return ConfigGlobal()
    try:
        return ConfigGlobal.model_validate_json(caminho.read_text(encoding="utf-8"))
    except ValidationError as e:
        raise ConfigInvalida(
            f"A configuração global em {caminho} está com problema e não pôde ser lida."
        ) from e


def salvar(cfg: ConfigGlobal, dados: Path | None = None) -> None:
    gravar_atomico(caminho_global(dados), cfg.model_dump_json(indent=2))
