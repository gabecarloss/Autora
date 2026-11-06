"""Conexão por assinatura Claude: Claude Code em modo não interativo (`claude -p`).

Isolamento (plano do passo 1, "O agente e dados não confiáveis"):
- o token vem do keyring e só chega ao processo pelo ambiente daquela chamada;
- CLAUDE_CONFIG_DIR aponta para uma pasta do app, sem login nem configurações:
  o agente nunca usa o login do desenvolvimento nem lê CLAUDE.md da máquina;
- roda numa pasta de trabalho vazia e temporária;
- ferramentas restritas à lista da etapa (no máximo WebSearch e WebFetch);
- --safe-mode desliga plugins, hooks, MCP e personalizações;
- --permission-prompts none: qualquer coisa que pediria permissão é negada.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from autora.agente.provedor import (
    MODELO_POR_NIVEL_ASSINATURA,
    AgenteNaoConectado,
    ErroAgente,
    LimiteDeUso,
    Pedido,
    Resposta,
    RespostaInvalida,
    resolver_nivel,
)

_SEM_JANELA = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
_PADRAO_LIMITE = re.compile(r"(?i)(usage limit|rate limit|limit reached|limite)")
_PADRAO_AUTH = re.compile(
    r"(?i)(not logged in|/login|invalid api key|oauth|unauthori[sz]ed|authentication)"
)


def ambiente_isolado(token: str, pasta_config: Path) -> dict[str, str]:
    """Ambiente limpo: nada de variáveis CLAUDE*/ANTHROPIC* herdadas do desenvolvimento."""
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("CLAUDE", "ANTHROPIC"))}
    pasta_config.mkdir(parents=True, exist_ok=True)
    env["CLAUDE_CONFIG_DIR"] = str(pasta_config)
    env["CLAUDE_CODE_OAUTH_TOKEN"] = token
    env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
    env["DISABLE_AUTOUPDATER"] = "1"
    return env


def montar_argumentos(executavel: Path, pedido: Pedido, arquivo_sistema: Path) -> list[str]:
    nivel = resolver_nivel(pedido.etapa, pedido.nivel)
    args = [
        str(executavel),
        "-p",
        "--output-format",
        "json",
        "--model",
        MODELO_POR_NIVEL_ASSINATURA[nivel],
        "--system-prompt-file",
        str(arquivo_sistema),
        "--tools",
        ",".join(pedido.ferramentas),
        "--no-session-persistence",
        "--safe-mode",
        "--permission-prompts",
        "none",
        "--strict-mcp-config",
        "--disable-slash-commands",
    ]
    if pedido.ferramentas:
        args += ["--allowedTools", ",".join(pedido.ferramentas)]
    if pedido.esquema_json is not None:
        args += ["--json-schema", json.dumps(pedido.esquema_json, ensure_ascii=False)]
    return args


def interpretar_saida(stdout: str, stderr: str, codigo: int, pedido: Pedido) -> Resposta:
    try:
        saida: dict[str, Any] = json.loads(stdout)
    except json.JSONDecodeError as e:
        texto = (stderr or stdout or "").strip()[:2000]
        if _PADRAO_AUTH.search(texto):
            raise AgenteNaoConectado("A conexão com a assinatura não está válida.", texto) from e
        raise ErroAgente("O agente devolveu uma resposta ilegível.", texto) from e

    resultado = str(saida.get("result") or "")
    if saida.get("is_error") or codigo != 0:
        status = saida.get("api_error_status")
        detalhe = json.dumps(
            {k: saida.get(k) for k in ("result", "terminal_reason", "api_error_status")},
            ensure_ascii=False,
        )
        if status in (401, 403) or _PADRAO_AUTH.search(resultado):
            raise AgenteNaoConectado("A conexão com a assinatura não está válida.", detalhe)
        if status == 429 or _PADRAO_LIMITE.search(resultado):
            raise LimiteDeUso("O limite de uso da assinatura foi atingido.", detalhe)
        raise ErroAgente("O agente encontrou um erro ao responder.", detalhe)

    uso = saida.get("usage") or {}
    entrada = int(uso.get("input_tokens") or 0) + int(uso.get("cache_creation_input_tokens") or 0)
    modelos = list((saida.get("modelUsage") or {}).keys())
    dados: Any | None = None
    if pedido.esquema_json is not None:
        dados = saida.get("structured_output")
        if dados is None:
            try:
                dados = json.loads(resultado)
            except json.JSONDecodeError as e:
                raise RespostaInvalida(
                    "O agente não devolveu os dados no formato pedido.", resultado[:2000]
                ) from e
    return Resposta(
        texto=resultado,
        dados=dados,
        modelo=",".join(modelos) or "desconhecido",
        tokens_entrada=entrada,
        tokens_saida=int(uso.get("output_tokens") or 0),
        tokens_cache=int(uso.get("cache_read_input_tokens") or 0),
        custo_usd=float(saida["total_cost_usd"]) if "total_cost_usd" in saida else None,
        duracao_ms=int(saida.get("duration_ms") or 0),
        extras={"pesquisas_web": (uso.get("server_tool_use") or {}).get("web_search_requests")},
    )


class ProvedorAssinatura:
    nome = "assinatura"

    def __init__(self, executavel: Path, token: str, pasta_isolada: Path) -> None:
        self.executavel = executavel
        self._token = token
        self.pasta_isolada = pasta_isolada

    def chamar(self, pedido: Pedido) -> Resposta:
        trabalho = self.pasta_isolada / "trabalho"
        trabalho.mkdir(parents=True, exist_ok=True)
        inicio = time.monotonic()
        with tempfile.TemporaryDirectory(dir=trabalho) as cwd:
            arquivo_sistema = Path(cwd) / "base.md"
            arquivo_sistema.write_text(pedido.sistema, encoding="utf-8")
            args = montar_argumentos(self.executavel, pedido, arquivo_sistema)
            try:
                proc = subprocess.run(  # noqa: S603 - argumentos em lista, sem shell
                    args,
                    input=pedido.mensagem,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    cwd=cwd,
                    env=ambiente_isolado(self._token, self.pasta_isolada / "config"),
                    timeout=pedido.tempo_limite_s,
                    creationflags=_SEM_JANELA,
                    check=False,
                )
            except subprocess.TimeoutExpired as e:
                raise ErroAgente(
                    "O agente demorou demais e a chamada foi interrompida.",
                    f"tempo limite de {pedido.tempo_limite_s}s",
                ) from e
            except OSError as e:
                raise AgenteNaoConectado(
                    "O programa do agente não pôde ser iniciado.", str(e)
                ) from e
        resp = interpretar_saida(proc.stdout, proc.stderr, proc.returncode, pedido)
        if resp.duracao_ms == 0:
            resp.duracao_ms = int((time.monotonic() - inicio) * 1000)
        return resp
