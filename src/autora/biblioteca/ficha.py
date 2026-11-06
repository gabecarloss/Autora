"""Ficha dos clipes disponíveis para uma rodada (versão mínima da indexação, seção 4).

Lê as pastas do perfil, sonda cada vídeo com ffprobe, transcreve o que tem áudio e
guarda tudo na tabela `video` (origem 'pasta', apelido + caminho relativo: nada de
caminho absoluto no perfil). Clipes já usados (`post_video`) nunca voltam.

PROVISÓRIO até o passo 3: descrição manual opcional em `descricoes.json` na pasta
(`{"arquivo.mp4": "texto"}`) no lugar da análise por IA; `LIMITE_CANDIDATOS` fixo.
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Final

from autora.config import maquina
from autora.edicao.ffmpeg import ErroFfmpeg, inspecionar
from autora.perfil.perfil import Perfil
from autora.util.arquivos import resolver_dentro
from autora.util.tempo import agora_iso

EXTENSOES: Final = frozenset({".mp4", ".mov", ".mkv", ".webm"})
LIMITE_CANDIDATOS: Final = 8  # PROVISÓRIO
ARQUIVO_DESCRICOES: Final = "descricoes.json"
_NAO_APELIDO = re.compile(r"[^a-z0-9_-]+")

Transcritor = Callable[[Path], str | None]


@dataclass(frozen=True)
class FichaClipe:
    id: int
    referencia: str  # "apelido:caminho/relativo"
    nome_arquivo: str
    duracao_s: float
    largura: int
    altura: int
    orientacao: str
    tem_audio: bool
    transcricao: str | None
    descricao: str | None
    usado_antes: bool

    def para_agente(self) -> dict[str, Any]:
        """Só o que o agente precisa; sem caminho da máquina."""
        d = asdict(self)
        d.pop("referencia")
        return d


def apelido_para(pasta: Path, dados: Path | None = None) -> str:
    base = _NAO_APELIDO.sub("-", pasta.name.lower()).strip("-")[:36] or "pasta"
    if not base[0].isalnum():
        base = "p" + base
    cfg = maquina.carregar(dados)
    resolvida = str(pasta.resolve())
    for apelido, caminho in cfg.pastas.items():
        if caminho == resolvida:
            return apelido
    candidato, n = base, 1
    while candidato in cfg.pastas:
        n += 1
        candidato = f"{base}-{n}"
    return candidato


def registrar_pasta(perfil: Perfil, dados: Path, pasta: Path) -> str:
    """Apelido + caminho absoluto em maquina.json; só o apelido no perfil."""
    if not pasta.is_dir():
        raise FileNotFoundError(f"A pasta {pasta} não existe.")
    apelido = apelido_para(pasta, dados)
    maquina.definir_apelido(apelido, pasta, dados)
    if apelido not in perfil.config.conteudo.pastas:
        perfil.config.conteudo.pastas = [*perfil.config.conteudo.pastas, apelido]
        perfil.salvar_config()
        perfil.registro.registrar(
            "usuario",
            f"Pasta de vídeos “{pasta.name}” vinculada ao perfil.",
            detalhe={"apelido": apelido},
        )
    return apelido


def ler_descricoes(pasta: Path) -> dict[str, str]:
    arquivo = pasta / ARQUIVO_DESCRICOES
    if not arquivo.is_file():
        return {}
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {str(k): str(v) for k, v in dados.items()} if isinstance(dados, dict) else {}


def _arquivos_de_video(pasta: Path) -> list[Path]:
    return sorted(p for p in pasta.rglob("*") if p.is_file() and p.suffix.lower() in EXTENSOES)


def _garantir_linha(con: sqlite3.Connection, apelido: str, relativo: str) -> int:
    con.execute(
        "INSERT OR IGNORE INTO video (origem, apelido_pasta, caminho_relativo) "
        "VALUES ('pasta', ?, ?)",
        (apelido, relativo),
    )
    linha = con.execute(
        "SELECT id FROM video WHERE apelido_pasta = ? AND caminho_relativo = ?", (apelido, relativo)
    ).fetchone()
    return int(linha[0])


def _sondar_e_gravar(
    con: sqlite3.Connection,
    video_id: int,
    caminho: Path,
    descricao: str | None,
    transcrever: Transcritor | None,
    ffprobe: Path | None,
) -> None:
    try:
        info = inspecionar(caminho, ffprobe)
    except ErroFfmpeg as e:
        con.execute(
            "UPDATE video SET falha_indexacao = ?, indexado_em = ? WHERE id = ?",
            (str(e)[:500], agora_iso(), video_id),
        )
        return
    transcricao: str | None = None
    if info.tem_audio and transcrever is not None:
        try:
            transcricao = transcrever(caminho)
        except Exception:
            transcricao = None
    con.execute(
        """UPDATE video SET duracao_s = ?, largura = ?, altura = ?, orientacao = ?, tem_audio = ?,
                 transcricao = ?, analise_json = ?, indexado_em = ?, falha_indexacao = NULL
           WHERE id = ?""",
        (
            info.duracao_s,
            info.largura,
            info.altura,
            info.orientacao,
            1 if info.tem_audio else 0,
            transcricao,
            json.dumps({"descricao_manual": descricao}, ensure_ascii=False) if descricao else None,
            agora_iso(),
            video_id,
        ),
    )


def fichas_disponiveis(
    perfil: Perfil,
    dados: Path,
    con: sqlite3.Connection,
    *,
    limite: int = LIMITE_CANDIDATOS,
    transcrever: Transcritor | None = None,
    ffprobe: Path | None = None,
) -> list[FichaClipe]:
    """Clipes não usados das pastas do perfil, sondados (e transcritos) sob demanda."""
    cfg_maquina = maquina.carregar(dados)
    usados = {int(r[0]) for r in con.execute("SELECT DISTINCT video_id FROM post_video")}
    candidatos: list[tuple[int, Path, str | None]] = []
    for apelido in perfil.config.conteudo.pastas:
        if apelido not in cfg_maquina.pastas:
            perfil.registro.registrar(
                "erro",
                f"A pasta “{apelido}” não está apontada nesta máquina; ela foi ignorada.",
                detalhe={"apelido": apelido},
            )
            continue
        raiz = Path(cfg_maquina.pastas[apelido])
        descricoes = ler_descricoes(raiz)
        for arquivo in _arquivos_de_video(raiz):
            relativo = arquivo.relative_to(raiz).as_posix()
            video_id = _garantir_linha(con, apelido, relativo)
            if video_id in usados:
                continue
            candidatos.append(
                (video_id, arquivo, descricoes.get(relativo) or descricoes.get(arquivo.name))
            )
            if len(candidatos) >= limite:
                break
        if len(candidatos) >= limite:
            break

    fichas: list[FichaClipe] = []
    for video_id, arquivo, descricao in candidatos:
        linha = con.execute("SELECT * FROM video WHERE id = ?", (video_id,)).fetchone()
        if linha["indexado_em"] is None or (descricao and not linha["analise_json"]):
            _sondar_e_gravar(con, video_id, arquivo, descricao, transcrever, ffprobe)
            linha = con.execute("SELECT * FROM video WHERE id = ?", (video_id,)).fetchone()
        if linha["falha_indexacao"]:
            continue
        analise = json.loads(linha["analise_json"]) if linha["analise_json"] else {}
        fichas.append(
            FichaClipe(
                id=video_id,
                referencia=f"{linha['apelido_pasta']}:{linha['caminho_relativo']}",
                nome_arquivo=arquivo.name,
                duracao_s=float(linha["duracao_s"]),
                largura=int(linha["largura"]),
                altura=int(linha["altura"]),
                orientacao=str(linha["orientacao"]),
                tem_audio=bool(linha["tem_audio"]),
                transcricao=linha["transcricao"] or None,
                descricao=descricao or analise.get("descricao_manual"),
                usado_antes=False,
            )
        )
    return fichas


def caminhos_dos_clipes(fichas: Sequence[FichaClipe], dados: Path) -> dict[int, Path]:
    """Resolve as referências portáteis nos caminhos desta máquina (confinados à pasta)."""
    cfg = maquina.carregar(dados)
    saida: dict[int, Path] = {}
    for f in fichas:
        apelido, _, relativo = f.referencia.partition(":")
        saida[f.id] = resolver_dentro(Path(cfg.pastas[apelido]), relativo)
    return saida
