"""Operações de arquivo seguras: gravação atômica e resolução de caminhos confinados."""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path, PurePosixPath, PureWindowsPath


class CaminhoForaDaRaiz(ValueError):
    """Um caminho relativo tentou sair da pasta permitida."""


def gravar_atomico(destino: Path, conteudo: str | bytes) -> None:
    """Grava num arquivo temporário na mesma pasta e troca de uma vez.

    Um corte de energia no meio deixa o arquivo antigo intacto, nunca meio escrito.
    """
    destino.parent.mkdir(parents=True, exist_ok=True)
    dados = conteudo.encode("utf-8") if isinstance(conteudo, str) else conteudo
    fd, tmp = tempfile.mkstemp(dir=destino.parent, prefix=f".{destino.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(dados)
            f.flush()
            os.fsync(f.fileno())
        Path(tmp).replace(destino)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


_UNIDADE_WINDOWS = re.compile(r"^[A-Za-z]:")


def eh_caminho_absoluto(texto: str) -> bool:
    """Detecta caminhos absolutos de qualquer sistema (C:\\, \\\\servidor, /home...)."""
    if not texto:
        return False
    if _UNIDADE_WINDOWS.match(texto):
        return True
    if texto.startswith(("\\\\", "//")):
        return True
    return PurePosixPath(texto).is_absolute() or PureWindowsPath(texto).is_absolute()


def caminho_relativo_seguro(texto: str) -> PurePosixPath:
    """Valida um caminho relativo: sem raiz, sem unidade, sem '..'. Usa '/' sempre."""
    if not texto or eh_caminho_absoluto(texto):
        raise CaminhoForaDaRaiz(f"caminho precisa ser relativo: {texto!r}")
    partes = PurePosixPath(texto.replace("\\", "/")).parts
    if any(p == ".." for p in partes) or ":" in texto:
        raise CaminhoForaDaRaiz(f"caminho tenta sair da pasta: {texto!r}")
    return PurePosixPath(*partes)


def resolver_dentro(raiz: Path, relativo: str) -> Path:
    """Junta raiz + relativo e garante que o resultado continua dentro da raiz."""
    rel = caminho_relativo_seguro(relativo)
    raiz_res = raiz.resolve()
    alvo = (raiz_res / Path(*rel.parts)).resolve()
    if not alvo.is_relative_to(raiz_res):
        raise CaminhoForaDaRaiz(f"caminho tenta sair da pasta: {relativo!r}")
    return alvo
