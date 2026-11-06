"""Lista e criação mínima de perfis (o onboarding completo vem no passo 5) e o botão
"Criar agora" (rodada em segundo plano; a tela de revisão é o passo 9)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from autora.agente import conexao
from autora.agente.provedor import AgenteNaoConectado
from autora.api.esquemas import PedidoEstrito
from autora.perfil.esquema import SLUG_VALIDO
from autora.perfil.perfil import (
    Perfil,
    PerfilInvalido,
    PerfilJaExiste,
    PerfilNaoEncontrado,
    PerfilOcupado,
    listar,
)
from autora.rodada import estado as estado_criacao
from autora.rodada.executar import gerar

rotas = APIRouter(prefix="/api/perfis", tags=["perfis"])


class Criacao(BaseModel):
    estado: str = "ocioso"  # "ocioso" | "criando" | "pronto" | "falhou"
    mensagem: str | None = None
    pasta_saida: str | None = None
    iniciado_em: str | None = None
    terminado_em: str | None = None


class ResumoPerfil(BaseModel):
    slug: str
    nome: str
    pausado: bool
    estado: str  # "ok" | "problema"
    criacao: Criacao = Field(default_factory=Criacao)


def _criacao(slug: str) -> Criacao:
    return Criacao(**estado_criacao.consultar(slug).para_api())


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
                    criacao=_criacao(slug),
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


@rotas.post("/{slug}/criar-agora", status_code=202)
def criar_agora(slug: str, request: Request) -> dict[str, Any]:
    """Começa a criação de um post em segundo plano. Funciona com o sistema pausado."""
    if not SLUG_VALIDO.match(slug):
        raise HTTPException(422, "nome interno inválido")
    dados = request.app.state.dados
    try:
        perfil = Perfil.abrir(dados, slug)
    except PerfilNaoEncontrado as e:
        raise HTTPException(404, "Esse perfil não existe.") from e
    except PerfilInvalido as e:
        raise HTTPException(422, str(e)) from e
    try:
        provedor = conexao.provedor_atual(dados)
    except AgenteNaoConectado as e:
        raise HTTPException(400, f"{e.mensagem_amigavel} Conecte em Configurações globais.") from e

    def _trabalho() -> tuple[bool, str, str | None]:
        try:
            r = gerar(perfil, provedor, dados, origem="manual")
        except PerfilOcupado:
            return False, "Este perfil já está criando um post em outro lugar.", None
        return r.ok, r.mensagem, r.pasta_relativa  # nunca o caminho absoluto da máquina

    if not estado_criacao.iniciar_em_segundo_plano(slug, _trabalho):
        raise HTTPException(409, "Este perfil já está criando um post.")
    perfil.registro.registrar("usuario", "Criar agora acionado na tela.")
    return _criacao(slug).model_dump()
