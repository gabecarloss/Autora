"""Cópia de segurança automática dos perfis (seção 15.6).

Diária, ligada por padrão, com retenção configurável. Guarda o banco (cópia
consistente pela API de backup do SQLite, mesmo com o banco aberto), o config.json
e os arquivos de memória com o histórico. Nunca guarda segredos (eles não ficam no
perfil).

Destino: <dados>/backups/<slug>/AAAA-MM-DD.zip
"""

from __future__ import annotations

import sqlite3
import tempfile
import zipfile
from datetime import date, timedelta
from pathlib import Path

from autora.config import global_config
from autora.perfil.perfil import Perfil, listar
from autora.registro.log import registro_global
from autora.util.tempo import agora, hoje


def pasta_backups(dados: Path, slug: str) -> Path:
    return dados / "backups" / slug


def copiar_banco(origem: Path, destino: Path) -> None:
    """Cópia consistente do banco, mesmo se outro processo estiver escrevendo."""
    src = sqlite3.connect(origem)
    dst = sqlite3.connect(destino)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def _data_do_arquivo(arquivo: Path) -> date | None:
    try:
        return date.fromisoformat(arquivo.stem[:10])
    except ValueError:
        return None


def fazer_backup(perfil: Perfil, dados: Path, *, forcar: bool = False) -> Path | None:
    """Faz o backup do dia. Sem `forcar`, não repete se já houver um de hoje."""
    pasta = pasta_backups(dados, perfil.slug)
    pasta.mkdir(parents=True, exist_ok=True)
    dia = hoje()
    existentes = [a for a in pasta.glob("*.zip") if _data_do_arquivo(a) == dia]
    if existentes and not forcar:
        return None
    nome = f"{dia.isoformat()}.zip" if not existentes else f"{agora():%Y-%m-%d_%H%M%S}.zip"
    destino = pasta / nome
    tmp_zip = destino.with_suffix(".zip.tmp")
    with tempfile.TemporaryDirectory() as tmp:
        db_copia = Path(tmp) / "autora.db"
        if perfil.caminho_db.exists():
            copiar_banco(perfil.caminho_db, db_copia)
        with zipfile.ZipFile(tmp_zip, "w", compression=zipfile.ZIP_DEFLATED) as z:
            if db_copia.exists():
                z.write(db_copia, "autora.db")
            z.write(perfil.caminho_config, "config.json")
            pasta_mem = perfil.memoria.pasta
            for arq in sorted(pasta_mem.rglob("*")):
                if arq.is_file():
                    z.write(arq, (Path("memoria") / arq.relative_to(pasta_mem)).as_posix())
    tmp_zip.replace(destino)
    perfil.registro.registrar(
        "sistema",
        "Cópia de segurança feita.",
        detalhe={"arquivo": destino.name, "bytes": destino.stat().st_size},
    )
    return destino


def aplicar_retencao(dados: Path, slug: str, dias: int) -> list[Path]:
    """Apaga backups mais antigos que `dias`. Nunca apaga o mais recente."""
    pasta = pasta_backups(dados, slug)
    if not pasta.exists():
        return []
    limite = hoje() - timedelta(days=dias)
    arquivos = sorted(pasta.glob("*.zip"))
    apagados = []
    for arq in arquivos[:-1]:
        d = _data_do_arquivo(arq)
        if d is not None and d < limite:
            arq.unlink()
            apagados.append(arq)
    return apagados


def backup_diario(dados: Path) -> dict[str, str]:
    """Roda na primeira ação do dia (abrir o app, CLI) e pelo agendador.

    Falha num perfil não impede os outros. Devolve o resultado por perfil.
    """
    cfg = global_config.carregar(dados)
    resultado: dict[str, str] = {}
    for slug in listar(dados):
        try:
            perfil = Perfil.abrir(dados, slug)
            feito = fazer_backup(perfil, dados)
            aplicar_retencao(dados, slug, cfg.retencao_backups_dias)
            resultado[slug] = "feito" if feito else "já havia de hoje"
        except Exception as e:
            resultado[slug] = "falhou"
            registro_global(dados).erro(
                f"A cópia de segurança do perfil {slug} falhou.", e, detalhe={"slug": slug}
            )
    return resultado
