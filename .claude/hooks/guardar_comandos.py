"""PreToolUse (Bash|PowerShell): protege o repositório git e a pasta de dados real.

Regra do usuário (CLAUDE.md): o Claude nunca commita nem altera o repositório sem pedido
explícito. As regras de permissão do settings.json comparam só o começo do comando;
aqui o comando é dividido em partes (&&, ||, ;, |, quebra de linha) e cada parte é
avaliada, para que "cd x && git commit" também peça confirmação.

- deny: atalhos destrutivos ou que pulam verificações (push --force, reset --hard,
  clean -f, --no-verify) e apagar/mover algo na pasta de dados real do app.
- ask: qualquer git ou gh que altere o repositório ou o GitHub.
- nada: leitura (git status/diff/log..., gh run list...), que segue o fluxo normal.
"""

from __future__ import annotations

import os
import re
import shlex
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Final

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _comum import ESCRITOR_DE_TESTES, agente_da_entrada, decidir, ler_entrada

Decisao = tuple[str, str]

# "&" sozinho também separa (segundo plano no bash, operador de chamada no PowerShell).
_SEPARADORES: Final = re.compile(r"&&|\|\||[;|\n&]")
_SUBSHELL: Final = re.compile(r"\$\(([^()]*)\)|`([^`]*)`")
_PREFIXOS_IGNORADOS: Final = frozenset({"sudo", "command", "exec", "time", "nohup", "env"})
_SHELLS_POSIX: Final = frozenset({"bash", "sh", "zsh", "dash"})
_SHELLS_PS: Final = frozenset({"powershell", "pwsh"})
_XARGS_COM_VALOR: Final = frozenset({"-I", "-n", "-L", "-P", "-d", "-E", "-s", "-a"})
_PROFUNDIDADE_MAXIMA: Final = 4

# --- git --------------------------------------------------------------------
_GIT_OPCOES_COM_VALOR: Final = frozenset({"-C", "-c", "--git-dir", "--work-tree", "--namespace"})
GIT_LEITURA: Final = frozenset(
    {
        "status", "diff", "log", "show", "rev-parse", "ls-files", "blame", "describe",
        "shortlog", "grep", "cat-file", "rev-list", "merge-base", "check-ignore", "ls-tree",
        "ls-remote", "version", "help", "whatchanged", "count-objects", "for-each-ref",
        "show-ref", "name-rev", "var", "diff-tree", "diff-files", "diff-index",
    }
)  # fmt: skip
_BRANCH_ESCRITA: Final = frozenset(
    {"-d", "-D", "--delete", "-m", "-M", "--move", "-c", "-C", "--copy", "-u",
     "--set-upstream-to", "--unset-upstream", "--edit-description", "-f", "--force", "-t",
     "--track", "--no-track"}
)  # fmt: skip
_BRANCH_LISTAGEM: Final = frozenset(
    {"-l", "--list", "--contains", "--no-contains", "--merged", "--no-merged", "--points-at"}
)
_TAG_ESCRITA: Final = frozenset(
    {"-d", "--delete", "-a", "--annotate", "-s", "--sign", "-u", "--local-user", "-m",
     "--message", "-F", "--file", "-f", "--force"}
)  # fmt: skip
_TAG_LISTAGEM: Final = frozenset(
    {"-l", "--list", "--contains", "--no-contains", "--merged", "--no-merged", "--points-at"}
)
_CONFIG_LEITURA: Final = frozenset(
    {"--get", "--get-all", "--get-regexp", "--get-urlmatch", "-l", "--list"}
)

# --- gh ---------------------------------------------------------------------
GH_LEITURA: Final[dict[str, frozenset[str] | None]] = {
    # None = qualquer subcomando é leitura
    "run": frozenset({"list", "view", "watch"}),
    "pr": frozenset({"list", "view", "diff", "checks", "status"}),
    "issue": frozenset({"list", "view", "status"}),
    "repo": frozenset({"view", "list"}),
    "auth": frozenset({"status"}),
    "release": frozenset({"list", "view"}),
    "workflow": frozenset({"list", "view"}),
    "search": None,
    "status": None,
    "version": None,
    "help": None,
    "--version": None,
    "--help": None,
}
_GH_API_ESCRITA: Final = frozenset(
    {"-f", "-F", "--field", "--raw-field", "--input", "-X", "--method"}
)

