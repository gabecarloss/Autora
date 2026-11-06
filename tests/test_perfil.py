from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from autora.db.conexao import abrir, migrar, versao
from autora.perfil.esquema import ConfigPerfil, Identidade
from autora.perfil.memoria import ARQUIVOS
from autora.perfil.perfil import (
    Perfil,
    PerfilInvalido,
    PerfilJaExiste,
    PerfilOcupado,
    listar,
)
from autora.util.arquivos import eh_caminho_absoluto
from autora.util.tempo import hoje
from tests.conftest import secao_mandato_do_briefing

TABELAS = {
    "rodada",
    "etapa_execucao",
    "post",
    "post_video",
    "decisao",
    "chamada_servico",
    "video",
    "versao_estilo",
    "resumo_dia",
}


def test_criar_perfil_monta_a_pasta_completa(dados: Path) -> None:
    p = Perfil.criar(dados, "humor", "Humor")
    assert p.raiz == dados / "perfis" / "humor"
    assert (p.raiz / "config.json").exists()
    assert (p.raiz / "material").is_dir()
    for nome in ARQUIVOS:
        assert (p.raiz / "memoria" / nome).exists(), nome
    with p.conectar() as con:
        assert versao(con) == 1
        tabelas = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert tabelas >= TABELAS
    eventos = p.registro.ler_dia(hoje())
    assert any(e["tipo"] == "sistema" and "criado" in e["mensagem"] for e in eventos)
    assert listar(dados) == ["humor"]


def test_mandato_e_copia_literal_da_secao_3_1(dados: Path) -> None:
    p = Perfil.criar(dados, "humor", "Humor")
    assert p.memoria.ler("mandato.md") == secao_mandato_do_briefing()


def test_config_do_perfil_nao_tem_caminho_absoluto(dados: Path) -> None:
    p = Perfil.criar(dados, "humor", "Humor")
    conteudo = json.loads((p.raiz / "config.json").read_text(encoding="utf-8"))

    def strings(o: object) -> list[str]:
        if isinstance(o, str):
            return [o]
        if isinstance(o, dict):
            return [s for v in o.values() for s in strings(v)]
        if isinstance(o, list):
            return [s for v in o for s in strings(v)]
        return []

    assert not [s for s in strings(conteudo) if eh_caminho_absoluto(s)]
    assert str(dados) not in (p.raiz / "config.json").read_text(encoding="utf-8")


@pytest.mark.parametrize("caminho", [r"C:\videos", "/home/x", r"\\servidor\pasta", "D:/a"])
def test_esquema_recusa_caminho_absoluto(caminho: str) -> None:
    with pytest.raises(ValidationError):
        ConfigPerfil(
            slug="x",
            criado_em=datetime.now().astimezone(),
            identidade=Identidade(nome=caminho),
        )


def test_slug_invalido_e_duplicado(dados: Path) -> None:
    with pytest.raises(PerfilInvalido):
        Perfil.criar(dados, "Humor Ruim", "x")
    with pytest.raises(PerfilInvalido):
        Perfil.criar(dados, "../fora", "x")
    Perfil.criar(dados, "humor", "Humor")
    with pytest.raises(PerfilJaExiste):
        Perfil.criar(dados, "humor", "Humor")


def test_config_corrompido_gera_erro_claro(dados: Path) -> None:
    p = Perfil.criar(dados, "humor", "Humor")
    p.caminho_config.write_text("{ isso não é json", encoding="utf-8")
    with pytest.raises(PerfilInvalido, match="problema"):
        Perfil.abrir(dados, "humor")


def test_trava_impede_duas_rodadas_simultaneas(dados: Path) -> None:
    p1 = Perfil.criar(dados, "humor", "Humor")
    p2 = Perfil.abrir(dados, "humor")
    with p1.trava(), pytest.raises(PerfilOcupado), p2.trava():
        pass
    with p2.trava():  # liberada depois
        pass


def test_memoria_guarda_historico(dados: Path) -> None:
    p = Perfil.criar(dados, "humor", "Humor")
    original = p.memoria.ler("aprendizados.md")
    assert p.memoria.gravar("aprendizados.md", "v2") is not None
    assert p.memoria.gravar("aprendizados.md", "v2") is None  # igual: não cria versão
    p.memoria.gravar("aprendizados.md", "v3")
    hist = p.memoria.historico("aprendizados.md")
    assert [h.read_text(encoding="utf-8") for h in hist] == [original, "v2"]
    assert p.memoria.ler("aprendizados.md") == "v3"


def test_historico_nao_perde_versao_no_mesmo_instante(
    dados: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regressão: no Windows, duas gravações podem cair no mesmo tique do relógio.
    A segunda versão não pode sobrescrever a primeira, e a ordem tem de se manter."""
    from autora.perfil import memoria as mod_memoria

    instante = datetime(2026, 11, 6, 12, 0, 0, 123456).astimezone()
    monkeypatch.setattr(mod_memoria, "agora", lambda: instante)
    p = Perfil.criar(dados, "humor", "Humor")
    original = p.memoria.ler("aprendizados.md")
    for texto in ("v2", "v3", "v4"):
        p.memoria.gravar("aprendizados.md", texto)
    hist = p.memoria.historico("aprendizados.md")
    assert [h.read_text(encoding="utf-8") for h in hist] == [original, "v2", "v3"]
    assert [h.name for h in hist] == [
        "2026-11-06T12-00-00-123456.md",
        "2026-11-06T12-00-00-123456_01.md",
        "2026-11-06T12-00-00-123456_02.md",
    ]
    assert p.memoria.ler("aprendizados.md") == "v4"


def test_migracao_e_idempotente(tmp_path: Path) -> None:
    con = abrir(tmp_path / "x.db")
    assert migrar(con) == ["0001_base.sql"]
    assert migrar(con) == []
    con.close()


def test_decisao_sem_motivo_e_recusada(dados: Path) -> None:
    import sqlite3

    p = Perfil.criar(dados, "humor", "Humor")
    with p.conectar() as con, pytest.raises(sqlite3.IntegrityError):
        con.execute(
            "INSERT INTO decisao (campo, escolha, motivo, criada_em) "
            "VALUES ('formato', 'x', '  ', 't')"
        )
