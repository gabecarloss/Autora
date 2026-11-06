"""Hooks do Claude Code (.claude/hooks): decisões e contrato de entrada/saída."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PASTA_HOOKS = RAIZ / ".claude" / "hooks"
DADOS_REAIS = "C:/Users/fulano/Autora"


def _carregar(nome: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"hook_{nome}", PASTA_HOOKS / f"{nome}.py")
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


guardar = _carregar("guardar_comandos")
proteger = _carregar("proteger_arquivos")
inicio = _carregar("inicio_sessao")
FORMAS = [DADOS_REAIS.lower(), "/c/users/fulano/autora", "~/autora", "%userprofile%/autora"]


def _decisao(comando: str) -> str | None:
    r = guardar.avaliar(comando, FORMAS)
    return None if r is None else str(r[0])


def _rodar_hook(nome: str, entrada: dict[str, object]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, str(PASTA_HOOKS / f"{nome}.py")],
        input=json.dumps(entrada),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=RAIZ,
        timeout=60,
        check=False,
    )


# --- guardar_comandos: git -------------------------------------------------
@pytest.mark.parametrize(
    "comando",
    [
        "git status",
        "git diff --stat HEAD~1",
        "git log --oneline -5",
        "git -C C:\\repo --no-pager log",
        "git branch",
        "git branch -a -v",
        "git branch --show-current",
        "git branch --list 'feat*'",
        "git tag",
        "git tag -l",
        "git stash list",
        "git remote -v",
        "git config --get user.name",
        "git worktree list",
        "git --version",
        "uv run pytest -q",
        "npm --prefix frontend run lint",
        "echo 'git commit -m teste'",
        "git log --oneline 2>&1 | head -5",
        "bash -c 'git status'",
        "echo $(git rev-parse HEAD)",
    ],
)
def test_leitura_segue_o_fluxo_normal(comando: str) -> None:
    assert _decisao(comando) is None


@pytest.mark.parametrize(
    "comando",
    [
        "git add .",
        "git commit -m 'msg'",
        "git push",
        "git push origin main",
        "git pull",
        "git checkout -b nova",
        "git switch main",
        "git merge main",
        "git rebase main",
        "git branch nova",
        "git branch -d velha",
        "git tag v1.0.0",
        "git stash",
        "git restore arquivo.py",
        "git reset HEAD~1",
        "git cherry-pick abc123",
        "git revert abc123",
        "git fetch",
        "git remote add outro https://x",
        "git config user.name Fulano",
        "cd /c/repo && git commit -m x",
        "Set-Location C:\\repo; git add -A",
        "git status | git add .",
        "& 'C:\\Program Files\\Git\\cmd\\git.exe' commit -m x",
        "GIT_AUTHOR_NAME=x git commit -m y",
        # embrulhados e aninhados (achados da auditoria de conformidade)
        "git status & git commit -m x",
        "echo $(git commit -m x)",
        "echo `git commit -m x`",
        "bash -c 'git commit -m x'",
        "bash -lc 'cd x && git push'",
        'powershell -Command "git commit -m x"',
        "pwsh -c git add .",
        "cmd /c git commit -m x",
        "wsl git push",
        "ls | xargs git add",
        "ls | xargs -I {} git add {}",
        "git diff --output=x.patch",
        "git log 2>&1 | tail -1 && git commit -m x",
    ],
)
def test_alterar_o_repositorio_pede_confirmacao(comando: str) -> None:
    assert _decisao(comando) == "ask"


@pytest.mark.parametrize(
    "comando",
    [
        "git push --force",
        "git push -f origin main",
        "git push --force-with-lease",
        "git push origin +main",
        "git commit --no-verify -m x",
        "git commit -nm x",
        "git reset --hard HEAD",
        "git clean -fd",
        "git add . && git commit -m x --no-verify",
        "bash -c 'git push --force'",
        "cmd /c rmdir /s /q C:\\Users\\fulano\\Autora",
    ],
)
def test_atalhos_destrutivos_sao_negados(comando: str) -> None:
    assert _decisao(comando) == "deny"


# --- guardar_comandos: gh --------------------------------------------------
@pytest.mark.parametrize(
    "comando",
    ["gh run list", "gh run watch 123", "gh pr view 4", "gh auth status", "gh --version",
     "gh api repos/x/y/actions/runs", "gh api -X GET repos/x/y"],
)  # fmt: skip
def test_gh_leitura(comando: str) -> None:
    assert _decisao(comando) is None


@pytest.mark.parametrize(
    "comando",
    ["gh pr create --fill", "gh pr merge 3", "gh release create v1", "gh repo edit",
     "gh workflow run ci.yml", "gh api -X POST repos/x/y/issues", "gh api repos/x -f a=b",
     "gh auth login"],
)  # fmt: skip
def test_gh_que_altera_pede_confirmacao(comando: str) -> None:
    assert _decisao(comando) == "ask"


# --- guardar_comandos: pasta de dados real -----------------------------------
@pytest.mark.parametrize(
    "comando",
    [
        "rm -rf /c/Users/fulano/Autora",
        "rm -rf /c/Users/fulano/Autora/perfis/humor",
        "Remove-Item -Recurse -Force C:\\Users\\fulano\\Autora\\perfis",
        'Remove-Item "C:\\Users\\fulano\\Autora"',
        "Get-ChildItem C:\\Users\\fulano\\Autora | Remove-Item",
        "mv ~/Autora/perfis /tmp/x",
        "rmdir /s /q %USERPROFILE%\\Autora",
    ],
)
def test_apagar_a_pasta_de_dados_real_e_negado(comando: str) -> None:
    assert _decisao(comando) == "deny"


@pytest.mark.parametrize(
    "comando",
    [
        "rm -rf /c/Users/fulano/Autora-dev/perfis",
        "rm -rf /c/Users/fulano/Desktop/Autora/build",
        "ls /c/Users/fulano/Autora/perfis",
        "Get-ChildItem C:\\Users\\fulano\\Autora",
    ],
)
def test_outras_pastas_e_leitura_da_pasta_de_dados_passam(comando: str) -> None:
    assert _decisao(comando) is None


def test_formas_da_pasta_de_dados_incluem_git_bash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTORA_DADOS", "D:\\Dados\\Autora")
    formas = guardar.pastas_protegidas()
    assert "d:/dados/autora" in formas
    assert "/d/dados/autora" in formas


# --- proteger_arquivos --------------------------------------------------------
def test_briefing_e_mandato_pedem_confirmacao() -> None:
    for caminho in ("C:\\x\\BRIEFING.md", "src/autora/perfil/modelos/mandato.md"):
        r = proteger.avaliar({"file_path": caminho, "content": "x"})
        assert r is not None and r[0] == "ask"


def test_arquivo_comum_passa() -> None:
    assert proteger.avaliar({"file_path": "src/autora/x.py", "new_string": "a = 1"}) is None


def test_segredo_real_e_negado_e_falso_curto_passa() -> None:
    real = "sk-ant-oat01-" + "A1b2C3d4" * 12
    assert proteger.avaliar({"file_path": "a.py", "content": f"T = '{real}'"})[0] == "deny"
    falso = "sk-ant-oat01-SEGREDO-DE-TESTE-1234567890abcdef"
    assert proteger.avaliar({"file_path": "tests/a.py", "content": f"T = '{falso}'"}) is None


def test_segredo_em_multiedit_e_chave_privada() -> None:
    pem = "-----BEGIN " + "PRIVATE KEY-----"
    edicoes = {"file_path": "a.txt", "edits": [{"old_string": "x", "new_string": pem}]}
    assert proteger.avaliar(edicoes)[0] == "deny"


# --- escritor-de-testes: só escreve e roda testes ----------------------------------
ESCRITOR = "escritor-de-testes"
PATH_PS = (
    "$env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + "
    "[Environment]::GetEnvironmentVariable('Path','User')"
)


@pytest.mark.parametrize(
    "caminho",
    [
        "tests/test_novo.py",
        str(RAIZ / "tests" / "hooks" / "test_x.py"),
        "frontend/src/telas/Perfis.test.tsx",
    ],
)
def test_escritor_pode_escrever_testes(caminho: str) -> None:
    assert proteger.avaliar({"file_path": caminho, "content": "x"}, ESCRITOR) is None


@pytest.mark.parametrize(
    "caminho",
    [
        "src/autora/perfil/memoria.py",
        str(RAIZ / "CLAUDE.md"),
        "tests/../src/autora/x.py",
        "../fora.py",
        "frontend/src/telas/Perfis.tsx",
        str(RAIZ / ".claude" / "settings.json"),
    ],
)
def test_escritor_nao_escreve_fora_dos_testes(caminho: str) -> None:
    r = proteger.avaliar({"file_path": caminho, "content": "x"}, ESCRITOR)
    assert r is not None and r[0] == "deny"


def test_outros_agentes_seguem_as_regras_normais() -> None:
    assert proteger.avaliar({"file_path": "src/autora/x.py", "content": "x"}, "Explore") is None


@pytest.mark.parametrize(
    "comando",
    [
        "uv run pytest tests/test_novo.py -q",
        "uv run --quiet pytest tests -k memoria",
        "uv run poe testar",
        "npm --prefix frontend run test",
        f"{PATH_PS}; uv run pytest tests/test_novo.py -q",
        "cd frontend; npm test",
        "uv run pytest tests/hooks/test_hooks.py -k 'escritor and not gh' -x --tb=short",
        "uv run pytest tests/test_x.py::test_um -vv",
        "cd frontend && npx vitest run src/telas/Perfis.test.tsx",
        "Set-Location 'C:\\Users\\x\\Autora'; uv run poe testar",
    ],
)
def test_escritor_pode_rodar_testes(comando: str) -> None:
    assert guardar.avaliar_escritor_de_testes(comando) is None


@pytest.mark.parametrize(
    "comando",
    [
        "Set-Content src/autora/x.py 'a = 1'",
        "python -c \"open('src/x.py','w')\"",
        "git add .",
        "uv run pytest tests; Remove-Item src -Recurse",
        "uv run pytest $(rm -rf src)",
        "echo x > src/autora/x.py",
        "uv run ruff format src",
        # furos achados pela auditoria de conformidade
        "uv run pytest -q > src/autora/x.py",
        "uv run pytest -q >> src/autora/x.py",
        "$env:path = (Set-Content src/x.py 1)",
        "cd (Remove-Item src -Recurse)",
        "npx vitest-qualquer-pacote",
        "uv run pytest --junitxml=src/x.xml",
        "uv run pytest --basetemp=src",
        "uv run --with pacote pytest",
        "uv run --directory .. pytest",
        "uv run poe testar-agente",
        "uv run pytest tests | Set-Content src/x.py",
        "uv run pytest tests & Set-Content src/x.py 1",
        "npm test -- --outputFile=src/x.json",
        "$x = 1",
        "& { Set-Content src/x.py 1 }",
    ],
)
def test_escritor_nao_roda_outros_comandos(comando: str) -> None:
    r = guardar.avaliar_escritor_de_testes(comando)
    assert r is not None and r[0] == "deny"


def test_hooks_aplicam_a_regra_do_escritor_pela_entrada_real() -> None:
    edicao = _rodar_hook(
        "proteger_arquivos",
        {"agent_type": ESCRITOR, "tool_input": {"file_path": "src/x.py", "content": "x"}},
    )
    assert json.loads(edicao.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    comando = _rodar_hook(
        "guardar_comandos",
        {"agent_type": ESCRITOR, "tool_input": {"command": "Set-Content src/x.py 1"}},
    )
    assert json.loads(comando.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    sessao_principal = _rodar_hook(
        "proteger_arquivos", {"tool_input": {"file_path": "src/x.py", "content": "x"}}
    )
    assert sessao_principal.stdout == ""


# --- contrato de entrada e saída (processo de verdade) -----------------------
def test_hook_responde_no_formato_do_claude_code() -> None:
    r = _rodar_hook("guardar_comandos", {"tool_input": {"command": "git commit -m x"}})
    assert r.returncode == 0
    saida = json.loads(r.stdout)["hookSpecificOutput"]
    assert saida["hookEventName"] == "PreToolUse"
    assert saida["permissionDecision"] == "ask"
    assert "pedido explícito" in saida["permissionDecisionReason"]


def test_hook_silencioso_quando_nao_ha_nada_a_dizer() -> None:
    r = _rodar_hook("guardar_comandos", {"tool_input": {"command": "git status"}})
    assert r.returncode == 0
    assert r.stdout == ""


def test_hooks_toleram_entrada_estranha() -> None:
    for nome in ("guardar_comandos", "proteger_arquivos", "formatar"):
        r = subprocess.run(  # noqa: S603
            [sys.executable, str(PASTA_HOOKS / f"{nome}.py")],
            input="isto não é json",
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
            check=False,
        )
        assert r.returncode == 0, r.stderr


def test_formatar_ignora_arquivo_fora_do_projeto(tmp_path: Path) -> None:
    arquivo = tmp_path / "fora.py"
    arquivo.write_text("x=1\n", encoding="utf-8")
    r = _rodar_hook("formatar", {"tool_input": {"file_path": str(arquivo)}})
    assert r.returncode == 0
    assert arquivo.read_text(encoding="utf-8") == "x=1\n"


def test_formatar_respeita_excecoes_do_ruff_com_drive_minusculo() -> None:
    """Regressão: com CLAUDE_PROJECT_DIR = "c:\\..." o ruff ignorava as per-file-ignores."""
    raiz = str(RAIZ)
    minusculo = raiz[0].lower() + raiz[1:]
    r = subprocess.run(  # noqa: S603
        [sys.executable, str(PASTA_HOOKS / "formatar.py")],
        input=json.dumps({"tool_input": {"file_path": str(PASTA_HOOKS / "formatar.py")}}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "CLAUDE_PROJECT_DIR": minusculo},
        timeout=60,
        check=False,
    )
    assert r.returncode == 0, r.stderr


# --- inicio_sessao --------------------------------------------------------------
def test_estado_do_projeto_vem_do_claude_md(tmp_path: Path) -> None:
    md = tmp_path / "CLAUDE.md"
    md.write_text(
        "# X\n\n## Estado do projeto\n\n**Passo 3 concluído.** Próximo:\n**passo 4**.\n\n"
        "### Outra\n",
        encoding="utf-8",
    )
    assert inicio.estado_do_projeto(md) == "Passo 3 concluído. Próximo: passo 4."


def test_inicio_de_sessao_imprime_contexto_curto() -> None:
    r = _rodar_hook("inicio_sessao", {"hook_event_name": "SessionStart", "source": "startup"})
    assert r.returncode == 0
    linhas = r.stdout.strip().splitlines()
    assert 2 <= len(linhas) <= 4
    assert linhas[0].startswith("[Autora] branch ")