# --- pasta de dados ---------------------------------------------------------
_DESTRUTIVOS: Final = frozenset(
    {"rm", "rmdir", "rd", "del", "erase", "remove-item", "ri", "mv", "move", "move-item",
     "mi", "rename-item", "ren", "rni", "clear-content", "clc", "robocopy", "shred"}
)  # fmt: skip

MOTIVO_GIT: Final = (
    "Esta operação altera o repositório git. Regra do projeto (CLAUDE.md): o Claude só "
    "commita ou mexe no repositório com pedido explícito do usuário."
)
MOTIVO_GH: Final = (
    "Esta operação altera o GitHub (PR, release, repositório, workflow ou API). "
    "Só com pedido explícito do usuário."
)


def _tokens(parte: str) -> list[str]:
    # posix=False preserva as barras invertidas dos caminhos do Windows; as aspas que
    # sobram nas pontas são tiradas à mão.
    try:
        brutos = shlex.split(parte, posix=False)
    except ValueError:
        brutos = parte.split()
    return [t[1:-1] if len(t) >= 2 and t[0] == t[-1] and t[0] in "'\"" else t for t in brutos]


def _programa(tokens: Sequence[str]) -> tuple[str, list[str]]:
    """Nome do programa (minúsculo, sem caminho nem .exe) e seus argumentos."""
    i = 0
    while i < len(tokens) and (
        tokens[i].lower() in _PREFIXOS_IGNORADOS or re.match(r"^[A-Za-z_]\w*=", tokens[i])
    ):
        i += 1
    if i >= len(tokens):
        return "", []
    nome = tokens[i].strip("'\"").replace("\\", "/").rsplit("/", 1)[-1].lower()
    nome = nome.removesuffix(".exe")
    return nome, list(tokens[i + 1 :])


def _posicionais(args: Sequence[str]) -> list[str]:
    return [a for a in args if not a.startswith("-")]


def _tem(args: Sequence[str], opcoes: frozenset[str]) -> bool:
    return any(a in opcoes or a.split("=", 1)[0] in opcoes for a in args)


def avaliar_git(args: Sequence[str]) -> Decisao | None:
    i = 0
    while i < len(args) and args[i].startswith("-"):
        i += 2 if args[i] in _GIT_OPCOES_COM_VALOR else 1
    if i >= len(args):
        return None  # "git --version", "git --help"
    sub, resto = args[i].lower(), list(args[i + 1 :])

    if "--no-verify" in resto or (
        sub == "commit" and any(re.fullmatch(r"-[a-zA-Z]*n[a-zA-Z]*", a) for a in resto)
    ):
        return ("deny", "Pular os hooks do git (--no-verify) não é permitido neste projeto.")
    if sub == "push" and (
        _tem(resto, frozenset({"-f", "--force", "--force-with-lease", "--force-if-includes"}))
        or any(a.startswith("+") for a in resto)
    ):
        return ("deny", "push forçado não é permitido neste projeto.")
    if sub == "reset" and "--hard" in resto:
        return ("deny", "git reset --hard descarta trabalho e não é permitido.")
    if sub == "clean" and (
        _tem(resto, frozenset({"--force"}))
        or any(re.fullmatch(r"-[a-zA-Z]*f[a-zA-Z]*", a) for a in resto)
    ):
        return ("deny", "git clean -f apaga arquivos não versionados e não é permitido.")

    if sub in GIT_LEITURA:
        # --output grava o resultado em arquivo (git diff/log/show --output=x).
        return ("ask", MOTIVO_GIT) if any(a.startswith("--output") for a in resto) else None
    leitura = False
    if sub == "branch":
        leitura = not _tem(resto, _BRANCH_ESCRITA) and (
            not _posicionais(resto) or _tem(resto, _BRANCH_LISTAGEM)
        )
    elif sub == "tag":
        leitura = not _tem(resto, _TAG_ESCRITA) and (
            not _posicionais(resto) or _tem(resto, _TAG_LISTAGEM)
        )
    elif sub == "stash":
        leitura = bool(resto) and resto[0] in {"list", "show"}
    elif sub == "remote":
        leitura = not resto or resto[0] in {"-v", "--verbose", "show", "get-url"}
    elif sub == "config":
        leitura = _tem(resto, _CONFIG_LEITURA)
    elif sub in {"worktree", "notes"}:
        leitura = bool(resto) and resto[0] in {"list", "show"}
    elif sub == "reflog":
        leitura = not resto or resto[0] == "show" or resto[0].startswith("-")
    elif sub == "submodule":
        leitura = bool(resto) and resto[0] == "status"
    return None if leitura else ("ask", MOTIVO_GIT)


