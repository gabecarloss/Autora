"""Proteções do servidor local.

- Token de sessão aleatório por abertura do app. A janela entra por
  /entrar?s=<token>, que troca o token por um cookie HttpOnly + SameSite=Strict e
  redireciona. Toda outra requisição exige o cookie (ou o cabeçalho X-Autora-Sessao,
  usado pelos testes). Outro programa ou um site aberto no navegador não tem o token.
- Host só 127.0.0.1/localhost (contra DNS rebinding) via TrustedHostMiddleware.
- Cabeçalhos: CSP restritiva, nosniff, sem referrer, sem embutir em frames.
"""

from __future__ import annotations

import secrets
from collections.abc import Awaitable, Callable
from typing import Final

from fastapi import Request, Response
from fastapi.responses import JSONResponse, RedirectResponse

COOKIE: Final = "autora_sessao"
CABECALHO: Final = "x-autora-sessao"
HOSTS_PERMITIDOS: Final = ["127.0.0.1", "localhost"]

CSP: Final = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; media-src 'self' blob:; font-src 'self'; "
    "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'; "
    "object-src 'none'"
)


def novo_token() -> str:
    return secrets.token_urlsafe(32)


Proximo = Callable[[Request], Awaitable[Response]]


def middleware_sessao(token: str) -> Callable[[Request, Proximo], Awaitable[Response]]:
    async def _mw(request: Request, call_next: Proximo) -> Response:
        if request.url.path == "/entrar":
            recebido = request.query_params.get("s", "")
            if not secrets.compare_digest(recebido, token):
                return JSONResponse({"erro": "sessão inválida"}, status_code=401)
            resp: Response = RedirectResponse("/", status_code=303)
            resp.set_cookie(COOKIE, token, httponly=True, samesite="strict", secure=False, path="/")
            return resp
        recebido = request.cookies.get(COOKIE) or request.headers.get(CABECALHO) or ""
        if not secrets.compare_digest(recebido, token):
            return JSONResponse({"erro": "sessão inválida"}, status_code=401)
        return await call_next(request)

    return _mw


async def middleware_cabecalhos(request: Request, call_next: Proximo) -> Response:
    resp = await call_next(request)
    resp.headers["Content-Security-Policy"] = CSP
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Cache-Control"] = "no-store"
    return resp
