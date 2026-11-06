"""Registro (seção 9.5): uma linha JSON por evento, um arquivo por dia.

Toda etapa, decisão, chamada a serviço e erro passa por aqui. Antes de gravar, todo
texto passa pela máscara de segredos. `mensagem` é o texto amigável mostrado na tela
Bastidores; `detalhe` guarda o resto (raciocínio, erro inteiro, parâmetros).
"""

from __future__ import annotations

import json
import logging
import threading
import traceback
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Literal

from autora.config.segredos import mascarar_texto
from autora.util.tempo import agora, agora_iso, hoje

TipoEvento = Literal["rodada", "etapa", "decisao", "servico", "erro", "usuario", "teste", "sistema"]

_locks: dict[Path, threading.Lock] = {}
_locks_guard = threading.Lock()

_log_python = logging.getLogger("autora")


def _lock_para(caminho: Path) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(caminho, threading.Lock())


def mascarar(obj: Any) -> Any:
    """Aplica a máscara de segredos recursivamente em strings, listas e dicionários."""
    if isinstance(obj, str):
        return mascarar_texto(obj)
    if isinstance(obj, dict):
        return {str(k): mascarar(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [mascarar(v) for v in obj]
    return obj


@dataclass
class ResumoDia:
    data: date
    eventos: int
    erros: int
    por_tipo: dict[str, int]
    custo_usd: float


class Registro:
    """Escreve eventos em <pasta>/AAAA-MM-DD.jsonl. Seguro entre threads."""

    def __init__(self, pasta_logs: Path, escopo: str) -> None:
        self.pasta = pasta_logs
        self.escopo = escopo  # slug do perfil ou "global"

    def _arquivo(self, dia: date) -> Path:
        return self.pasta / f"{dia.isoformat()}.jsonl"

    def registrar(
        self,
        tipo: TipoEvento,
        mensagem: str,
        *,
        etapa: str | None = None,
        rodada_id: int | None = None,
        post_id: int | None = None,
        detalhe: dict[str, Any] | None = None,
        duracao_ms: int | None = None,
        custo_usd: float | None = None,
    ) -> None:
        evento: dict[str, Any] = {
            "ts": agora_iso(),
            "escopo": self.escopo,
            "tipo": tipo,
            "mensagem": mensagem,
        }
        for chave, valor in (
            ("etapa", etapa),
            ("rodada_id", rodada_id),
            ("post_id", post_id),
            ("detalhe", detalhe),
            ("duracao_ms", duracao_ms),
            ("custo_usd", custo_usd),
        ):
            if valor is not None:
                evento[chave] = valor
        linha = json.dumps(mascarar(evento), ensure_ascii=False, default=str)
        arquivo = self._arquivo(hoje())
        self.pasta.mkdir(parents=True, exist_ok=True)
        with _lock_para(arquivo), arquivo.open("a", encoding="utf-8") as f:
            f.write(linha + "\n")
        nivel = logging.ERROR if tipo == "erro" else logging.INFO
        _log_python.log(nivel, "[%s] %s: %s", self.escopo, tipo, mascarar_texto(mensagem))

    def erro(
        self,
        mensagem: str,
        exc: BaseException | None = None,
        **kwargs: Any,
    ) -> None:
        """Registra um erro com o traceback inteiro (mascarado)."""
        detalhe: dict[str, Any] = dict(kwargs.pop("detalhe", None) or {})
        if exc is not None:
            detalhe["excecao"] = f"{type(exc).__name__}: {exc}"
            detalhe["traceback"] = "".join(
                traceback.format_exception(type(exc), exc, exc.__traceback__)
            )
        self.registrar("erro", mensagem, detalhe=detalhe, **kwargs)

    def ler_dia(self, dia: date) -> list[dict[str, Any]]:
        arquivo = self._arquivo(dia)
        if not arquivo.exists():
            return []
        eventos = []
        for linha in arquivo.read_text(encoding="utf-8").splitlines():
            if linha.strip():
                eventos.append(json.loads(linha))
        return eventos

    def resumir_dia(self, dia: date) -> ResumoDia:
        eventos = self.ler_dia(dia)
        por_tipo = Counter(str(e.get("tipo")) for e in eventos)
        custo = sum(float(e.get("custo_usd") or 0) for e in eventos)
        return ResumoDia(dia, len(eventos), por_tipo.get("erro", 0), dict(por_tipo), custo)

    def aplicar_retencao(
        self, dias: int, guardar_resumo: Callable[[ResumoDia], None]
    ) -> list[date]:
        """Apaga o detalhe de dias mais antigos que `dias`, guardando antes o resumo.

        O resumo fica para sempre (no banco do perfil ou em resumos.jsonl, no global).
        """
        limite = hoje() - timedelta(days=dias)
        apagados: list[date] = []
        if not self.pasta.exists():
            return apagados
        for arquivo in sorted(self.pasta.glob("*.jsonl")):
            try:
                dia = date.fromisoformat(arquivo.stem)
            except ValueError:
                continue
            if dia < limite:
                guardar_resumo(self.resumir_dia(dia))
                arquivo.unlink()
                apagados.append(dia)
        return apagados


def guardar_resumo_em_arquivo(arquivo: Path) -> Callable[[ResumoDia], None]:
    """Destino de resumos para o registro global (que não tem banco)."""

    def _guardar(r: ResumoDia) -> None:
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        linha = {
            "data": r.data.isoformat(),
            "eventos": r.eventos,
            "erros": r.erros,
            "por_tipo": r.por_tipo,
            "custo_usd": r.custo_usd,
            "criado_em": agora().isoformat(timespec="seconds"),
        }
        with arquivo.open("a", encoding="utf-8") as f:
            f.write(json.dumps(linha, ensure_ascii=False) + "\n")

    return _guardar


def registro_global(dados: Path) -> Registro:
    return Registro(dados / "logs", "global")
