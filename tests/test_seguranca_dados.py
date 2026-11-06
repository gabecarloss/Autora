"""Segredos, logs, caminhos, backup, exportação e importação."""

from __future__ import annotations

import json
import zipfile
from datetime import timedelta
from pathlib import Path

import pytest

from autora.backup.backup import aplicar_retencao, backup_diario, fazer_backup, pasta_backups
from autora.config import global_config, maquina, segredos
from autora.perfil.exportar import ExportacaoBloqueada, ImportacaoInvalida, exportar, importar
from autora.perfil.perfil import Perfil
from autora.registro.log import Registro
from autora.util.arquivos import CaminhoForaDaRaiz, resolver_dentro
from autora.util.tempo import hoje

TOKEN = "sk-ant-oat01-SEGREDO-DE-TESTE-1234567890abcdef"


# --- máscara de segredos ----------------------------------------------------
def test_log_mascara_segredo_do_cofre_e_padroes(tmp_path: Path) -> None:
    segredos.definir("agente_token_assinatura", "valor-guardado-no-cofre-xyz")
    reg = Registro(tmp_path, "t")
    reg.registrar(
        "servico",
        "token valor-guardado-no-cofre-xyz vazou",
        detalhe={
            "lista": ["sk-ant-api03-abcdefghijklmnop"],
            "Authorization": "Bearer abcdefghijklmnopqrstu",
        },
    )
    try:
        raise RuntimeError(f"falhou com {TOKEN}")
    except RuntimeError as e:
        reg.erro("deu erro", e)
    texto = (tmp_path / f"{hoje().isoformat()}.jsonl").read_text(encoding="utf-8")
    assert "valor-guardado-no-cofre-xyz" not in texto
    assert "sk-ant-api03-abcdefghijklmnop" not in texto
    assert TOKEN not in texto
    assert "abcdefghijklmnopqrstu" not in texto
    assert texto.count("***") >= 4
    eventos = [json.loads(linha) for linha in texto.splitlines()]
    assert "traceback" in eventos[1]["detalhe"]


def test_retencao_de_logs_guarda_resumo(tmp_path: Path) -> None:
    reg = Registro(tmp_path, "t")
    antigo = hoje() - timedelta(days=100)
    (tmp_path / f"{antigo.isoformat()}.jsonl").write_text(
        json.dumps({"tipo": "erro", "custo_usd": 0.5})
        + "\n"
        + json.dumps({"tipo": "etapa"})
        + "\n",
        encoding="utf-8",
    )
    reg.registrar("sistema", "hoje")
    resumos = []
    apagados = reg.aplicar_retencao(90, resumos.append)
    assert apagados == [antigo]
    assert resumos[0].eventos == 2 and resumos[0].erros == 1 and resumos[0].custo_usd == 0.5
    assert (tmp_path / f"{hoje().isoformat()}.jsonl").exists()


# --- caminhos ---------------------------------------------------------------
@pytest.mark.parametrize(
    "relativo", ["../fora.mp4", "a/../../fora", r"..\fora", "C:/Windows/x", "/etc/passwd", "a:b"]
)
def test_caminho_fora_da_pasta_e_recusado(tmp_path: Path, relativo: str) -> None:
    with pytest.raises(CaminhoForaDaRaiz):
        resolver_dentro(tmp_path, relativo)


def test_apelido_de_pasta_resolve_so_dentro_dela(dados: Path, tmp_path: Path) -> None:
    bib = tmp_path / "biblioteca"
    (bib / "sub").mkdir(parents=True)
    maquina.definir_apelido("humor1", bib, dados)
    assert maquina.resolver("humor1:sub/v.mp4", dados) == (bib / "sub" / "v.mp4").resolve()
    with pytest.raises(CaminhoForaDaRaiz):
        maquina.resolver("humor1:../segredo.txt", dados)
    with pytest.raises(maquina.ApelidoDesconhecido):
        maquina.resolver("outro:v.mp4", dados)


