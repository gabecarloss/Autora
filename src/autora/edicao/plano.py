"""Roteiro de edição: o JSON que o agente escreve e o motor ffmpeg executa (seção 7.1).

Unidades: segundos (3 casas), pixels numa tela de 1080x1920, cores "#RRGGBB", `y` em
fração da altura. O agente descreve o vídeo; nunca escreve comandos ffmpeg.

Linha do tempo FINAL: cada trecho dura (fim_s - inicio_s) / velocidade e começa onde o
anterior terminou. Textos, capa e legendas usam só esse tempo final.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from autora.plataformas.base import EspecificacaoVideo

# A resolução e o fps reais vêm de `Plataforma.video`; isto é só o padrão dos testes.
FORMATO_PADRAO: Final = EspecificacaoVideo(1080, 1920, 30, "h264", False)

# PROVISÓRIO: catálogo de fontes do Windows (ver edicao/fontes.py); limites de duração,
# tamanho de fonte e zona segura do TikTok a confirmar no estudo inicial (passo 4).
DURACAO_MINIMA_S: Final = 3.0
DURACAO_MAXIMA_S: Final = 180.0
Fonte = Literal["impact", "arial_black", "arial_bold", "bahnschrift", "segoe_bold"]
Posicao = Literal["topo", "centro", "base"]
PapelTexto = Literal["gancho", "narrativa", "comentario", "destaque"]

_COR_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")  # campo desconhecido do agente = roteiro inválido


def _cor(v: str) -> str:
    if not _COR_HEX.match(v):
        raise ValueError(f"cor precisa ser #RRGGBB, veio {v!r}")
    return v.upper()


class Enquadramento(_Base):
    """Como um clipe que não é 9:16 vira 9:16 (seção 7.1)."""

    modo: Literal["fundo_desfocado", "recorte"] = "recorte"
    foco_x: float = Field(default=0.5, ge=0, le=1)  # ponto de interesse (só no recorte)
    foco_y: float = Field(default=0.5, ge=0, le=1)


class Zoom(_Base):
    """Tempos relativos ao início do trecho, já na velocidade final."""

    inicio_s: float = Field(ge=0)
    fim_s: float = Field(gt=0)
    fator: float = Field(default=1.15, gt=1.0, le=1.5)

    @model_validator(mode="after")
    def _ordem(self) -> Zoom:
        if self.fim_s < self.inicio_s + 0.1:
            raise ValueError("zoom precisa durar pelo menos 0,1 s")
        return self


class Trecho(_Base):
    clipe_id: int
    inicio_s: float = Field(ge=0)  # no clipe de origem
    fim_s: float = Field(gt=0)
    velocidade: float = Field(default=1.0, ge=0.5, le=2.0)
    enquadramento: Enquadramento = Field(default_factory=Enquadramento)
    zoom: Zoom | None = None

    @property
    def duracao_fonte_s(self) -> float:
        return round(self.fim_s - self.inicio_s, 3)

    @property
    def duracao_final_s(self) -> float:
        return round(self.duracao_fonte_s / self.velocidade, 3)

    @model_validator(mode="after")
    def _coerente(self) -> Trecho:
        if self.fim_s - self.inicio_s < 0.3:
            raise ValueError("trecho menor que 0,3 s")
        if self.zoom is not None and self.zoom.fim_s > self.duracao_final_s + 0.01:
            raise ValueError("zoom termina depois do fim do trecho")
        return self


class EstiloTexto(_Base):
    fonte: Fonte = "impact"
    tamanho: int = Field(default=72, ge=36, le=160)
    cor: str = "#FFFFFF"
    cor_contorno: str = "#000000"
    contorno: int = Field(default=4, ge=0, le=10)
    caixa: bool = False  # fundo opaco atrás do texto
    animacao: Literal["nenhuma", "fade", "pop"] = "fade"

    @field_validator("cor", "cor_contorno")
    @classmethod
    def _hex(cls, v: str) -> str:
        return _cor(v)


class TextoNaTela(_Base):
    texto: str = Field(min_length=1, max_length=120)
    papel: PapelTexto
    inicio_s: float = Field(ge=0)  # linha do tempo FINAL
    fim_s: float = Field(gt=0)
    posicao: Posicao = "centro"
    y: float | None = Field(default=None, ge=0.08, le=0.78)  # fração da altura (None: `posicao`)
    estilo: EstiloTexto = Field(default_factory=EstiloTexto)

    @model_validator(mode="after")
    def _ordem(self) -> TextoNaTela:
        if self.fim_s < self.inicio_s + 0.2:
            raise ValueError("texto precisa ficar pelo menos 0,2 s na tela")
        return self


class Legendas(_Base):
    ativas: bool = True
    modo: Literal["palavra", "grupo"] = "palavra"
    palavras_por_grupo: int = Field(default=3, ge=2, le=4)
    posicao: Posicao = "base"
    estilo: EstiloTexto = Field(default_factory=lambda: EstiloTexto(tamanho=64))
    cor_destaque: str = "#FFD400"  # palavra atual no modo "grupo"

    @field_validator("cor_destaque")
    @classmethod
    def _hex(cls, v: str) -> str:
        return _cor(v)


class Capa(_Base):
    segundo: float = Field(ge=0)  # na linha do tempo final
    texto: str = Field(min_length=1, max_length=60)
    estilo: EstiloTexto = Field(default_factory=lambda: EstiloTexto(tamanho=110))


class Audio(_Base):
    manter_original: bool = True
    volume: float = Field(default=1.0, ge=0, le=2.0)


class Motivos(_Base):
    """Todo post tem motivo registrado (seção 14.2)."""

    ritmo: str = Field(min_length=10)
    enquadramento: str = Field(min_length=10)
    textos: str = Field(min_length=10)
    legendas: str = Field(min_length=10)


class PlanoEdicao(_Base):
    versao_esquema: Literal[1] = 1
    versao_estilo: int = Field(default=1, ge=1)  # seção 7.1
    trechos: list[Trecho] = Field(min_length=1, max_length=30)
    textos: list[TextoNaTela] = Field(default_factory=list, max_length=20)
    legendas: Legendas = Field(default_factory=Legendas)
    capa: Capa
    audio: Audio = Field(default_factory=Audio)
    motivos: Motivos

    @property
    def duracao_s(self) -> float:
        return round(sum(t.duracao_final_s for t in self.trechos), 3)

    def inicios_dos_trechos(self) -> list[float]:
        """Segundo (na linha final) em que cada trecho começa."""
        inicios: list[float] = []
        t = 0.0
        for trecho in self.trechos:
            inicios.append(round(t, 3))
            t += trecho.duracao_final_s
        return inicios

    @model_validator(mode="after")
    def _linha_do_tempo(self) -> PlanoEdicao:
        d = self.duracao_s
        if not DURACAO_MINIMA_S <= d <= DURACAO_MAXIMA_S:
            limites = f"{DURACAO_MINIMA_S:.0f}–{DURACAO_MAXIMA_S:.0f} s"
            raise ValueError(f"vídeo final com {d:.1f} s; o limite é {limites}")
        for texto in self.textos:
            if texto.fim_s > d + 0.01:
                raise ValueError(
                    f"texto {texto.texto!r} termina depois do fim do vídeo ({d:.1f} s)"
                )
        if self.capa.segundo >= d:
            raise ValueError(f"capa no segundo {self.capa.segundo} está fora do vídeo ({d:.1f} s)")
        return self


def verificar_contra_clipes(
    plano: PlanoEdicao, duracoes: Mapping[int, float], permitidos: set[int] | None = None
) -> list[str]:
    """Checagens que dependem dos clipes reais. Devolve problemas (vazio = ok)."""
    problemas: list[str] = []
    for i, t in enumerate(plano.trechos, start=1):
        if t.clipe_id not in duracoes:
            problemas.append(f"trecho {i}: clipe {t.clipe_id} não existe")
            continue
        if permitidos is not None and t.clipe_id not in permitidos:
            problemas.append(f"trecho {i}: clipe {t.clipe_id} não foi escolhido na ideia do post")
        if t.fim_s > duracoes[t.clipe_id] + 0.05:
            problemas.append(
                f"trecho {i}: fim em {t.fim_s} s passa da duração do clipe "
                f"{t.clipe_id} ({duracoes[t.clipe_id]:.2f} s)"
            )
    return problemas
