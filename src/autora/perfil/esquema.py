"""Esquema do config.json do perfil.

Fonte ÚNICA para o onboarding e as configurações (seção 9.1: "onboarding e
configurações são a MESMA coisa"). As abas da seção 9.3 viram blocos aqui.
`None` significa "deixar o agente decidir" ou "ainda não definido no onboarding".

Nenhum caminho absoluto pode aparecer aqui (perfil portátil). Pastas da biblioteca
entram como apelidos; o caminho real fica em maquina.json.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from autora.util.arquivos import eh_caminho_absoluto

SLUG_VALIDO = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")
HORA_VALIDA = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Identidade(_Base):
    nome: str = Field(min_length=1, max_length=80)
    arroba: str | None = None
    personalidade_adjetivos: list[str] = Field(default_factory=list, max_length=3)
    personalidade_frase: str | None = None
    objetivos: list[str] = Field(default_factory=list)  # em ordem de prioridade
    idioma_saida: str | None = None


class Nicho(_Base):
    nome: str
    proporcao: float | None = Field(default=None, ge=0, le=1)


class GeracaoPermitida(_Base):
    por_codigo: bool = True
    imagens_ia: bool | None = None  # None = o app detecta GPU
    video_modelo: bool = False  # desligado até o usuário habilitar (seção 7.5)


class Conteudo(_Base):
    nichos: list[Nicho] = Field(default_factory=list)
    idioma_origem: str | None = None
    pastas: list[str] = Field(default_factory=list)  # apelidos (ver maquina.json)
    selecao: Literal["automatica", "manual"] = "automatica"
    quantidade_por_rodada: int | None = Field(default=None, ge=1, le=20)
    fonte_material: Literal["livre", "so_pasta", "so_geracao"] = "livre"
    geracao: GeracaoPermitida = Field(default_factory=GeracaoPermitida)

    @field_validator("pastas")
    @classmethod
    def _apelidos(cls, v: list[str]) -> list[str]:
        for apelido in v:
            if not SLUG_VALIDO.match(apelido):
                raise ValueError(f"apelido de pasta inválido: {apelido!r}")
        return v


class Producao(_Base):
    servico_voz_principal: str = "edge-tts"
    servicos_voz_reserva: list[str] = Field(default_factory=lambda: ["kokoro", "piper", "xtts"])
    vozes_desativadas: list[str] = Field(default_factory=list)
    usar_voz_do_usuario: bool = False


class Publicacao(_Base):
    aprovacao: bool = True
    horarios: Literal["agente", "fixos"] = "agente"
    horarios_fixos: list[str] = Field(default_factory=list)
    fuso: str | None = None
    horario_rodada: str | None = None  # definido no onboarding
    conta_nova: bool = True
    pausado: bool = False
    limite_rodadas_aguardando: int = Field(default=2, ge=1, le=20)  # seção 15.2

    @field_validator("horarios_fixos")
    @classmethod
    def _horas(cls, v: list[str]) -> list[str]:
        for h in v:
            if not HORA_VALIDA.match(h):
                raise ValueError(f"horário inválido: {h!r} (use HH:MM)")
        return v

    @field_validator("horario_rodada")
    @classmethod
    def _hora_rodada(cls, v: str | None) -> str | None:
        if v is not None and not HORA_VALIDA.match(v):
            raise ValueError(f"horário inválido: {v!r} (use HH:MM)")
        return v


class Metricas(_Base):
    lembrete_dia: Literal["seg", "ter", "qua", "qui", "sex", "sab", "dom"] | None = None
    lembrete_hora: str | None = None


class Aprendizado(_Base):
    proporcao_explorar: float = Field(default=0.3, ge=0, le=1)  # 70/30 (seção 8.2)


class Avancado(_Base):
    teto_custo_mensal_usd: float | None = Field(default=None, ge=0)


def _strings(obj: Any) -> list[str]:
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        return [s for v in obj.values() for s in _strings(v)]
    if isinstance(obj, (list, tuple)):
        return [s for v in obj for s in _strings(v)]
    return []


class ConfigPerfil(_Base):
    versao_esquema: int = 1
    slug: str
    criado_em: datetime
    plataforma: str = "tiktok"
    identidade: Identidade
    conteudo: Conteudo = Field(default_factory=Conteudo)
    producao: Producao = Field(default_factory=Producao)
    publicacao: Publicacao = Field(default_factory=Publicacao)
    metricas: Metricas = Field(default_factory=Metricas)
    aprendizado: Aprendizado = Field(default_factory=Aprendizado)
    avancado: Avancado = Field(default_factory=Avancado)

    @field_validator("slug")
    @classmethod
    def _slug(cls, v: str) -> str:
        if not SLUG_VALIDO.match(v):
            raise ValueError(
                f"nome interno inválido: {v!r} (use letras minúsculas, números, - e _)"
            )
        return v

    @model_validator(mode="after")
    def _sem_caminho_absoluto(self) -> ConfigPerfil:
        for s in _strings(self.model_dump(mode="json")):
            if eh_caminho_absoluto(s):
                raise ValueError(f"o perfil não pode guardar caminho absoluto: {s!r}")
        return self
