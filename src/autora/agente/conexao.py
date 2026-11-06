"""Conexão do agente feita DENTRO do app (Configurações globais → Agente).

Fluxo da assinatura:
1. `localizar_claude()`; se não houver, `instalar_claude()` (instalador oficial).
2. `abrir_login()` abre uma janela de terminal com `claude setup-token`; o usuário faz
   login no navegador e o terminal mostra um token de longa duração.
3. O usuário cola o token no campo oculto da tela → `conectar_assinatura(token)`,
   que testa ANTES de guardar. Só guarda no keyring se o teste passar.

Fluxo da chave: `conectar_chave(chave)`, também testada antes de guardar.

Nada aqui devolve ou registra o segredo.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from autora.agente.claude_api import ProvedorChave
from autora.agente.claude_assinatura import ProvedorAssinatura, ambiente_isolado
from autora.agente.contexto import montar_sistema_sem_perfil
from autora.agente.provedor import (
    AgenteNaoConectado,
    ErroAgente,
    Pedido,
    ProvedorAgente,
    Resposta,
    chamar_registrando,
)
from autora.config import global_config, segredos
from autora.config.global_config import ConfigGlobal
from autora.registro.log import registro_global
from autora.util.tempo import agora

_SYSTEM32: Final = Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "System32"
CMD: Final = str(_SYSTEM32 / "cmd.exe")
POWERSHELL: Final = str(_SYSTEM32 / "WindowsPowerShell" / "v1.0" / "powershell.exe")

COMANDO_INSTALADOR: Final = [
    POWERSHELL,
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-Command",
    "irm https://claude.ai/install.ps1 | iex",
]
PERGUNTA_TESTE: Final = (
    "Teste de conexão do sistema Autora. Em uma frase curta, em português, diga que "
    "está pronto para trabalhar como o agente descrito no mandato."
)


def pasta_isolada(dados: Path) -> Path:
    """CLAUDE_CONFIG_DIR e pasta de trabalho do agente. Sem credenciais em disco."""
    return dados / "agente_isolado"


def localizar_claude() -> Path | None:
    candidatos: list[Path] = []
    achado = shutil.which("claude")
    if achado:
        candidatos.append(Path(achado))
    home = Path.home()
    candidatos += [
        home / ".local" / "bin" / ("claude.exe" if sys.platform == "win32" else "claude"),
    ]
    for c in candidatos:
        if c.is_file():
            return c
    return None


def versao_claude(executavel: Path) -> str | None:
    try:
        r = subprocess.run(  # noqa: S603
            [str(executavel), "--version"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.strip() or None


def instalar_claude(dados: Path) -> Path:
    """Roda o instalador oficial do Claude Code. Ação disparada pelo usuário na tela."""
    reg = registro_global(dados)
    reg.registrar("usuario", "Instalação do programa do agente iniciada.")
    try:
        r = subprocess.run(  # noqa: S603
            COMANDO_INSTALADOR, capture_output=True, text=True, timeout=600, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        reg.erro("A instalação do programa do agente falhou.", e)
        raise ErroAgente("A instalação do programa do agente falhou.", str(e)) from e
    exe = localizar_claude()
    if exe is None:
        detalhe = (r.stderr or r.stdout)[-2000:]
        reg.registrar(
            "erro",
            "O programa do agente não apareceu após a instalação.",
            detalhe={"saida": detalhe},
        )
        raise ErroAgente("O programa do agente não apareceu após a instalação.", detalhe)
    reg.registrar(
        "sistema", "Programa do agente instalado.", detalhe={"versao": versao_claude(exe)}
    )
    return exe


def abrir_login(dados: Path) -> None:
    """Abre um terminal novo com `claude setup-token`, isolado do login do desenvolvimento."""
    exe = localizar_claude()
    if exe is None:
        raise AgenteNaoConectado("O programa do agente não está instalado.")
    env = ambiente_isolado("", pasta_isolada(dados) / "config_login")
    env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
    if sys.platform != "win32":
        raise ErroAgente("Abrir o login automaticamente só está disponível no Windows.")
    subprocess.Popen(  # noqa: S603
        [CMD, "/k", str(exe), "setup-token"],
        env=env,
        cwd=str(pasta_isolada(dados)),
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )
    registro_global(dados).registrar("usuario", "Janela de login da assinatura aberta.")


@dataclass
class ResultadoTeste:
    ok: bool
    mensagem: str
    resposta: str | None = None
    duracao_ms: int | None = None
    custo_usd: float | None = None


def provedor_atual(dados: Path, cfg: ConfigGlobal | None = None) -> ProvedorAgente:
    cfg = cfg or global_config.carregar(dados)
    tipo = cfg.agente.tipo
    if tipo == "assinatura":
        token = segredos.obter("agente_token_assinatura")
        exe = localizar_claude()
        if not token or exe is None:
            raise AgenteNaoConectado("A assinatura não está conectada.")
        return ProvedorAssinatura(exe, token, pasta_isolada(dados))
    if tipo == "chave":
        chave = segredos.obter("agente_chave_api")
        if not chave:
            raise AgenteNaoConectado("A chave da API não está conectada.")
        return ProvedorChave(chave)
    raise AgenteNaoConectado("O agente ainda não foi conectado.")


def _testar_provedor(dados: Path, provedor: ProvedorAgente) -> Resposta:
    pedido = Pedido(
        etapa="teste",
        sistema=montar_sistema_sem_perfil(),
        mensagem=PERGUNTA_TESTE,
        tempo_limite_s=180,
    )
    return chamar_registrando(provedor, pedido, registro_global(dados))


def _registrar_resultado(dados: Path, ok: bool, erro: str | None) -> None:
    cfg = global_config.carregar(dados)
    cfg.agente.ultima_verificacao = agora()
    cfg.agente.ultimo_resultado = "ok" if ok else "falhou"
    cfg.agente.ultimo_erro = erro
    global_config.salvar(cfg, dados)


def testar(dados: Path) -> ResultadoTeste:
    try:
        resp = _testar_provedor(dados, provedor_atual(dados))
    except ErroAgente as e:
        _registrar_resultado(dados, False, e.mensagem_amigavel)
        return ResultadoTeste(False, e.mensagem_amigavel)
    _registrar_resultado(dados, True, None)
    return ResultadoTeste(True, "O agente respondeu.", resp.texto, resp.duracao_ms, resp.custo_usd)


def _conectar(
    dados: Path, tipo: str, nome: segredos.NomeSegredo, valor: str, provedor: ProvedorAgente
) -> ResultadoTeste:
    reg = registro_global(dados)
    try:
        resp = _testar_provedor(dados, provedor)
    except ErroAgente as e:
        reg.registrar(
            "usuario",
            "Tentativa de conectar o agente falhou no teste.",
            detalhe={"tipo": tipo, "erro": e.mensagem_amigavel},
        )
        return ResultadoTeste(False, e.mensagem_amigavel)
    # Só guarda depois do teste passar. Troca de conexão apaga o segredo antigo.
    for outro in segredos.NOMES:
        if outro != nome:
            segredos.apagar(outro)
    segredos.definir(nome, valor)
    cfg = global_config.carregar(dados)
    cfg.agente.tipo = tipo  # type: ignore[assignment]
    cfg.agente.conectado_em = agora()
    cfg.agente.ultima_verificacao = agora()
    cfg.agente.ultimo_resultado = "ok"
    cfg.agente.ultimo_erro = None
    global_config.salvar(cfg, dados)
    reg.registrar("usuario", "Agente conectado.", detalhe={"tipo": tipo})
    return ResultadoTeste(True, "Agente conectado.", resp.texto, resp.duracao_ms, resp.custo_usd)


def conectar_assinatura(dados: Path, token: str) -> ResultadoTeste:
    token = token.strip()
    if not token.startswith("sk-ant-"):
        return ResultadoTeste(False, "Isso não parece um código de acesso da assinatura.")
    exe = localizar_claude()
    if exe is None:
        return ResultadoTeste(False, "O programa do agente não está instalado.")
    resultado = _conectar(
        dados,
        "assinatura",
        "agente_token_assinatura",
        token,
        ProvedorAssinatura(exe, token, pasta_isolada(dados)),
    )
    if resultado.ok:
        # A janela de login pode ter deixado arquivos de sessão; o token já está no keyring.
        shutil.rmtree(pasta_isolada(dados) / "config_login", ignore_errors=True)
    return resultado


def conectar_chave(dados: Path, chave: str) -> ResultadoTeste:
    chave = chave.strip()
    if not chave.startswith("sk-ant-"):
        return ResultadoTeste(False, "Isso não parece uma chave da API do Claude.")
    return _conectar(dados, "chave", "agente_chave_api", chave, ProvedorChave(chave))


def desconectar(dados: Path) -> None:
    for nome in segredos.NOMES:
        segredos.apagar(nome)
    cfg = global_config.carregar(dados)
    cfg.agente.tipo = "nenhuma"
    cfg.agente.conectado_em = None
    cfg.agente.ultimo_resultado = None
    cfg.agente.ultimo_erro = None
    global_config.salvar(cfg, dados)
    registro_global(dados).registrar("usuario", "Agente desconectado.")


@dataclass
class EstadoAgente:
    tipo: str
    conectado_em: str | None
    ultima_verificacao: str | None
    ultimo_resultado: str | None
    ultimo_erro: str | None
    programa_instalado: bool
    versao_programa: str | None
    niveis: dict[str, str]


def estado(dados: Path) -> EstadoAgente:
    cfg = global_config.carregar(dados)
    exe = localizar_claude()
    a = cfg.agente
    return EstadoAgente(
        tipo=a.tipo,
        conectado_em=a.conectado_em.isoformat() if a.conectado_em else None,
        ultima_verificacao=a.ultima_verificacao.isoformat() if a.ultima_verificacao else None,
        ultimo_resultado=a.ultimo_resultado,
        ultimo_erro=a.ultimo_erro,
        programa_instalado=exe is not None,
        versao_programa=versao_claude(exe) if exe else None,
        niveis={str(k): str(v) for k, v in a.niveis.items()},
    )