def avaliar_gh(args: Sequence[str]) -> Decisao | None:
    if not args:
        return None
    grupo = args[0].lower()
    if grupo == "api":
        resto = args[1:]
        metodo = next(
            (resto[i + 1].upper() for i, a in enumerate(resto[:-1]) if a in {"-X", "--method"}),
            None,
        )
        metodo = metodo or next(
            (a.split("=", 1)[1].upper() for a in resto if a.startswith("--method=")), None
        )
        if metodo in (None, "GET") and not _tem(resto, _GH_API_ESCRITA - {"-X", "--method"}):
            return None
        return ("ask", MOTIVO_GH)
    if grupo in GH_LEITURA:
        permitidos = GH_LEITURA[grupo]
        if permitidos is None:
            return None
        if len(args) > 1 and args[1].lower() in permitidos:
            return None
    return ("ask", MOTIVO_GH)


def pastas_protegidas() -> list[str]:
    """Formas (normalizadas) de escrever a pasta de dados real no comando."""
    pastas = [Path.home() / "Autora"]
    if os.environ.get("AUTORA_DADOS"):
        pastas.append(Path(os.environ["AUTORA_DADOS"]))
    formas: set[str] = {"~/autora", "$home/autora", "${home}/autora", "%userprofile%/autora",
                        "$env:userprofile/autora"}  # fmt: skip
    for pasta in pastas:
        texto = str(pasta).replace("\\", "/").lower().rstrip("/")
        formas.add(texto)
        if re.match(r"^[a-z]:/", texto):
            formas.add(f"/{texto[0]}{texto[2:]}")  # forma do Git Bash: /c/Users/...
    return sorted(formas)


def _menciona_pasta(comando: str, formas: Sequence[str]) -> bool:
    texto = comando.replace("\\", "/").lower()
    return any(re.search(re.escape(forma) + r"(?=$|[/\s\"');])", texto) for forma in formas)


def _comando_embrulhado(programa: str, args: Sequence[str]) -> str | None:
    """Texto do comando que um shell ou o xargs vai rodar (bash -c '...', cmd /c ...)."""
    if programa in _SHELLS_POSIX:
        for i, a in enumerate(args[:-1]):
            if re.fullmatch(r"-[a-z]*c[a-z]*", a):  # -c, -lc, -ic
                return args[i + 1]
        return None
    if programa in _SHELLS_PS:
        for i, a in enumerate(args):
            if a.lower() in {"-command", "-c"}:
                return " ".join(args[i + 1 :])
        return None
    if programa == "cmd":
        for i, a in enumerate(args):
            if a.lower() in {"/c", "/k"}:
                return " ".join(args[i + 1 :])
        return None
    if programa == "wsl":
        resto = list(args)
        if resto and resto[0] in {"-e", "--exec", "--"}:
            resto = resto[1:]
        return " ".join(resto)
    if programa == "xargs":
        i = 0
        while i < len(args) and args[i].startswith("-"):
            i += 2 if args[i] in _XARGS_COM_VALOR else 1
        return " ".join(args[i:])
    return None


def _coletar(comando: str, profundidade: int = 0) -> tuple[list[Decisao], bool]:
    """Decisões de cada parte do comando, entrando em $(...), `...` e shells embrulhados."""
    decisoes: list[Decisao] = []
    destrutivo = False
    if profundidade > _PROFUNDIDADE_MAXIMA:
        return [("ask", "Comando aninhado demais para avaliar com segurança.")], False
    for interno in _SUBSHELL.findall(comando):
        d_int, x_int = _coletar(interno[0] or interno[1], profundidade + 1)
        decisoes += d_int
        destrutivo = destrutivo or x_int
    for parte in _SEPARADORES.split(comando):
        programa, args = _programa(_tokens(parte))
        if programa == "git":
            d = avaliar_git(args)
        elif programa == "gh":
            d = avaliar_gh(args)
        else:
            d = None
            destrutivo = destrutivo or programa in _DESTRUTIVOS
            embrulhado = _comando_embrulhado(programa, args)
            if embrulhado:
                d_emb, x_emb = _coletar(embrulhado, profundidade + 1)
                decisoes += d_emb
                destrutivo = destrutivo or x_emb
        if d is not None:
            decisoes.append(d)
    return decisoes, destrutivo


