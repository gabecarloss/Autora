"""Linha de comando (desenvolvimento e agendador do Windows).

A conexão do agente NÃO fica aqui: é feita dentro do app.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

import typer

from autora.agente.provedor import AgenteNaoConectado
from autora.backup.backup import aplicar_retencao, backup_diario, fazer_backup
from autora.biblioteca.ficha import registrar_pasta
from autora.config import global_config
from autora.config.global_config import pasta_dados
from autora.perfil.perfil import (
    Perfil,
    PerfilInvalido,
    PerfilJaExiste,
    PerfilNaoEncontrado,
    PerfilOcupado,
    listar,
)
from autora.plataformas.tiktok import registrar_padrao
from autora.rodada.executar import gerar_com_conexao

app = typer.Typer(no_args_is_help=True, add_completion=False, help="Autora")
perfil_app = typer.Typer(no_args_is_help=True, help="Perfis")
app.add_typer(perfil_app, name="perfil")


@app.callback()
def _inicio() -> None:
    logging.basicConfig(level=logging.WARNING)
    registrar_padrao()
    backup_diario(pasta_dados())  # "primeira ação do dia" também faz a cópia


@perfil_app.command("criar")
def perfil_criar(
    slug: str = typer.Argument(..., help="nome interno (letras minúsculas, números, - e _)"),
    nome: str = typer.Option(None, "--nome", help="nome exibido"),
) -> None:
    try:
        p = Perfil.criar(pasta_dados(), slug, nome or slug)
    except PerfilJaExiste:
        typer.echo(f"Já existe um perfil chamado {slug}.", err=True)
        raise typer.Exit(1) from None
    except PerfilInvalido as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1) from None
    typer.echo(f"Perfil criado em {p.raiz}")


@perfil_app.command("listar")
def perfil_listar() -> None:
    dados = pasta_dados()
    slugs = listar(dados)
    if not slugs:
        typer.echo("Nenhum perfil ainda.")
    for slug in slugs:
        try:
            p = Perfil.abrir(dados, slug)
            typer.echo(f"{slug}\t{p.config.identidade.nome}")
        except PerfilInvalido:
            typer.echo(f"{slug}\t(com problema na configuração)")


@app.command("backup")
def backup(
    perfil: str = typer.Option(None, "--perfil", help="só este perfil"),
    forcar: bool = typer.Option(False, "--forcar", help="fazer mesmo se já houver um de hoje"),
) -> None:
    dados = pasta_dados()
    slugs = [perfil] if perfil else listar(dados)
    dias = global_config.carregar(dados).retencao_backups_dias
    for slug in slugs:
        p = Perfil.abrir(dados, slug)
        feito = fazer_backup(p, dados, forcar=forcar)
        aplicar_retencao(dados, slug, dias)
        typer.echo(f"{slug}: {feito.name if feito else 'já havia cópia de hoje'}")


@app.command("gerar")
def gerar(
    slug: str = typer.Argument(..., help="nome interno do perfil"),
    pasta: Annotated[
        Path | None, typer.Option("--pasta", help="pasta de vídeos a vincular antes de criar")
    ] = None,
    teste: bool = typer.Option(
        False, "--teste", help="rodada de teste (marcada como tal no banco)"
    ),
) -> None:
    """Cria um post agora com o agente conectado no app (o mesmo que o botão "Criar agora")."""
    dados = pasta_dados()
    try:
        perfil = Perfil.abrir(dados, slug)
    except PerfilNaoEncontrado:
        typer.echo(f"Não existe perfil chamado {slug}.", err=True)
        raise typer.Exit(1) from None
    except PerfilInvalido as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1) from None
    if pasta is not None:
        try:
            apelido = registrar_pasta(perfil, dados, pasta)
        except FileNotFoundError as e:
            typer.echo(str(e), err=True)
            raise typer.Exit(1) from None
        typer.echo(f"Pasta vinculada como “{apelido}”.")
    try:
        resultado = gerar_com_conexao(perfil, dados, origem="teste" if teste else "manual")
    except AgenteNaoConectado as e:
        typer.echo(f"{e.mensagem_amigavel} Conecte em Configurações globais → Agente.", err=True)
        raise typer.Exit(2) from None
    except PerfilOcupado:
        typer.echo("Este perfil já está criando um post.", err=True)
        raise typer.Exit(3) from None
    if not resultado.ok:
        typer.echo(f"Falhou: {resultado.mensagem}", err=True)
        raise typer.Exit(1)
    typer.echo(f"{resultado.mensagem}\nPasta: {resultado.pasta_saida}")


if __name__ == "__main__":
    app()
