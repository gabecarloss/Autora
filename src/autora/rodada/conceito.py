"""Etapa "conceito" (ideia do post): o agente decide formato, clipes, gancho, tema, som,
horário e capa, com motivo registrado (seções 5 e 6).

Mensagem (contexto longo antes, tarefa depois): perfil → plataforma → limites desta
versão → padrão mínimo de transformação → tarefa → fichas dos clipes em <dados_externos>.
O texto de sistema vem de `montar_sistema` (mandato integral e primeiro).
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from typing import Final

from autora.agente.contexto import dados_externos
from autora.agente.provedor import FERRAMENTAS_POR_ETAPA, ProvedorAgente
from autora.biblioteca.ficha import FichaClipe
from autora.config.global_config import Nivel
from autora.edicao import fontes
from autora.perfil.esquema import ConfigPerfil
from autora.perfil.perfil import Perfil
from autora.plataformas.base import Plataforma
from autora.rodada.chamada import chamar_com_esquema
from autora.rodada.esquemas import COMO_VERIFICAR_ELEMENTO, FORMATOS, Conceito
from autora.util.tempo import agora_iso

# PROVISÓRIO (passo 2): o que esta versão do sistema consegue produzir. Cada item some
# quando o passo correspondente entrar (narração: 7; geração: 7; som: 6; revisor: 8).
LIMITES_DESTA_VERSAO: Final = """\
# Limites desta versão do sistema

Esta é a primeira versão do sistema. Decida dentro do que ela consegue produzir hoje:
- Não há narração nem voz sintética: o áudio do post é o áudio original dos clipes.
- Não há geração de material (animação, personagem, imagem): só clipes da pasta.
- O som (música da plataforma) é adicionado pelo usuário no app na hora de postar.
  Você pode sugerir um som, mas só com nome se tiver localizado uma fonte verificável
  (link e data). Sem fonte, descreva a função do som e deixe o nome vazio. "Não sei"
  é resposta válida.
- Um post nesta rodada.
- Recursos de edição disponíveis para o roteiro (etapa seguinte): cortes e remontagem
  de trechos, velocidade (0,5x a 2x), enquadramento 9:16 (fundo desfocado ou recorte no
  ponto de interesse), zoom suave, textos na tela com posição e tempo, e legendas
  sincronizadas palavra por palavra a partir da fala dos clipes (só se houver fala).
"""

_PADRAO_MINIMO: Final = """\
# Padrão mínimo de transformação (seção 6 do briefing)

Todo post com material da biblioteca precisa de pelo menos DOIS elementos autorais
verificáveis, de tipos distintos. "Só legenda e gancho" não existe, mesmo em clipe já
bom. Os tipos que o sistema consegue conferir no roteiro, e como confere cada um:
"""

_TAREFA: Final = """\
# Tarefa: a ideia do post desta rodada

Abaixo, em <dados_externos>, estão as fichas dos clipes disponíveis (metadados,
transcrição da fala quando houver, e uma descrição do conteúdo quando houver). Clipes
já usados em posts anteriores não aparecem; nunca reposte material.

Decida o post desta rodada e devolva só o JSON no formato pedido. Para isso:
1. Responda as cinco perguntas de "Como você raciocina antes de agir" no campo
   `raciocinio`, com conteúdo específico sobre ESTE material, não frases genéricas.
2. Escolha os clipes (pelo menos um) e o trecho de interesse fica para o roteiro.
3. Escolha formato, tema, conceito, gancho (e 2 a 4 alternativas diferentes dele),
   descrição do post, 3 a 5 hashtags, horário sugerido, texto da capa e som.
4. Declare os elementos autorais (dois ou mais, de tipos distintos) e, em cada um,
   o que o roteiro precisa ter para provar que ele existe.
5. Cada escolha com motivo. Sem motivo, não há decisão.
6. Evite clipe com risco alto de direitos autorais (filme, série, TV) ou diga por que
   a transformação pesada justifica.
