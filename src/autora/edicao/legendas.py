"""Legendas e textos na tela → um único arquivo ASS (libass), funções puras.

Legendas palavra por palavra (seção 7.1): um evento por palavra. No modo "grupo", um
evento por 2–4 palavras com karaokê (\\k): a palavra atual fica na cor de destaque.
Textos na tela ficam na camada 1 (por cima das legendas).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from autora.edicao.fontes import FONTES
from autora.edicao.plano import (
    EstiloTexto,
    Legendas,
    PlanoEdicao,
    Posicao,
    TextoNaTela,
)
from autora.plataformas.base import EspecificacaoVideo
from autora.servicos.transcricao import Palavra

# PROVISÓRIO: zona segura do TikTok (interface cobre ~22% inferior e a borda direita).
# Margens em fração da tela, convertidas para a resolução da plataforma.
_ALINHAMENTO: Final[dict[str, tuple[int, float]]] = {
    "topo": (8, 200 / 1920),
    "centro": (5, 0.0),
    "base": (2, 430 / 1920),
}
_MARGEM_LATERAL: Final = 60 / 1080
_FADE: Final = r"\fad(150,150)"
_POP: Final = r"\fscx80\fscy80\t(0,120,\fscx105\fscy105)\t(120,200,\fscx100\fscy100)"
DURACAO_MINIMA_PALAVRA_S: Final = 0.15
FOLGA_PALAVRA_S: Final = 0.08


@dataclass(frozen=True)
class EstiloAss:
    nome: str
    fonte: str
    negrito: bool
    tamanho: int
    cor_primaria: str
    cor_secundaria: str
    cor_contorno: str
    cor_fundo: str
    contorno: int
    caixa: bool
    alinhamento: int
    margem_v: int
    margem_lateral: int

    def linha(self) -> str:
        return (
            f"Style: {self.nome},{self.fonte},{self.tamanho},{self.cor_primaria},"
            f"{self.cor_secundaria},{self.cor_contorno},{self.cor_fundo},"
            f"{-1 if self.negrito else 0},0,0,0,100,100,0,0,{3 if self.caixa else 1},"
            f"{self.contorno},0,{self.alinhamento},{self.margem_lateral},{self.margem_lateral},"
            f"{self.margem_v},1"
        )


@dataclass(frozen=True)
class EventoAss:
    camada: int
    inicio_s: float
    fim_s: float
    estilo: str
    texto: str

    def linha(self) -> str:
        return (
            f"Dialogue: {self.camada},{tempo_ass(self.inicio_s)},{tempo_ass(self.fim_s)},"
            f"{self.estilo},,0,0,0,,{self.texto}"
        )


def tempo_ass(segundos: float) -> str:
    cs = round(max(segundos, 0) * 100)
    h, resto = divmod(cs, 360000)
    m, resto = divmod(resto, 6000)
    s, c = divmod(resto, 100)
    return f"{h}:{m:02d}:{s:02d}.{c:02d}"


def cor_ass(hex_rrggbb: str, alfa: int = 0) -> str:
    """#RRGGBB → &HAABBGGRR (ASS guarda azul, verde, vermelho)."""
    rr, gg, bb = hex_rrggbb[1:3], hex_rrggbb[3:5], hex_rrggbb[5:7]
    return f"&H{alfa:02X}{bb}{gg}{rr}".upper()


def escapar(texto: str) -> str:
    return texto.replace("\r", "").replace("{", "(").replace("}", ")").replace("\n", r"\N")


def estilo_ass(
    nome: str,
    e: EstiloTexto,
    posicao: Posicao,
    espec: EspecificacaoVideo,
    *,
    cor_secundaria: str | None = None,
) -> EstiloAss:
    fonte = FONTES[e.fonte]
    alinhamento, margem_frac = _ALINHAMENTO[posicao]
    return EstiloAss(
        nome=nome,
        fonte=fonte.nome_ass,
        negrito=fonte.negrito,
        tamanho=e.tamanho,
        cor_primaria=cor_ass(e.cor),
        cor_secundaria=cor_ass(cor_secundaria or e.cor),
        cor_contorno=cor_ass(e.cor_contorno),
        cor_fundo=cor_ass("#000000", 0x00 if e.caixa else 0x80),
        contorno=e.contorno,
        caixa=e.caixa,
        alinhamento=alinhamento,
        margem_v=round(margem_frac * espec.altura),
        margem_lateral=round(_MARGEM_LATERAL * espec.largura),
    )


