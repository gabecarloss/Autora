"""O que o agente devolve na etapa "conceito" (ideia do post), validado por pydantic.

Regras da skill chamada-ao-agente: as cinco perguntas da seção 3.1 num campo próprio
(`raciocinio`), separado da decisão; toda escolha com motivo (14.2); "não sei" é
resposta válida; nada de texto livre "consertado" pelo código.
"""

from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Formato = Literal[
    "compilacao",
    "historia_com_fundo",
    "texto_narrativo",
    "reacao_comentario",
    "remontagem",
    "adaptacao",
    "outro",
]
FORMATOS: Final[tuple[str, ...]] = (
    "compilacao",
    "historia_com_fundo",
    "texto_narrativo",
    "reacao_comentario",
    "remontagem",
    "adaptacao",
    "outro",
)

# PROVISÓRIO (até o revisor e as verificações do passo 8): tipos de elemento autoral
# que o código consegue conferir no roteiro (ver rodada/transformacao.py).
TipoElemento = Literal[
    "narrativa_propria",
    "comentario",
    "remontagem",
    "ritmo_proprio",
    "compilacao_com_criterio",
    "zoom_destaque",
]
COMO_VERIFICAR_ELEMENTO: Final[dict[str, str]] = {
    "narrativa_propria": "pelo menos 2 textos na tela com papel 'narrativa'",
    "comentario": "pelo menos 1 texto na tela com papel 'comentario'",
    "remontagem": "2 ou mais trechos e (ordem diferente da cronológica, ou 2 ou mais "
    "clipes, ou descarte de pelo menos 30% do material entre o primeiro e o último corte)",
    "ritmo_proprio": "3 ou mais trechos com duração média de até 3 s, ou algum trecho "
    "com velocidade diferente de 1",
    "compilacao_com_criterio": "trechos de 2 ou mais clipes e pelo menos 1 texto com "
    "papel 'destaque' ou 'narrativa'",
    "zoom_destaque": "pelo menos 1 trecho com zoom",
}


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Raciocinio(_Base):
    """As cinco perguntas de "Como você raciocina antes de agir" (seção 3.1)."""

    sei_com_certeza: str = Field(min_length=10)
    estou_supondo: str = Field(min_length=10)
    o_melhor_criador_faria: str = Field(min_length=10)
    pode_dar_errado_e_como_percebo: str = Field(min_length=10)
    motivo_da_escolha: str = Field(min_length=10)


class Escolha(_Base):
    valor: str = Field(min_length=1)
    motivo: str = Field(min_length=10)


class ClipeEscolhido(_Base):
    clipe_id: int
    motivo: str = Field(min_length=10)


class ElementoAutoral(_Base):
    tipo: TipoElemento
    descricao: str = Field(min_length=10)  # o que será feito, específico
    como_verificar: str = Field(min_length=10)  # o que o roteiro precisa ter para provar


class SomSugerido(_Base):
    """Som só sugerido: a localização e a análise do som são do passo 6 (seção 7.2)."""

    nome: str | None = None  # só se localizado com fonte; senão None
    fonte: str | None = None  # onde achou, com data
    funcao_no_video: str = Field(min_length=5)
    volume: Literal["baixo", "medio", "alto"] = "medio"
    cobertura: Literal["inteiro", "trecho"] = "inteiro"
    motivo: str = Field(min_length=10)
    verificado: Literal[False] = False  # PROVISÓRIO: verificação de som é passo 6

    @model_validator(mode="after")
    def _nome_exige_fonte(self) -> SomSugerido:
        if self.nome and not self.fonte:
            raise ValueError("som com nome precisa de fonte; sem fonte, deixe nome vazio")
        return self


class Conceito(_Base):
    raciocinio: Raciocinio
    clipes_escolhidos: list[ClipeEscolhido] = Field(min_length=1)
    formato: Escolha  # valor em FORMATOS
    descricao_formato: str | None = None  # obrigatório se formato "outro"
    fonte_material: Literal["pasta"] = "pasta"  # PROVISÓRIO: só pasta nesta versão
    tema: str = Field(min_length=3)
    conceito: str = Field(min_length=20)  # a ideia em 2-4 frases
    gancho: Escolha
    alternativas_gancho: list[str] = Field(min_length=2, max_length=4)
    descricao_post: str = Field(min_length=5)
    hashtags: list[str] = Field(min_length=3, max_length=5)
    horario_sugerido: Escolha  # "HH:MM" ou "não sei ainda", com motivo
    capa: Escolha  # texto da capa + motivo (o segundo vem no roteiro)
    som: SomSugerido | None = None
    elementos_autorais: list[ElementoAutoral] = Field(min_length=2)
    duracao_alvo_s: float = Field(ge=3, le=180)
    nao_sei: list[str] = Field(default_factory=list)  # lacunas assumidas, nunca inventadas
    confianca: Literal["baixa", "media", "alta"]

    @model_validator(mode="after")
    def _coerente(self) -> Conceito:
        if self.formato.valor not in FORMATOS:
            raise ValueError(f"formato precisa ser um de {FORMATOS}, veio {self.formato.valor!r}")
        if self.formato.valor == "outro" and not self.descricao_formato:
            raise ValueError("formato 'outro' exige descricao_formato")
        tipos = [e.tipo for e in self.elementos_autorais]
        if len(set(tipos)) != len(tipos):
            raise ValueError("elementos autorais precisam ser de tipos distintos")
        if self.gancho.valor.strip().lower() in {
            a.strip().lower() for a in self.alternativas_gancho
        }:
            raise ValueError(
                "as alternativas de gancho precisam ser diferentes do gancho escolhido"
            )
        for h in self.hashtags:
            if not h.startswith("#") or " " in h or len(h) < 2:
                raise ValueError(f"hashtag inválida: {h!r}")
        ids = [c.clipe_id for c in self.clipes_escolhidos]
        if len(set(ids)) != len(ids):
            raise ValueError("clipe escolhido mais de uma vez")
        return self

    def ids_escolhidos(self) -> set[int]:
        return {c.clipe_id for c in self.clipes_escolhidos}
