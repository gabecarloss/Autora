"""Arquivos de memória do perfil, com histórico de versões.

Antes de sobrescrever um arquivo, a versão atual é copiada para
memoria/.historico/<arquivo>/<data-hora>.md. Assim a tela Bastidores (seção 9.5)
consegue abrir uma versão antiga e comparar com a atual.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Final, Literal

from autora.util.arquivos import gravar_atomico
from autora.util.tempo import agora

ArquivoMemoria = Literal[
    "mandato.md",
    "preferencias_usuario.md",
    "aprendizados.md",
    "tendencias.md",
    "publico.md",
    "ganchos.md",
    "testes.md",
]

ARQUIVOS: Final[tuple[ArquivoMemoria, ...]] = (
    "mandato.md",
    "preferencias_usuario.md",
    "aprendizados.md",
    "tendencias.md",
    "publico.md",
    "ganchos.md",
    "testes.md",
)


def modelo(nome: ArquivoMemoria) -> str:
    """Conteúdo inicial do arquivo, empacotado com o app."""
    return (resources.files("autora.perfil") / "modelos" / nome).read_text(encoding="utf-8")


class Memoria:
    def __init__(self, pasta: Path) -> None:
        self.pasta = pasta
        self.pasta_historico = pasta / ".historico"

    def caminho(self, nome: ArquivoMemoria) -> Path:
        if nome not in ARQUIVOS:
            raise ValueError(f"arquivo de memória desconhecido: {nome!r}")
        return self.pasta / nome

    def ler(self, nome: ArquivoMemoria) -> str:
        return self.caminho(nome).read_text(encoding="utf-8")

    def gravar(self, nome: ArquivoMemoria, texto: str) -> Path | None:
        """Grava a nova versão. Devolve o caminho da versão anterior guardada (se havia)."""
        atual = self.caminho(nome)
        guardada: Path | None = None
        if atual.exists():
            anterior = atual.read_text(encoding="utf-8")
            if anterior == texto:
                return None
            guardada = self._nome_livre(self.pasta_historico / nome.removesuffix(".md"))
            gravar_atomico(guardada, anterior)
        gravar_atomico(atual, texto)
        return guardada

    @staticmethod
    def _nome_livre(pasta_h: Path) -> Path:
        """Nome da versão: data e hora; se já existir (duas gravações no mesmo tique do
        relógio do Windows), desempata com _01, _02... Nunca sobrescreve uma versão.

        A ordem por nome continua cronológica: "T.md" < "T_01.md" < "T_02.md", porque
        "_" vem depois de "." e todos os carimbos têm o mesmo tamanho.
        """
        carimbo = agora().strftime("%Y-%m-%dT%H-%M-%S-%f")
        candidato = pasta_h / f"{carimbo}.md"
        n = 0
        while candidato.exists():
            n += 1
            candidato = pasta_h / f"{carimbo}_{n:02d}.md"
        return candidato

    def historico(self, nome: ArquivoMemoria) -> list[Path]:
        pasta_h = self.pasta_historico / nome.removesuffix(".md")
        return sorted(pasta_h.glob("*.md")) if pasta_h.exists() else []

    def criar_iniciais(self) -> None:
        for nome in ARQUIVOS:
            if not self.caminho(nome).exists():
                gravar_atomico(self.caminho(nome), modelo(nome))