def test_pasta_de_dados_padrao_e_origem(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem AUTORA_DADOS: Autora dentro da pasta do usuário. Com ela: a pasta indicada."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "usuario")
    monkeypatch.delenv("AUTORA_DADOS", raising=False)
    assert global_config.pasta_dados() == tmp_path / "usuario" / "Autora"
    assert global_config.origem_pasta_dados() == "padrao"
    monkeypatch.setenv("AUTORA_DADOS", str(tmp_path / "mae" / "dados"))
    assert global_config.pasta_dados() == tmp_path / "mae" / "dados"
    assert global_config.origem_pasta_dados() == "variavel"
    monkeypatch.setenv("AUTORA_DADOS", "")
    assert global_config.origem_pasta_dados() == "padrao"


# --- backup -----------------------------------------------------------------
def test_retencao_padrao_de_backups_e_30_dias(dados: Path) -> None:
    """Decisão do usuário (06/11/2026): 30 dias. O backup diário aplica esse padrão."""
    assert global_config.ConfigGlobal().retencao_backups_dias == 30
    p = Perfil.criar(dados, "humor", "Humor")
    de_hoje = fazer_backup(p, dados)
    assert de_hoje is not None
    pasta = pasta_backups(dados, "humor")
    com_31 = pasta / f"{(hoje() - timedelta(days=31)).isoformat()}.zip"
    com_29 = pasta / f"{(hoje() - timedelta(days=29)).isoformat()}.zip"
    for arq in (com_31, com_29):
        arq.write_bytes(de_hoje.read_bytes())
    assert backup_diario(dados) == {"humor": "já havia de hoje"}
    assert not com_31.exists()
    assert com_29.exists() and de_hoje.exists()


def test_backup_diario_nao_duplica_e_respeita_retencao(dados: Path) -> None:
    p = Perfil.criar(dados, "humor", "Humor")
    primeiro = fazer_backup(p, dados)
    assert primeiro is not None and primeiro.name == f"{hoje().isoformat()}.zip"
    with zipfile.ZipFile(primeiro) as z:
        nomes = set(z.namelist())
    assert {"autora.db", "config.json", "memoria/mandato.md"} <= nomes
    assert fazer_backup(p, dados) is None  # mesmo dia
    assert fazer_backup(p, dados, forcar=True) is not None

    pasta = pasta_backups(dados, "humor")
    velho = pasta / f"{(hoje() - timedelta(days=60)).isoformat()}.zip"
    velho.write_bytes(primeiro.read_bytes())
    apagados = aplicar_retencao(dados, "humor", 30)
    assert apagados == [velho]
    assert primeiro.exists()


def test_backup_diario_falha_isolada(dados: Path) -> None:
    Perfil.criar(dados, "bom", "Bom")
    ruim = Perfil.criar(dados, "ruim", "Ruim")
    ruim.caminho_config.write_text("quebrado", encoding="utf-8")
    resultado = backup_diario(dados)
    assert resultado == {"bom": "feito", "ruim": "falhou"}


# --- exportar / importar ----------------------------------------------------
def test_exportar_e_importar_com_remapeamento(dados: Path, tmp_path: Path) -> None:
    p = Perfil.criar(dados, "humor", "Humor")
    p.config.conteudo.pastas = ["humor1"]
    p.salvar_config()
    p.memoria.gravar("aprendizados.md", "aprendi algo")
    arquivo = exportar(p, tmp_path / "humor.zip")

    outro_pc = tmp_path / "outro_pc"
    outro_pc.mkdir()
    importado, pendentes = importar(arquivo, outro_pc)
    assert pendentes == ["humor1"]
    assert importado.memoria.ler("aprendizados.md") == "aprendi algo"
    assert importado.memoria.ler("mandato.md") == p.memoria.ler("mandato.md")

    bib = tmp_path / "bib"
    bib.mkdir()
    _, pendentes2 = importar(arquivo, outro_pc, novo_slug="humor2", mapeamento={"humor1": bib})
    assert pendentes2 == []
    assert maquina.carregar(outro_pc).pastas["humor1"] == str(bib.resolve())


def _zip_malicioso(caminho: Path, entrada: str) -> Path:
    with zipfile.ZipFile(caminho, "w") as z:
        z.writestr("manifesto.json", "{}")
        z.writestr("config.json", "{}")
        z.writestr(entrada, "x")
    return caminho


@pytest.mark.parametrize("entrada", ["../../fora.txt", "/abs.txt", "C:/Windows/x.txt", r"..\x"])
def test_importar_recusa_zip_perigoso(dados: Path, tmp_path: Path, entrada: str) -> None:
    arquivo = _zip_malicioso(tmp_path / "mal.zip", entrada)
    with pytest.raises(ImportacaoInvalida):
        importar(arquivo, dados)
    assert not (tmp_path / "fora.txt").exists()


def test_exportar_bloqueia_se_segredo_aparecer(dados: Path, tmp_path: Path) -> None:
    p = Perfil.criar(dados, "humor", "Humor")
    segredos.definir("agente_chave_api", TOKEN)
    (p.raiz / "memoria" / "publico.md").write_text(f"vazou {TOKEN}", encoding="utf-8")
    with pytest.raises(ExportacaoBloqueada):
        exportar(p, tmp_path / "x.zip")
    assert not (tmp_path / "x.zip").exists()
