"""Exportar e importar um perfil inteiro (seção 9.3, aba Avançado).

Exportar: zip da pasta do perfil com o banco copiado de forma consistente, mais um
manifesto com os apelidos de pasta usados. Antes de gerar, confere que nenhum
segredo conhecido aparece em nenhum arquivo de texto (nunca deveria).

Importar: valida cada entrada do zip (sem caminho absoluto, sem '..', limites de
tamanho contra zip bomb), valida o config.json pelo esquema, e só então move para
perfis/<slug>. Devolve os apelidos que ainda precisam ser apontados nesta máquina.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Final

from autora import __version__
from autora.backup.backup import copiar_banco
from autora.config import maquina, segredos
from autora.perfil.esquema import ConfigPerfil
from autora.perfil.perfil import NOME_TRAVA, Perfil, PerfilJaExiste, pasta_perfis
from autora.util.arquivos import CaminhoForaDaRaiz, caminho_relativo_seguro
from autora.util.tempo import agora_iso

LIMITE_TOTAL_BYTES: Final = 50 * 1024**3
LIMITE_ENTRADAS: Final = 500_000
LIMITE_TAXA_COMPRESSAO: Final = 200
_IGNORAR: Final = {NOME_TRAVA, "autora.db", "autora.db-wal", "autora.db-shm"}
_EXTENSOES_TEXTO: Final = {".json", ".jsonl", ".md", ".txt", ".csv"}


class ExportacaoBloqueada(RuntimeError):
    pass


class ImportacaoInvalida(ValueError):
    pass


def exportar(perfil: Perfil, destino: Path) -> Path:
    arquivos = [a for a in sorted(perfil.raiz.rglob("*")) if a.is_file() and a.name not in _IGNORAR]
    # Varredura ANTES de escrever qualquer coisa: se um segredo aparecer, nada é gerado.
    valores = segredos.valores_conhecidos()
    if valores:
        for arq in arquivos:
            if arq.suffix in _EXTENSOES_TEXTO:
                conteudo = arq.read_text(encoding="utf-8", errors="ignore")
                if any(v in conteudo for v in valores):
                    raise ExportacaoBloqueada(
                        f"Um segredo apareceu em {arq.name}. A exportação foi cancelada."
                    )
    tmp_zip = destino.with_suffix(destino.suffix + ".tmp")
    with tempfile.TemporaryDirectory() as tmp:
        db_copia = Path(tmp) / "autora.db"
        copiar_banco(perfil.caminho_db, db_copia)
        manifesto = {
            "app": "autora",
            "versao_app": __version__,
            "exportado_em": agora_iso(),
            "slug": perfil.slug,
            "apelidos_pastas": perfil.config.conteudo.pastas,
        }
        with zipfile.ZipFile(tmp_zip, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("manifesto.json", json.dumps(manifesto, ensure_ascii=False, indent=2))
            z.write(db_copia, "autora.db")
            for arq in arquivos:
                z.write(arq, arq.relative_to(perfil.raiz).as_posix())
    tmp_zip.replace(destino)
    perfil.registro.registrar("sistema", "Perfil exportado.", detalhe={"arquivo": destino.name})
    return destino


def _validar_entradas(z: zipfile.ZipFile) -> None:
    infos = z.infolist()
    if len(infos) > LIMITE_ENTRADAS:
        raise ImportacaoInvalida("o arquivo tem entradas demais")
    total = 0
    for info in infos:
        try:
            caminho_relativo_seguro(info.filename.rstrip("/"))
        except CaminhoForaDaRaiz as e:
            raise ImportacaoInvalida(f"entrada perigosa no arquivo: {info.filename!r}") from e
        total += info.file_size
        if (
            info.compress_size > 0
            and info.file_size > 1024**2
            and info.file_size / info.compress_size > LIMITE_TAXA_COMPRESSAO
        ):
            raise ImportacaoInvalida(f"entrada suspeita (compressão anormal): {info.filename!r}")
    if total > LIMITE_TOTAL_BYTES:
        raise ImportacaoInvalida("o arquivo é grande demais")


def importar(
    arquivo: Path,
    dados: Path,
    *,
    novo_slug: str | None = None,
    mapeamento: dict[str, Path] | None = None,
) -> tuple[Perfil, list[str]]:
    """Importa o perfil. Devolve (perfil, apelidos ainda sem pasta nesta máquina)."""
    with zipfile.ZipFile(arquivo) as z:
        _validar_entradas(z)
        nomes = set(z.namelist())
        if "config.json" not in nomes or "manifesto.json" not in nomes:
            raise ImportacaoInvalida("não é uma exportação de perfil do Autora")
        try:
            config = ConfigPerfil.model_validate_json(z.read("config.json"))
        except ValueError as e:
            raise ImportacaoInvalida("a configuração do perfil no arquivo é inválida") from e
        if novo_slug:
            config = config.model_copy(update={"slug": novo_slug})
            ConfigPerfil.model_validate(config.model_dump())
        destino = pasta_perfis(dados) / config.slug
        if destino.exists():
            raise PerfilJaExiste(config.slug)
        pasta_perfis(dados).mkdir(parents=True, exist_ok=True)
        tmp = Path(tempfile.mkdtemp(prefix=".importando-", dir=pasta_perfis(dados)))
        try:
            for info in z.infolist():
                if info.is_dir() or info.filename == "manifesto.json":
                    continue
                rel = caminho_relativo_seguro(info.filename)
                alvo = tmp.joinpath(*rel.parts)
                alvo.parent.mkdir(parents=True, exist_ok=True)
                with z.open(info) as src, alvo.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
            (tmp / "config.json").write_text(config.model_dump_json(indent=2), encoding="utf-8")
            tmp.rename(destino)
        except BaseException:
            shutil.rmtree(tmp, ignore_errors=True)
            raise

    for apelido, pasta in (mapeamento or {}).items():
        maquina.definir_apelido(apelido, pasta, dados)
    conhecidos = maquina.carregar(dados).pastas
    pendentes = [a for a in config.conteudo.pastas if a not in conhecidos]

    perfil = Perfil.abrir(dados, config.slug)
    with perfil.conectar():
        pass  # aplica migrações novas, se o perfil veio de versão anterior
    perfil.registro.registrar(
        "sistema",
        "Perfil importado.",
        detalhe={"arquivo": arquivo.name, "pastas_pendentes": pendentes},
    )
    return perfil, pendentes
