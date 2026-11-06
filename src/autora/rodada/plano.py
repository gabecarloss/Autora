"""Etapa "plano" (roteiro de edição): o agente materializa a ideia do post em cortes,
textos, legendas e capa (seção 5, item 4). O código traduz o JSON em ffmpeg."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from typing import Final

from autora.agente.contexto import dados_externos
from autora.agente.provedor import ProvedorAgente
from autora.biblioteca.ficha import FichaClipe
from autora.config.global_config import Nivel
from autora.edicao import fontes
from autora.edicao.plano import (
    DURACAO_MAXIMA_S,
    DURACAO_MINIMA_S,
    PlanoEdicao,
    verificar_contra_clipes,
)
from autora.perfil.perfil import Perfil
from autora.plataformas.base import EspecificacaoVideo, Plataforma
from autora.rodada.chamada import chamar_com_esquema
from autora.rodada.conceito import descrever_perfil, descrever_plataforma
from autora.rodada.esquemas import COMO_VERIFICAR_ELEMENTO, Conceito
from autora.rodada.transformacao import conferir_padrao_minimo

_REGRAS: Final = f"""\
# Regras do roteiro de edição

- Saída: {{saida}}. Duração final entre {DURACAO_MINIMA_S:.0f} e \
{DURACAO_MAXIMA_S:.0f} s.
- Tempos em segundos. Nos trechos, `inicio_s` e `fim_s` são no CLIPE DE ORIGEM (dentro
  da duração dele). Em textos, capa e zoom, os tempos são na LINHA DO TEMPO FINAL: cada
  trecho dura (fim_s - inicio_s) / velocidade e começa onde o anterior terminou.
- Velocidade de 0,5 a 2. Enquadramento: "recorte" (ponto de interesse foco_x/foco_y) ou
  "fundo_desfocado" (clipe inteiro sobre fundo desfocado); em clipe já vertical, tanto faz.
- Textos na tela: até 120 caracteres cada, com `papel` (gancho, narrativa, comentario,
  destaque), posição (topo, centro, base) ou `y` entre 0,08 e 0,78 (zona segura da
  plataforma), fonte entre as disponíveis, tamanho 36–160, cores #RRGGBB.
- Legendas: só fazem sentido se os trechos escolhidos têm fala; elas são geradas
  automaticamente a partir do áudio final. Você decide se ficam ativas, o modo
  (palavra ou grupo) e o estilo.
- Capa: um segundo da linha do tempo final e um texto curto (até 60 caracteres).
- `motivos`: por que este ritmo, este enquadramento, estes textos e estas legendas.
- Os elementos autorais declarados na ideia do post PRECISAM aparecer no roteiro; o
  sistema confere cada um assim:
"""

_TAREFA: Final = """\
# Tarefa: o roteiro de edição deste post

Abaixo, em <dados_externos>, a ideia do post decidida na etapa anterior e as fichas dos
clipes escolhidos. Escreva o roteiro que materializa essa ideia: cortes, ritmo, textos,
legendas, capa e áudio, dentro das regras acima. Devolva só o JSON no formato pedido.
Se a ideia pedir algo que o roteiro não consegue cumprir, faça o melhor possível dentro
das regras e explique em `motivos`.
"""


def regras_do_roteiro(espec: EspecificacaoVideo) -> str:
    """Regras com a resolução e o fps da plataforma do perfil."""
    itens = "\n".join(f"- `{tipo}`: {como}" for tipo, como in COMO_VERIFICAR_ELEMENTO.items())
    saida = f"{espec.largura}x{espec.altura}, {espec.fps} fps"
    return _REGRAS.replace("{saida}", saida) + itens + "\n"


def mensagem_plano(
    perfil: Perfil, plataforma: Plataforma, conceito: Conceito, fichas: Sequence[FichaClipe]
) -> str:
    escolhidas = [f for f in fichas if f.id in conceito.ids_escolhidos()]
    partes = [
        descrever_perfil(perfil.config),
        descrever_plataforma(plataforma),
        regras_do_roteiro(plataforma.video),
        f"Fontes disponíveis: {', '.join(fontes.CHAVES)}.\n",
        _TAREFA,
        dados_externos(
            conceito.model_dump_json(indent=1), fonte="ideia do post decidida na etapa anterior"
        ),
        dados_externos(
            json.dumps([f.para_agente() for f in escolhidas], ensure_ascii=False, indent=1),
            fonte="fichas dos clipes escolhidos",
        ),
    ]
    return "\n".join(partes)


def conferir_plano(
    plano: PlanoEdicao, conceito: Conceito, fichas: Sequence[FichaClipe]
) -> list[str]:
    duracoes = {f.id: f.duracao_s for f in fichas}
    problemas = verificar_contra_clipes(plano, duracoes, conceito.ids_escolhidos())
    return problemas or conferir_padrao_minimo(conceito, plano)


def roteirizar(
    perfil: Perfil,
    provedor: ProvedorAgente,
    con: sqlite3.Connection,
    conceito: Conceito,
    fichas: Sequence[FichaClipe],
    plataforma: Plataforma,
    *,
    rodada_id: int | None,
    post_id: int | None,
    nivel: Nivel = "automatico",
) -> PlanoEdicao:
    return chamar_com_esquema(
        provedor,
        perfil,
        con,
        etapa="plano",
        mensagem=mensagem_plano(perfil, plataforma, conceito, fichas),
        modelo=PlanoEdicao,
        nivel=nivel,
        rodada_id=rodada_id,
        post_id=post_id,
        conferir=lambda p: conferir_plano(p, conceito, fichas),
    )
