"""Conexão do agente pela tela Configurações globais → Agente.

Token e chave chegam como SecretStr e nunca são devolvidos nem registrados.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import SecretStr

from autora.agente import conexao
from autora.agente.provedor import ErroAgente
from autora.api.esquemas import PedidoEstrito
from autora.config import global_config
from autora.config.global_config import Etapa, Nivel
from autora.registro.log import registro_global

rotas = APIRouter(prefix="/api/agente", tags=["agente"])


class PedidoToken(PedidoEstrito):
    token: SecretStr


class PedidoChave(PedidoEstrito):
    chave: SecretStr


class PedidoConfirmacao(PedidoEstrito):
    confirmar: Literal[True]


class PedidoNiveis(PedidoEstrito):
    niveis: dict[Etapa, Nivel]


@rotas.get("")
def obter(request: Request) -> dict[str, Any]:
    return asdict(conexao.estado(request.app.state.dados))


@rotas.post("/instalar")
def instalar(request: Request) -> dict[str, Any]:
    try:
        conexao.instalar_claude(request.app.state.dados)
    except ErroAgente as e:
        raise HTTPException(502, e.mensagem_amigavel) from e
    return asdict(conexao.estado(request.app.state.dados))


@rotas.post("/abrir-login")
def abrir_login(request: Request) -> dict[str, bool]:
    try:
        conexao.abrir_login(request.app.state.dados)
    except ErroAgente as e:
        raise HTTPException(400, e.mensagem_amigavel) from e
    return {"aberto": True}


@rotas.post("/conectar/assinatura")
def conectar_assinatura(pedido: PedidoToken, request: Request) -> dict[str, Any]:
    r = conexao.conectar_assinatura(request.app.state.dados, pedido.token.get_secret_value())
    return asdict(r)


@rotas.post("/conectar/chave")
def conectar_chave(pedido: PedidoChave, request: Request) -> dict[str, Any]:
    r = conexao.conectar_chave(request.app.state.dados, pedido.chave.get_secret_value())
    return asdict(r)


@rotas.post("/testar")
def testar(request: Request) -> dict[str, Any]:
    return asdict(conexao.testar(request.app.state.dados))


@rotas.post("/desconectar")
def desconectar(_: PedidoConfirmacao, request: Request) -> dict[str, Any]:
    conexao.desconectar(request.app.state.dados)
    return asdict(conexao.estado(request.app.state.dados))


@rotas.put("/niveis")
def definir_niveis(pedido: PedidoNiveis, request: Request) -> dict[str, Any]:
    dados = request.app.state.dados
    cfg = global_config.carregar(dados)
    cfg.agente.niveis.update(pedido.niveis)
    global_config.salvar(cfg, dados)
    registro_global(dados).registrar(
        "usuario", "Nível do agente por etapa alterado.", detalhe={"niveis": pedido.niveis}
    )
    return asdict(conexao.estado(dados))