7. O que você não sabe vai em `nao_sei`; não invente fonte, nome de som nem número.
"""


def descrever_perfil(config: ConfigPerfil) -> str:
    i, c = config.identidade, config.conteudo
    nichos = ", ".join(
        f"{n.nome}" + (f" ({n.proporcao:.0%})" if n.proporcao is not None else "") for n in c.nichos
    )
    fonte = {
        "livre": "livre (pasta, geração ou os dois)",
        "so_pasta": "só da pasta",
        "so_geracao": "só criado pelo agente",
    }[c.fonte_material]
    linhas = [
        "# Perfil",
        "",
        f"- Nome da conta: {i.nome}" + (f" ({i.arroba})" if i.arroba else ""),
        f"- Personalidade: {', '.join(i.personalidade_adjetivos) or 'não definida'}"
        + (f". {i.personalidade_frase}" if i.personalidade_frase else ""),
        "- Objetivos, em ordem de prioridade: "
        + ("; ".join(i.objetivos) if i.objetivos else "não definidos"),
        f"- Nicho(s): {nichos or 'não definido (decida pelo material e registre a suposição)'}",
        f"- Idioma de origem do material: {c.idioma_origem or 'não informado'}",
        "- Idioma de saída (textos, legendas, descrição): "
        + (i.idioma_saida or "português do Brasil"),
        "- Conta nova: "
        + (
            "sim (regime de início, seção 8.8: assunto fechado, formato variado)"
            if config.publicacao.conta_nova
            else "não"
        ),
        f"- Origem do material permitida: {fonte}",
        f"- Data e hora de agora: {agora_iso()}",
    ]
    return "\n".join(linhas) + "\n"


def descrever_plataforma(plataforma: Plataforma) -> str:
    v = plataforma.video
    musica = "nunca embutida (o usuário adiciona no app)" if not v.musica_embutida else "embutida"
    return (
        "# Plataforma\n\n"
        f"- {plataforma.nome_amigavel}: vídeo {v.largura}x{v.altura}, {v.fps} fps, {v.codec}; "
        f"música {musica}.\n"
    )


def _padrao_minimo() -> str:
    itens = "\n".join(f"- `{tipo}`: {como}" for tipo, como in COMO_VERIFICAR_ELEMENTO.items())
    return _PADRAO_MINIMO + itens + "\n"


def mensagem_conceito(perfil: Perfil, plataforma: Plataforma, fichas: Sequence[FichaClipe]) -> str:
    fichas_json = json.dumps([f.para_agente() for f in fichas], ensure_ascii=False, indent=1)
    partes = [
        descrever_perfil(perfil.config),
        descrever_plataforma(plataforma),
        LIMITES_DESTA_VERSAO,
        _padrao_minimo(),
        f"Formatos aceitos no campo `formato.valor`: {', '.join(FORMATOS)} "
        '("outro" exige `descricao_formato`).\n'
        f"Fontes disponíveis para textos (o roteiro escolhe): {', '.join(fontes.CHAVES)}.\n",
        _TAREFA,
        dados_externos(fichas_json, fonte="fichas dos clipes da biblioteca do perfil"),
    ]
    return "\n".join(partes)


def conferir_conceito(conceito: Conceito, fichas: Sequence[FichaClipe]) -> list[str]:
    """Checagens contra as fichas (o que o esquema sozinho não vê)."""
    ids = {f.id for f in fichas}
    problemas = [
        f"clipe {c.clipe_id} não está entre os clipes disponíveis ({sorted(ids)})"
        for c in conceito.clipes_escolhidos
        if c.clipe_id not in ids
    ]
    escolhidas = {f.id: f for f in fichas}
    total = sum(
        escolhidas[c.clipe_id].duracao_s
        for c in conceito.clipes_escolhidos
        if c.clipe_id in escolhidas
    )
    if problemas == [] and conceito.duracao_alvo_s > total + 0.5:
        problemas.append(
            f"duração alvo de {conceito.duracao_alvo_s:.0f} s maior que o material escolhido "
            f"({total:.1f} s); sem narração nem geração, o vídeo não pode ser mais longo "
            "que os clipes"
        )
    return problemas


def decidir_conceito(
    perfil: Perfil,
    provedor: ProvedorAgente,
    con: sqlite3.Connection,
    fichas: Sequence[FichaClipe],
    plataforma: Plataforma,
    *,
    rodada_id: int | None,
    post_id: int | None,
    nivel: Nivel = "automatico",
) -> Conceito:
    return chamar_com_esquema(
        provedor,
        perfil,
        con,
        etapa="conceito",
        mensagem=mensagem_conceito(perfil, plataforma, fichas),
        modelo=Conceito,
        ferramentas=tuple(sorted(FERRAMENTAS_POR_ETAPA["conceito"])),
        nivel=nivel,
        rodada_id=rodada_id,
        post_id=post_id,
        conferir=lambda c: conferir_conceito(c, fichas),
    )
