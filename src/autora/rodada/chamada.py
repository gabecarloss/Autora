"""Chamada ao agente com resposta estruturada e validada (skill chamada-ao-agente).

- Texto de sistema sempre por `montar_sistema` (mandato integral e primeiro).
- Esquema JSON do modelo pydantic, adaptado ao que a API aceita (`transform_schema`
  move restrições não suportadas para a descrição); a validação de verdade é local.
- Resposta inválida: pede de novo UMA vez, com a lista de problemas; nunca "conserta".
- Nível por etapa: o que o usuário escolheu na tela (global.json).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, TypeVar

from anthropic import transform_schema
from pydantic import BaseModel, ValidationError

from autora.agente.contexto import montar_sistema
from autora.agente.provedor import Pedido, ProvedorAgente, RespostaInvalida, chamar_registrando
from autora.config import global_config
from autora.config.global_config import Etapa, Nivel
from autora.perfil.perfil import Perfil

T = TypeVar("T", bound=BaseModel)


def esquema_para_agente(modelo: type[BaseModel]) -> dict[str, Any]:
    return transform_schema(modelo.model_json_schema())


def nivel_configurado(dados: Path, etapa: Etapa) -> Nivel:
    return global_config.carregar(dados).agente.niveis.get(etapa, "automatico")


def _problemas_de_validacao(e: ValidationError) -> list[str]:
    saida = []
    for erro in e.errors():
        caminho = ".".join(str(p) for p in erro.get("loc", ())) or "(raiz)"
        saida.append(f"{caminho}: {erro.get('msg')}")
    return saida


def chamar_com_esquema(
    provedor: ProvedorAgente,
    perfil: Perfil,
    con: sqlite3.Connection,
    *,
    etapa: Etapa,
    mensagem: str,
    modelo: type[T],
    ferramentas: Sequence[str] = (),
    nivel: Nivel = "automatico",
    rodada_id: int | None,
    post_id: int | None,
    conferir: Callable[[T], list[str]] | None = None,
    tempo_limite_s: int = 900,
) -> T:
    """Chama, valida, confere; repete uma vez se vier inválida; senão RespostaInvalida."""
    sistema = montar_sistema(perfil.memoria, etapa)
    esquema = esquema_para_agente(modelo)
    problemas: list[str] = []
    for tentativa in (1, 2):
        texto = mensagem
        if problemas:
            lista = "\n".join(f"- {p}" for p in problemas)
            texto += (
                "\n\n# Problemas da resposta anterior\n\nA resposta anterior não pôde ser "
                f"usada pelos motivos abaixo. Refaça a decisão corrigindo cada ponto:\n{lista}\n"
            )
        pedido = Pedido(
            etapa=etapa,
            sistema=sistema,
            mensagem=texto,
            ferramentas=tuple(ferramentas),
            esquema_json=esquema,
            nivel=nivel,
            tempo_limite_s=tempo_limite_s,
        )
        resposta = chamar_registrando(
            provedor, pedido, perfil.registro, con=con, rodada_id=rodada_id, post_id=post_id
        )
        try:
            obj = modelo.model_validate(resposta.dados)
        except ValidationError as e:
            problemas = _problemas_de_validacao(e)
        else:
            problemas = conferir(obj) if conferir is not None else []
            if not problemas:
                return obj
        perfil.registro.registrar(
            "etapa",
            "A resposta do agente veio fora do esperado"
            + ("; pedindo de novo." if tentativa == 1 else " pela segunda vez."),
            etapa=etapa,
            rodada_id=rodada_id,
            post_id=post_id,
            detalhe={"tentativa": tentativa, "problemas": problemas},
        )
    raise RespostaInvalida(
        "O agente não devolveu uma resposta válida depois de duas tentativas.",
        "\n".join(problemas),
    )
