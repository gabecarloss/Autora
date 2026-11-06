"""Integração com o agente REAL. Roda só com `uv run pytest -m agente`.

Usa a conexão configurada no app (pasta de dados real). Se o agente não estiver
conectado, o teste é pulado.
"""

from __future__ import annotations

import os

import pytest

from autora.agente import conexao
from autora.config.global_config import pasta_dados

pytestmark = pytest.mark.agente


@pytest.fixture(autouse=True)
def cofre() -> None:  # sobrepõe o cofre falso: aqui usamos o cofre real
    return None


def test_agente_real_responde() -> None:
    os.environ.pop("AUTORA_DADOS", None)
    dados = pasta_dados()
    try:
        conexao.provedor_atual(dados)
    except conexao.AgenteNaoConectado:
        pytest.skip("agente não conectado no app")
    r = conexao.testar(dados)
    assert r.ok, r.mensagem
    assert r.resposta
    assert r.duracao_ms and r.duracao_ms > 0
