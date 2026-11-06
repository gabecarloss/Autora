"""Coerência da configuração do Claude Code (.claude/, .mcp.json, CLAUDE.md).

Substitui a conferência manual: hooks apontam para scripts que existem, subagentes e
skills estão bem formados e listados no CLAUDE.md, e os caminhos citados nas skills e
nos subagentes existem no repositório.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
CLAUDE = RAIZ / ".claude"
AGENTES = sorted((CLAUDE / "agents").glob("*.md"))
SKILLS = sorted(p.parent for p in (CLAUDE / "skills").glob("*/SKILL.md"))
MODELOS = {"haiku", "sonnet", "opus", "inherit"}
SO_LEITURA = {"verificador", "conformidade", "pesquisador-tecnico"}
_CAMINHO_CITADO = re.compile(
    r"`((?:src|tests|frontend|ferramentas|\.claude)/[\w./-]+\.(?:py|md|ts|tsx|sql|json|toml))`"
)


def _frontmatter(arquivo: Path) -> dict[str, str]:
    texto = arquivo.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", texto, re.S)
    assert m, f"{arquivo} sem frontmatter"
    campos: dict[str, str] = {}
    for linha in m.group(1).splitlines():
        chave, _, valor = linha.partition(":")
        campos[chave.strip()] = valor.strip().strip('"')
    return campos


def _settings() -> dict[str, object]:
    return json.loads((CLAUDE / "settings.json").read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def test_ha_subagentes_e_skills() -> None:
    assert AGENTES
    assert SKILLS


@pytest.mark.parametrize("arquivo", AGENTES, ids=lambda p: p.stem)
def test_subagente_bem_formado(arquivo: Path) -> None:
    fm = _frontmatter(arquivo)
    assert fm.get("name") == arquivo.stem
    assert len(fm.get("description", "")) > 40, "descrição precisa dizer quando usar"
    assert fm.get("model") in MODELOS
    ferramentas = {f.strip() for f in fm.get("tools", "").split(",") if f.strip()}
    assert ferramentas, "ferramentas mínimas explícitas"
    if arquivo.stem in SO_LEITURA:
        assert not ferramentas & {"Write", "Edit", "MultiEdit", "NotebookEdit"}


@pytest.mark.parametrize("pasta", SKILLS, ids=lambda p: p.name)
def test_skill_bem_formada(pasta: Path) -> None:
    fm = _frontmatter(pasta / "SKILL.md")
    assert fm.get("name") == pasta.name
    assert len(fm.get("description", "")) > 40, "descrição precisa dizer quando usar"


def test_claude_md_lista_todos_os_subagentes_e_skills() -> None:
    texto = (RAIZ / "CLAUDE.md").read_text(encoding="utf-8")
    for nome in [a.stem for a in AGENTES] + [s.name for s in SKILLS]:
        assert f"`{nome}" in texto or f"/{nome}" in texto, f"{nome} não aparece no CLAUDE.md"


@pytest.mark.parametrize(
    "arquivo",
    [*AGENTES, *(s / "SKILL.md" for s in SKILLS), CLAUDE / "skills/iniciar-passo/bibliotecas.md"],
    ids=lambda p: p.parent.name if p.name == "SKILL.md" else p.stem,
)
def test_caminhos_citados_existem(arquivo: Path) -> None:
    faltando = [
        c
        for c in _CAMINHO_CITADO.findall(arquivo.read_text(encoding="utf-8"))
        if "<" not in c and "*" not in c and not (RAIZ / c).exists()
    ]
    assert not faltando, f"{arquivo.name} cita caminhos que não existem: {faltando}"


def test_hooks_apontam_para_scripts_existentes_e_todos_estao_ligados() -> None:
    hooks = _settings()["hooks"]
    assert isinstance(hooks, dict)
    usados: set[str] = set()
    for grupos in hooks.values():
        for grupo in grupos:
            for hook in grupo["hooks"]:
                assert hook["type"] == "command"
                scripts = re.findall(r"\.claude/hooks/(\w+\.py)", hook["command"])
                assert scripts, hook["command"]
                assert ".venv/Scripts/python.exe" in hook["command"]
                usados.update(scripts)
    existentes = {p.name for p in (CLAUDE / "hooks").glob("*.py") if not p.name.startswith("_")}
    assert usados == existentes


def test_mcp_configurado_e_habilitado() -> None:
    mcp = json.loads((RAIZ / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]
    habilitados = _settings()["enabledMcpjsonServers"]
    assert isinstance(habilitados, list)
    assert set(habilitados) <= set(mcp)
    sqlite = mcp["autora-sqlite"]
    for valor in [sqlite["command"], *sqlite["args"]]:
        caminho = valor.replace("${CLAUDE_PROJECT_DIR:-.}", str(RAIZ))
        assert Path(caminho).exists(), valor
    assert mcp["context7"]["url"].startswith("https://")


def test_permissoes_nao_liberam_alteracao_do_repositorio() -> None:
    permissoes = _settings()["permissions"]
    assert isinstance(permissoes, dict)
    proibidos = re.compile(
        r"\((?:git (?:add|commit|push|pull|merge|rebase|checkout|switch|tag|stash|restore|"
        r"reset|cherry-pick|revert|branch -[dDmMcCf]\b)|gh (?:pr (?:create|merge)|release create|"
        r"repo (?:create|edit|delete)|workflow run))"
    )
    liberados = [r for r in permissoes["allow"] if proibidos.search(r)]
    assert not liberados, f"regras que liberam alteração do repositório: {liberados}"
    for essencial in ("git commit:*", "git push:*", "git add:*"):
        assert f"Bash({essencial})" in permissoes["ask"]
        assert f"PowerShell({essencial})" in permissoes["ask"]
