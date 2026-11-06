"""Aplicação FastAPI: só regras de transporte; a regra de negócio fica nos módulos de domínio."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from autora.api import seguranca
from autora.api.rotas import agente, perfis, sistema

PASTA_FRONT_PADRAO = Path(__file__).resolve().parents[3] / "frontend" / "dist"


def criar_app(
    dados: Path,
    token_sessao: str,
    *,
    pasta_front: Path | None = PASTA_FRONT_PADRAO,
    desenvolvimento: bool = False,
) -> FastAPI:
    app = FastAPI(
        title="Autora",
        docs_url="/api/docs" if desenvolvimento else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if desenvolvimento else None,
    )
    app.state.dados = dados

    @app.exception_handler(RequestValidationError)
    async def _validacao(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Nunca ecoa o valor recebido (pode ser um token colado no campo errado).
        erros: list[dict[str, Any]] = [
            {"campo": ".".join(str(p) for p in e.get("loc", ())), "problema": e.get("msg")}
            for e in exc.errors()
        ]
        return JSONResponse({"erro": "dados inválidos", "detalhes": erros}, status_code=422)

    app.include_router(sistema.rotas)
    app.include_router(agente.rotas)
    app.include_router(perfis.rotas)

    if pasta_front is not None and (pasta_front / "index.html").exists():
        app.mount("/", StaticFiles(directory=pasta_front, html=True), name="front")
    else:

        @app.get("/", include_in_schema=False)
        def _sem_front() -> HTMLResponse:
            return HTMLResponse(
                "<h1>Autora</h1><p>As telas ainda não foram montadas. "
                "Rode <code>npm run build</code> na pasta frontend.</p>"
            )

    # Ordem: o último adicionado roda primeiro. Host → cabeçalhos → sessão.
    app.middleware("http")(seguranca.middleware_sessao(token_sessao))
    app.middleware("http")(seguranca.middleware_cabecalhos)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=seguranca.HOSTS_PERMITIDOS)
    return app