# --- escritor-de-testes: lista fechada ---------------------------------------
# Só a forma exata da atualização do PATH (a do verificador) é aceita.
_PATH_PS: Final = re.compile(
    r"\$env:Path\s*=\s*\[Environment\]::GetEnvironmentVariable\(\s*'Path'\s*,\s*'Machine'\s*\)"
    r"\s*\+\s*';'\s*\+\s*"
    r"\[Environment\]::GetEnvironmentVariable\(\s*'Path'\s*,\s*'User'\s*\)",
    re.IGNORECASE,
)
# Redirecionamento, pipe, parênteses/chaves (executam comandos no PowerShell), variáveis
# e "&" sozinho ficam proibidos; separadores aceitos: ";", "&&" e quebra de linha.
_ESCRITOR_PROIBIDOS: Final = re.compile(r"[<>|(){}$`]|(?<!&)&(?!&)")
_ESCRITOR_SEPARADORES: Final = re.compile(r"&&|[;\n]")
# Argumentos aceitos: caminho de teste, '' (texto entre aspas já esvaziado), palavra
# simples (ex.: expressão do -k) e opções de leitura do pytest.
_ARG_PYTEST: Final = (
    r"(?:tests(?:[/\\][\w.\-\[\]:/\\]*)?"
    r"|''|[A-Za-z_]\w*"
    r"|-q|-qq|-v|-vv|-x|-s|-k|-m|-rA|--lf|--ff|--sw|--no-cov|--tb=\w+|--maxfail=\d+)"
)
_ESCRITOR_PERMITIDOS: Final = (
    re.compile(rf"uv run (?:--quiet |-q )?pytest(?: {_ARG_PYTEST})*"),
    re.compile(r"uv run (?:--quiet |-q )?poe testar"),
    re.compile(r"npm (?:--prefix frontend )?(?:run )?test"),
    re.compile(r"npx vitest(?: run)?(?: (?:src|frontend/src)/[\w./-]+\.test\.tsx?)*"),
    re.compile(r"(?:cd|set-location|sl) (?:''|[\w.:/\\-]+)", re.IGNORECASE),
)


def avaliar_escritor_de_testes(comando: str) -> Decisao | None:
    """O escritor de testes só roda testes: qualquer outro comando é negado.

    Lista fechada: cada parte do comando precisa casar POR INTEIRO com uma forma
    permitida. Sem isso, o PowerShell dele poderia escrever fora de tests/ (Set-Content,
    redirecionamento, python -c, --junitxml=src/...) ou disparar o agente real.
    """
    recusa = (
        "O escritor de testes só roda testes (uv run pytest tests/..., uv run poe testar, "
        "npm test), sem redirecionamento nem subcomandos. Comando recusado: "
    )
    sem_path = _PATH_PS.sub("", comando)
    # Esvazia o conteúdo entre aspas: ';' ou '>' dentro de texto não contam.
    sem_textos = re.sub(r"'[^']*'|\"[^\"]*\"", "''", sem_path)
    proibido = _ESCRITOR_PROIBIDOS.search(sem_textos)
    if proibido:
        return ("deny", recusa + f"(contém {proibido.group(0)!r})")
    for parte in _ESCRITOR_SEPARADORES.split(sem_textos):
        texto = " ".join(parte.split())
        if texto and not any(p.fullmatch(texto) for p in _ESCRITOR_PERMITIDOS):
            return ("deny", recusa + texto[:80])
    return None


def avaliar(comando: str, formas_dados: Sequence[str] | None = None) -> Decisao | None:
    formas = pastas_protegidas() if formas_dados is None else formas_dados
    decisoes, destrutivo = _coletar(comando)
    if destrutivo and _menciona_pasta(comando, formas):
        decisoes.append(
            (
                "deny",
                "O comando apaga ou move algo na pasta de dados real do Autora (perfis, "
                "backups). Isso nunca é feito pelo Claude; peça ao usuário.",
            )
        )
    for tipo in ("deny", "ask"):
        for decisao in decisoes:
            if decisao[0] == tipo:
                return decisao
    return None


def main() -> None:
    entrada = ler_entrada()
    ferramenta = entrada.get("tool_input")
    if not isinstance(ferramenta, dict):
        return
    comando = ferramenta.get("command")
    if not isinstance(comando, str):
        return
    resultado = None
    if agente_da_entrada(entrada) == ESCRITOR_DE_TESTES:
        resultado = avaliar_escritor_de_testes(comando)
    resultado = resultado or avaliar(comando)
    if resultado is not None:
        decidir(*resultado)


if __name__ == "__main__":
    main()
