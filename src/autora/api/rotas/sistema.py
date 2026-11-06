"""Estado do sistema: ligado / pausado / manual (seção 15.1)."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel

from autora.api.esquemas import PedidoEstrito
from autora.config import global_config
from autora.config.global_config import OrigemPastaDados
from autora.registro.log import registro_global

rotas = APIRouter(prefix="/api/sistema", tags=["sistema"])


class EstadoSistema(BaseModel):
    estado: Literal["ligado", "pausado", "manual"]
    modo: Literal["automatico", "manual"]
    pausado: bool
    pasta_dados: str
    """Pasta de dados em uso nesta máquina (mostrada em Configurações globais)."""
    origem_pasta_dados: OrigemPastaDados


class PedidoModo(PedidoEstrito):
    modo: Literal["automatico", "manual"]


def _estado(request: Request) -> EstadoSistema:
    dados = request.app.state.dados
    cfg = global_config.carregar(dados)
    return EstadoSistema(
        estado=cfg.estado_sistema,
        modo=cfg.modo,
        pausado=cfg.pausado,
        pasta_dados=str(dados),
        origem_pasta_dados=global_config.origem_pasta_dados(),
    )


@rotas.get("")
def obter(request: Request) -> EstadoSistema:
    return _estado(request)


def _definir_pausa(request: Request, pausado: bool) -> EstadoSistema:
    dados = request.app.state.dados
    cfg = global_config.carregar(dados)
    cfg.pausado = pausado
    global_config.salvar(cfg, dados)
    registro_global(dados).registrar(
        "usuario", "Sistema pausado." if pausado else "Sistema religado."
    )
    return _estado(request)


@rotas.post("/pausar")
def pausar(request: Request) -> EstadoSistema:
    return _definir_pausa(request, True)


@rotas.post("/ligar")
def ligar(request: Request) -> EstadoSistema:
    return _definir_pausa(request, False)


@rotas.put("/modo")
def definir_modo(pedido: PedidoModo, request: Request) -> EstadoSistema:
    dados = request.app.state.dados
    cfg = global_config.carregar(dados)
    cfg.modo = pedido.modo
    global_config.salvar(cfg, dados)
    registro_global(dados).registrar(
        "usuario",
        "Criação automática ligada." if pedido.modo == "automatico" else "Criação manual ligada.",
    )
    return _estado(request)
