"""Padrão mínimo de transformação (seção 6) conferido por código no roteiro.

PROVISÓRIO até o passo 8: o revisor independente e as verificações por chamada ao
agente substituem/complementam isto. Aqui só se confere que cada elemento autoral
declarado na ideia do post tem evidência no roteiro. Gancho sozinho nunca conta.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Final

from autora.edicao.plano import PlanoEdicao
from autora.rodada.esquemas import COMO_VERIFICAR_ELEMENTO, Conceito

MINIMO_ELEMENTOS: Final = 2


def _narrativa(p: PlanoEdicao) -> bool:
    return sum(t.papel == "narrativa" for t in p.textos) >= 2


def _comentario(p: PlanoEdicao) -> bool:
    return any(t.papel == "comentario" for t in p.textos)


def _remontagem(p: PlanoEdicao) -> bool:
    if len(p.trechos) < 2:
        return False
    clipes = {t.clipe_id for t in p.trechos}
    if len(clipes) >= 2:
        return True
    inicios = [t.inicio_s for t in p.trechos]
    if inicios != sorted(inicios):
        return True
    usado = sum(t.duracao_fonte_s for t in p.trechos)
    janela = max(t.fim_s for t in p.trechos) - min(t.inicio_s for t in p.trechos)
    return janela > 0 and (janela - usado) / janela >= 0.3


def _ritmo(p: PlanoEdicao) -> bool:
    if any(t.velocidade != 1 for t in p.trechos):
        return True
    media = sum(t.duracao_final_s for t in p.trechos) / len(p.trechos)
    return len(p.trechos) >= 3 and media <= 3.0


def _compilacao(p: PlanoEdicao) -> bool:
    return len({t.clipe_id for t in p.trechos}) >= 2 and any(
        t.papel in ("destaque", "narrativa") for t in p.textos
    )


def _zoom(p: PlanoEdicao) -> bool:
    return any(t.zoom is not None for t in p.trechos)


_CHECAGEM: Final[dict[str, Callable[[PlanoEdicao], bool]]] = {
    "narrativa_propria": _narrativa,
    "comentario": _comentario,
    "remontagem": _remontagem,
    "ritmo_proprio": _ritmo,
    "compilacao_com_criterio": _compilacao,
    "zoom_destaque": _zoom,
}


def elementos_atendidos(plano: PlanoEdicao) -> set[str]:
    return {tipo for tipo, checa in _CHECAGEM.items() if checa(plano)}


def conferir_padrao_minimo(conceito: Conceito, plano: PlanoEdicao) -> list[str]:
    """Problemas encontrados (vazio = padrão mínimo atendido)."""
    atendidos = elementos_atendidos(plano)
    problemas = [
        f"elemento autoral '{e.tipo}' declarado na ideia do post não aparece no roteiro "
        f"(precisa de: {COMO_VERIFICAR_ELEMENTO[e.tipo]})"
        for e in conceito.elementos_autorais
        if e.tipo not in atendidos
    ]
    declarados = {e.tipo for e in conceito.elementos_autorais}
    if len(declarados & atendidos) < MINIMO_ELEMENTOS:
        problemas.append(
            f"o roteiro comprova {len(declarados & atendidos)} elemento(s) autoral(is) de tipos "
            f"distintos; o padrão mínimo exige {MINIMO_ELEMENTOS}"
        )
    return problemas
