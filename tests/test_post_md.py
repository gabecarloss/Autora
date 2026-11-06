"""post.md do TikTok: conteúdo obrigatório, seção de som e snapshot."""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

from autora.plataformas.base import PacotePost
from autora.plataformas.tiktok import TikTok
from autora.plataformas.tiktok.post_md import gerar_post_md

ESPERADO = Path(__file__).parent / "esperado" / "post_md_exemplo.md"


def _pacote() -> PacotePost:
    return PacotePost(
        gancho="ele jurou que dava certo",
        alternativas_gancho=["o plano era perfeito", "ninguém avisou ele"],
        descricao="quando a confiança é maior que o plano",
        hashtags=["#humor", "#deucerto", "#expectativa"],
        horario_sugerido="19:30",
        motivo_horario="Pico de audiência de humor no começo da noite.",
        capa_texto="DEU CERTO?",
        capa_segundo=1.0,
        formato="texto_narrativo",
        fonte_material="pasta",
        voz=None,
        versao_estilo=1,
        motivos={
            "ritmo": "Trecho repetido acelerado para fechar a piada.",
            "textos": "Contexto no topo e narrativa no centro.",
        },
        som=None,
        tema="expectativa quebrada",
        conceito="Um texto cria uma expectativa séria e o clipe a derruba no corte final.",
        duracao_s=4.5,
        legendas="sem_fala",
        elementos_autorais=[
            {
                "tipo": "narrativa_propria",
                "descricao": "Dois textos montam uma história.",
                "como_verificar": "Dois textos de papel narrativa.",
            },
            {
                "tipo": "ritmo_proprio",
                "descricao": "Corte seco com aceleração.",
                "como_verificar": "Trecho com velocidade diferente de 1.",
            },
        ],
        nao_sei=["Não sei qual som está em alta esta semana."],
        confianca="media",
        avisos=["Aviso de teste: o clipe b tem proporção horizontal."],
        nome_perfil="Humor",
        criado_em="2026-11-06 10:00",
    )


def test_plataforma_tiktok_declara_o_formato_do_video() -> None:
    t = TikTok()
    assert t.nome == "tiktok"
    assert t.nome_amigavel == "TikTok"
    v = t.video
    assert (v.largura, v.altura, v.fps, v.codec, v.musica_embutida) == (
        1080,
        1920,
        30,
        "h264",
        False,
    )
    assert t.gerar_post_md(_pacote()) == gerar_post_md(_pacote())


def test_post_md_traz_todas_as_informacoes_do_pacote() -> None:
    p = _pacote()
    md = gerar_post_md(p)
    baixo = md.lower()
    for trecho in (
        p.gancho,
        *p.alternativas_gancho,
        p.descricao,
        *p.hashtags,
        p.horario_sugerido,
        p.motivo_horario,
        p.capa_texto,
        p.formato,
        p.nao_sei[0],
        p.avisos[0],
        p.elementos_autorais[0]["descricao"],
        p.motivos["ritmo"],
        p.motivos["textos"],
    ):
        assert trecho in md, trecho
    assert "não está embutida" in baixo or "não embutida" in baixo or "não vem embutida" in baixo
    assert "sem sincronia" in baixo
    assert "sem narração" in baixo
    assert "fala" in baixo  # legendas "sem_fala" explicadas em palavras
    assert "sem_fala" not in md


def test_post_md_sem_som_diz_que_o_usuario_escolhe_no_app() -> None:
    md = gerar_post_md(_pacote()).lower()
    assert "escolha" in md and "app" in md


def test_post_md_com_som_mostra_nome_e_fonte() -> None:
    som: dict[str, object] = {"nome": "Faixa X", "fonte": "TikTok, 06/11/2026"}
    md = gerar_post_md(replace(_pacote(), som=som))
    assert "Faixa X" in md
    assert "TikTok, 06/11/2026" in md


def test_post_md_nao_fala_de_custo_e_tem_formatacao_limpa() -> None:
    md = gerar_post_md(_pacote())
    assert "custo" not in md.lower()
    assert md.endswith("\n") and not md.endswith("\n\n")
    assert "\n\n\n" not in md


def test_post_md_corresponde_ao_exemplo_guardado() -> None:
    md = gerar_post_md(_pacote())
    if os.environ.get("AUTORA_ATUALIZAR_SNAPSHOT") == "1" or not ESPERADO.exists():
        ESPERADO.parent.mkdir(exist_ok=True)
        ESPERADO.write_text(md, encoding="utf-8", newline="\n")
    assert ESPERADO.read_text(encoding="utf-8") == md
