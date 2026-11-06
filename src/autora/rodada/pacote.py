"""Pacote de publicação (seção 2): pasta saida/<perfil>/<data>/<n>/ com video.mp4,
post.md, capa.jpg e roteiro.json (ideia + roteiro, para depuração e Bastidores)."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path

from autora.config import maquina
from autora.edicao.plano import PlanoEdicao
from autora.edicao.renderizador import Entrega
from autora.perfil.perfil import Perfil
from autora.plataformas.base import PacotePost, Plataforma
from autora.rodada.esquemas import Conceito
from autora.util.tempo import agora_iso, hoje


def nova_pasta_do_post(dados: Path, slug: str) -> tuple[Path, str]:
    """Cria saida/<slug>/<AAAA-MM-DD>/<n>/ e devolve (pasta, "<AAAA-MM-DD>/<n>")."""
    raiz = maquina.pasta_saida(slug, dados) / hoje().isoformat()
    raiz.mkdir(parents=True, exist_ok=True)
    n = 1
    while (raiz / str(n)).exists():
        n += 1
    pasta = raiz / str(n)
    pasta.mkdir()
    return pasta, f"{hoje().isoformat()}/{n}"


def montar_pacote_post(
    perfil: Perfil, conceito: Conceito, plano: PlanoEdicao, entrega: Entrega
) -> PacotePost:
    motivos = {
        "formato": conceito.formato.motivo,
        "clipes": "; ".join(f"clipe {c.clipe_id}: {c.motivo}" for c in conceito.clipes_escolhidos),
        "gancho": conceito.gancho.motivo,
        "horário": conceito.horario_sugerido.motivo,
        "capa": conceito.capa.motivo,
        "ritmo": plano.motivos.ritmo,
        "enquadramento": plano.motivos.enquadramento,
        "textos": plano.motivos.textos,
        "legendas": plano.motivos.legendas,
    }
    if conceito.som is not None:
        motivos["som"] = conceito.som.motivo
    formato = conceito.formato.valor
    if conceito.descricao_formato:
        formato += f" ({conceito.descricao_formato})"
    return PacotePost(
        gancho=conceito.gancho.valor,
        alternativas_gancho=list(conceito.alternativas_gancho),
        descricao=conceito.descricao_post,
        hashtags=list(conceito.hashtags),
        horario_sugerido=conceito.horario_sugerido.valor,
        motivo_horario=conceito.horario_sugerido.motivo,
        capa_texto=plano.capa.texto,
        capa_segundo=plano.capa.segundo,
        formato=formato,
        fonte_material=conceito.fonte_material,
        voz=None,
        versao_estilo=plano.versao_estilo,
        motivos=motivos,
        som=conceito.som.model_dump() if conceito.som is not None else None,
        tema=conceito.tema,
        conceito=conceito.conceito,
        duracao_s=entrega.duracao_s,
        legendas=entrega.legendas,
        elementos_autorais=[
            {"tipo": e.tipo, "descricao": e.descricao} for e in conceito.elementos_autorais
        ],
        referencia=None,
        nao_sei=list(conceito.nao_sei),
        confianca=conceito.confianca,
        avisos=list(entrega.avisos),
        nome_perfil=perfil.config.identidade.nome,
        criado_em=agora_iso(),
    )


def escrever_pacote(
    pasta: Path,
    perfil: Perfil,
    plataforma: Plataforma,
    conceito: Conceito,
    plano: PlanoEdicao,
    entrega: Entrega,
) -> PacotePost:
    pacote = montar_pacote_post(perfil, conceito, plano, entrega)
    (pasta / "post.md").write_text(plataforma.gerar_post_md(pacote), encoding="utf-8")
    roteiro = {
        "ideia": conceito.model_dump(mode="json"),
        "roteiro": plano.model_dump(mode="json"),
        "entrega": {
            "duracao_s": entrega.duracao_s,
            "legendas": entrega.legendas,
            "avisos": entrega.avisos,
            "transcricao": [asdict(p) for p in entrega.transcricao.palavras]
            if entrega.transcricao
            else None,
        },
    }
    (pasta / "roteiro.json").write_text(
        json.dumps(roteiro, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return pacote


def gravar_post_pronto(
    con: sqlite3.Connection,
    post_id: int,
    conceito: Conceito,
    plano: PlanoEdicao,
    entrega: Entrega,
    pasta_relativa: str,
) -> None:
    con.execute(
        """UPDATE post SET estado = 'aguardando_revisao', formato = ?, fonte_material = ?, tema = ?,
                 gancho = ?, duracao_s = ?, som_json = ?, voz = NULL, horario_sugerido = ?,
                 pasta_saida = ?
           WHERE id = ?""",
        (
            conceito.formato.valor,
            conceito.fonte_material,
            conceito.tema,
            conceito.gancho.valor,
            entrega.duracao_s,
            conceito.som.model_dump_json() if conceito.som is not None else None,
            conceito.horario_sugerido.valor,
            pasta_relativa,
            post_id,
        ),
    )
    vistos: set[tuple[int, float]] = set()
    for t in plano.trechos:
        chave = (t.clipe_id, t.inicio_s)
        if chave in vistos:
            continue
        vistos.add(chave)
        con.execute(
            "INSERT INTO post_video (post_id, video_id, trecho_inicio_s, trecho_fim_s)"
            " VALUES (?, ?, ?, ?)",
            (post_id, t.clipe_id, t.inicio_s, t.fim_s),
        )
