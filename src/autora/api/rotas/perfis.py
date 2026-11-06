"""Lista e criação mínima de perfis (o onboarding completo vem no passo 5)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from autora.api.esquemas import PedidoEstrito
from autora.perfil.perfil import Perfil, PerfilInvalido, PerfilJaExiste, listar

rotas = APIRouter(prefix="/api/perfis", tags=["perfis"])


class ResumoPerfil(BaseModel):
    slug: str
    nome: str
    pausado: bool
    estado: str  # "ok" | "problema"


class PedidoCriar(PedidoEstrito):
    slug: str = Field(min_length=1, max_length=40)
    nome: str = Field(min_length=1, max_length=80)


@rotas.get("")
def listar_perfis(request: Request) -> list[ResumoPerfil]:
    dados = request.app.state.dados
    saida = []
    for slug in listar(dados):
        try:
            p = Perfil.abrir(dados, slug)
            saida.append(
                ResumoPerfil(
                    slug=slug,
                    nome=p.config.identidade.nome,
                    pausado=p.config.publicacao.pausado,
                    estado="ok",
                )
            )
        except PerfilInvalido:
            saida.append(ResumoPerfil(slug=slug, nome=slug, pausado=False, estado="problema"))
    return saida


@rotas.post("", status_code=201)
def criar(pedido: PedidoCriar, request: Request) -> ResumoPerfil:
    try:
        p = Perfil.criar(request.app.state.dados, pedido.slug, pedido.nome)
    except PerfilJaExiste as e:
        raise HTTPException(409, "Já existe um perfil com esse nome interno.") from e
    except PerfilInvalido as e:
        raise HTTPException(422, str(e)) from e
    return ResumoPerfil(slug=p.slug, nome=pedido.nome, pausado=False, estado="ok")
