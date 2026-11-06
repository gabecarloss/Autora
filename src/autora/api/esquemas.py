"""Base dos modelos de entrada da API local.

Todo corpo de pedido herda de PedidoEstrito: campo desconhecido vira erro 422 em vez de
ser ignorado em silêncio. Isso pega cedo uma divergência entre o front e o servidor e
não deixa dado inesperado entrar.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class PedidoEstrito(BaseModel):
    model_config = ConfigDict(extra="forbid")