def _animacao(e: EstiloTexto) -> str:
    return {"nenhuma": "", "fade": _FADE, "pop": _POP}[e.animacao]


def eventos_textos(
    textos: Sequence[TextoNaTela], espec: EspecificacaoVideo
) -> tuple[list[EstiloAss], list[EventoAss]]:
    estilos: list[EstiloAss] = []
    eventos: list[EventoAss] = []
    for i, t in enumerate(textos):
        nome = f"Texto{i}"
        estilos.append(estilo_ass(nome, t.estilo, t.posicao, espec))
        tags = _animacao(t.estilo)
        if t.y is not None:
            tags += rf"\an5\pos({espec.largura // 2},{round(t.y * espec.altura)})"
        texto = (f"{{{tags}}}" if tags else "") + escapar(t.texto)
        eventos.append(EventoAss(1, t.inicio_s, t.fim_s, nome, texto))
    return estilos, eventos


def _ajustar_tempos(palavras: Sequence[Palavra], duracao_s: float) -> list[Palavra]:
    saida: list[Palavra] = []
    for i, p in enumerate(palavras):
        if p.inicio_s >= duracao_s:
            break
        fim = max(p.fim_s + FOLGA_PALAVRA_S, p.inicio_s + DURACAO_MINIMA_PALAVRA_S)
        if i + 1 < len(palavras):  # nunca sobrepor a próxima palavra
            fim = min(fim, max(palavras[i + 1].inicio_s, p.inicio_s + 0.05))
        fim = min(fim, duracao_s)
        saida.append(Palavra(p.texto, p.inicio_s, round(fim, 3), p.confianca))
    return saida


def eventos_legenda(
    palavras: Sequence[Palavra], legendas: Legendas, duracao_s: float, espec: EspecificacaoVideo
) -> tuple[list[EstiloAss], list[EventoAss]]:
    if not legendas.ativas or not palavras:
        return [], []
    ajustadas = _ajustar_tempos(palavras, duracao_s)
    fade = _FADE if legendas.estilo.animacao == "fade" else ""
    if legendas.modo == "palavra":
        estilo = estilo_ass("Legenda", legendas.estilo, legendas.posicao, espec)
        eventos_palavra = [
            EventoAss(
                0,
                p.inicio_s,
                p.fim_s,
                "Legenda",
                (f"{{{fade}}}" if fade else "") + escapar(p.texto),
            )
            for p in ajustadas
        ]
        return [estilo], eventos_palavra
    # modo "grupo": cor primária = destaque (palavra atual), secundária = cor base
    estilo_grupo = EstiloTexto(**{**legendas.estilo.model_dump(), "cor": legendas.cor_destaque})
    estilo = estilo_ass(
        "Legenda", estilo_grupo, legendas.posicao, espec, cor_secundaria=legendas.estilo.cor
    )
    eventos: list[EventoAss] = []
    n = legendas.palavras_por_grupo
    for i in range(0, len(ajustadas), n):
        grupo = ajustadas[i : i + n]
        partes = []
        for j, p in enumerate(grupo):
            fim = grupo[j + 1].inicio_s if j + 1 < len(grupo) else p.fim_s
            partes.append(f"{{\\k{max(round((fim - p.inicio_s) * 100), 1)}}}{escapar(p.texto)}")
        eventos.append(
            EventoAss(0, grupo[0].inicio_s, grupo[-1].fim_s, "Legenda", " ".join(partes))
        )
    return [estilo], eventos


def gerar_ass(plano: PlanoEdicao, palavras: Sequence[Palavra], espec: EspecificacaoVideo) -> str:
    estilos_l, eventos_l = eventos_legenda(palavras, plano.legendas, plano.duracao_s, espec)
    estilos_t, eventos_t = eventos_textos(plano.textos, espec)
    cabecalho = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {espec.largura}",
        f"PlayResY: {espec.altura}",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
    ]
    estilos = [e.linha() for e in [*estilos_l, *estilos_t]]
    eventos = [
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    eventos += [
        e.linha() for e in sorted([*eventos_l, *eventos_t], key=lambda e: (e.inicio_s, e.camada))
    ]
    return "\n".join([*cabecalho, *estilos, *eventos]) + "\n"


def tem_eventos(plano: PlanoEdicao, palavras: Sequence[Palavra]) -> bool:
    return bool(plano.textos) or (plano.legendas.ativas and bool(palavras))
