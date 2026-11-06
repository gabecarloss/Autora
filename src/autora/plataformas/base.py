"""Interface genérica de plataforma (seção 1: código não assume TikTok em todo lugar).

Tudo que é específico de uma rede (formato do post.md, como o som é indicado,
métricas) mora num adaptador em autora/plataformas/<rede>/. O resto do sistema só
conhece esta interface. O adaptador do TikTok entra no passo 2.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class EspecificacaoVideo:
    largura: int
    altura: int
    fps: int
    codec: str
    musica_embutida: bool


@dataclass
class PacotePost:
    """Dados genéricos de um post pronto, antes de virar o post.md da plataforma."""

    gancho: str
    alternativas_gancho: list[str]
    descricao: str
    hashtags: list[str]
    horario_sugerido: str
    motivo_horario: str
    capa_texto: str
    capa_segundo: float
    formato: str
    fonte_material: str
    voz: str | None
    versao_estilo: int | None
    motivos: dict[str, str] = field(default_factory=dict)
    som: dict[str, object] | None = None
    # Campos do passo 2 (genéricos; o adaptador decide como mostrar).
    tema: str = ""
    conceito: str = ""
    duracao_s: float | None = None
    legendas: str = "ok"  # "ok" | "sem_fala" | "indisponiveis" | "desligadas"
    elementos_autorais: list[dict[str, str]] = field(default_factory=list)
    referencia: str | None = None  # se adaptação (seção 6)
    nao_sei: list[str] = field(default_factory=list)
    confianca: str | None = None
    avisos: list[str] = field(default_factory=list)
    nome_perfil: str = ""
    criado_em: str = ""


class Plataforma(Protocol):
    nome: str
    nome_amigavel: str
    video: EspecificacaoVideo

    def gerar_post_md(self, pacote: PacotePost) -> str: ...


_REGISTRADAS: dict[str, Plataforma] = {}


def registrar(plataforma: Plataforma) -> None:
    _REGISTRADAS[plataforma.nome] = plataforma


def obter(nome: str) -> Plataforma:
    try:
        return _REGISTRADAS[nome]
    except KeyError:
        raise KeyError(f"plataforma não disponível: {nome!r}") from None
