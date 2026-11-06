"""Fichas dos clipes da biblioteca: registro da pasta, sondagem, uso e portabilidade."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import pytest

from autora.biblioteca.ficha import (
    LIMITE_CANDIDATOS,
    apelido_para,
    caminhos_dos_clipes,
    fichas_disponiveis,
    ler_descricoes,
    registrar_pasta,
)
from autora.perfil.perfil import Perfil
from tests.auxiliar_banco import abrir


def _fichas(perfil: Perfil, dados: Path, **kw: object):  # type: ignore[no-untyped-def]
    con = abrir(perfil)
    try:
        return fichas_disponiveis(perfil, dados, con, **kw)  # type: ignore[arg-type]
    finally:
        con.close()


def _por_nome(fichas):  # type: ignore[no-untyped-def]
    return {f.nome_arquivo: f for f in fichas}


def test_tres_fichas_com_duracao_orientacao_audio_e_descricao(
    perfil_com_clipes_falsos: Perfil, dados: Path
) -> None:
    f = _por_nome(_fichas(perfil_com_clipes_falsos, dados))
    assert set(f) == {"a.mp4", "b.mp4", "c.mp4"}
    assert (f["a.mp4"].duracao_s, f["a.mp4"].orientacao, f["a.mp4"].tem_audio) == (
        3.0,
        "vertical",
        True,
    )
    assert (f["b.mp4"].duracao_s, f["b.mp4"].orientacao, f["b.mp4"].tem_audio) == (
        4.0,
        "horizontal",
        True,
    )
    assert (f["c.mp4"].duracao_s, f["c.mp4"].orientacao, f["c.mp4"].tem_audio) == (
        2.0,
        "vertical",
        False,
    )
    assert [f[n].descricao for n in ("a.mp4", "b.mp4", "c.mp4")] == ["Cena A", "Cena B", "Cena C"]


def test_ficha_para_o_agente_nao_traz_referencia(
    perfil_com_clipes_falsos: Perfil, dados: Path, tmp_path: Path
) -> None:
    ficha = _fichas(perfil_com_clipes_falsos, dados)[0]
    d = ficha.para_agente()
    assert "referencia" not in d
    assert str(tmp_path) not in json.dumps(d, ensure_ascii=False)


def test_config_do_perfil_guarda_so_o_apelido_e_a_maquina_guarda_o_caminho(
    perfil_com_clipes_falsos: Perfil, dados: Path, tmp_path: Path
) -> None:
    pasta = tmp_path / "biblioteca_falsa"
    config = perfil_com_clipes_falsos.caminho_config.read_text(encoding="utf-8")
    assert str(pasta) not in config
    assert str(pasta).replace("\\", "\\\\") not in config
    assert apelido_para(pasta, dados) in config
    maquina = (dados / "maquina.json").read_text(encoding="utf-8")
    assert json.dumps(str(pasta))[1:-1] in maquina


def test_segunda_chamada_nao_duplica_videos(perfil_com_clipes_falsos: Perfil, dados: Path) -> None:
    perfil = perfil_com_clipes_falsos
    _fichas(perfil, dados)
    _fichas(perfil, dados)
    con = abrir(perfil)
    try:
        assert con.execute("SELECT COUNT(*) FROM video").fetchone()[0] == 3
    finally:
        con.close()


def test_clipe_usado_em_post_nao_volta(perfil_com_clipes_falsos: Perfil, dados: Path) -> None:
    perfil = perfil_com_clipes_falsos
    id_a = _por_nome(_fichas(perfil, dados))["a.mp4"].id
    con = abrir(perfil)
    try:
        con.execute(
            "INSERT INTO post (criado_em, estado) VALUES (?, 'aprovado')",
            (datetime.now().isoformat(),),
        )
        post_id = con.execute("SELECT id FROM post").fetchone()[0]
        con.execute(
            "INSERT INTO post_video (post_id, video_id, trecho_inicio_s, trecho_fim_s) "
            "VALUES (?, ?, 0, 3)",
            (post_id, id_a),
        )
        con.commit()
    finally:
        con.close()
    assert set(_por_nome(_fichas(perfil, dados))) == {"b.mp4", "c.mp4"}


def test_limite_restringe_a_quantidade(perfil_com_clipes_falsos: Perfil, dados: Path) -> None:
    assert len(_fichas(perfil_com_clipes_falsos, dados, limite=1)) == 1
    assert LIMITE_CANDIDATOS >= 3


def test_transcricao_so_para_clipes_com_audio_e_fica_gravada(
    perfil_com_clipes_falsos: Perfil, dados: Path
) -> None:
    chamadas: list[str] = []

    def transcrever(caminho: Path) -> str:
        chamadas.append(Path(caminho).name)
        return "fala de teste"

    perfil = perfil_com_clipes_falsos
    f = _por_nome(_fichas(perfil, dados, transcrever=transcrever))
    assert sorted(chamadas) == ["a.mp4", "b.mp4"]
    assert f["a.mp4"].transcricao == "fala de teste"
    assert f["c.mp4"].transcricao is None
    con = abrir(perfil)
    try:
        linhas = con.execute(
            "SELECT caminho_relativo, transcricao FROM video WHERE transcricao IS NOT NULL"
        ).fetchall()
    finally:
        con.close()
    assert len(linhas) == 2
    assert all(linha[1] == "fala de teste" for linha in linhas)


def test_caminhos_dos_clipes_existem_dentro_da_pasta(
    perfil_com_clipes_falsos: Perfil, dados: Path, tmp_path: Path
) -> None:
    fichas = _fichas(perfil_com_clipes_falsos, dados)
    caminhos = caminhos_dos_clipes(fichas, dados)
    assert set(caminhos) == {f.id for f in fichas}
    pasta = (tmp_path / "biblioteca_falsa").resolve()
    for c in caminhos.values():
        assert c.exists()
        assert pasta in c.resolve().parents


def test_registrar_pasta_inexistente_levanta_erro(dados: Path, tmp_path: Path) -> None:
    perfil = Perfil.criar(dados, "outro", "Outro")
    with pytest.raises(FileNotFoundError):
        registrar_pasta(perfil, dados, tmp_path / "nao_existe")


def test_apelido_so_tem_letras_minusculas_numeros_hifen_e_sublinhado(
    dados: Path, tmp_path: Path
) -> None:
    apelido = apelido_para(tmp_path / "Meus Vídeos", dados)
    assert apelido
    assert re.fullmatch(r"[a-z0-9_-]+", apelido)


def test_ler_descricoes_le_o_arquivo_da_pasta(tmp_path: Path) -> None:
    (tmp_path / "descricoes.json").write_text(json.dumps({"x.mp4": "Cena X"}), encoding="utf-8")
    assert ler_descricoes(tmp_path) == {"x.mp4": "Cena X"}
    assert ler_descricoes(tmp_path / "vazia") == {}


def test_transcricao_que_falha_nao_derruba_a_ficha(
    perfil_com_clipes_falsos: Perfil, dados: Path
) -> None:
    def quebrado(caminho: Path) -> str | None:
        raise RuntimeError("serviço de legenda fora do ar")

    with perfil_com_clipes_falsos.conectar() as con:
        fichas = fichas_disponiveis(perfil_com_clipes_falsos, dados, con, transcrever=quebrado)
    assert len(fichas) == 3
    assert all(f.transcricao is None for f in fichas)
