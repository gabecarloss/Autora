"""A rodada de geração (seção 5), na ordem obrigatória, versão mínima do passo 2.

estudo (pulada: passo 6) → seleção → conceito → plano → edição → revisor e
verificações (puladas: passo 8) → pacote. Um post por rodada. Toda etapa vai para
`etapa_execucao` e para o log; toda decisão do agente vai para `decisao`. Nenhuma
exceção escapa sem registro: a rodada termina `falhou` com mensagem amigável.
"""

from __future__ import annotations

import sqlite3
import tempfile
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal, Protocol

from autora.agente.provedor import ErroAgente, ProvedorAgente
from autora.biblioteca.ficha import FichaClipe, caminhos_dos_clipes, fichas_disponiveis
from autora.config import maquina
from autora.edicao import renderizador
from autora.edicao.ffmpeg import ErroFfmpeg, FfmpegAusente, extrair_audio_wav, localizar_ffmpeg
from autora.edicao.plano import PlanoEdicao
from autora.perfil.perfil import Perfil
from autora.plataformas.base import EspecificacaoVideo, Plataforma, obter
from autora.registro.log import Registro
from autora.rodada import pacote
from autora.rodada.chamada import nivel_configurado
from autora.rodada.conceito import decidir_conceito
from autora.rodada.esquemas import Conceito
from autora.rodada.plano import roteirizar
from autora.servicos.cadeia import Resultado, TodosFalharam
from autora.servicos.transcricao import Transcricao, pasta_modelos, transcrever
from autora.util.tempo import agora_iso

Origem = Literal["automatica", "manual", "teste"]
MENSAGEM_ERRO_GENERICA: Final = (
    "Algo deu errado ao criar o post. Veja a linha do tempo em Bastidores."
)


class SemMaterial(RuntimeError):
    pass


class Renderizador(Protocol):
    def __call__(
        self,
        plano: PlanoEdicao,
        clipes: Mapping[int, Path],
        destino: Path,
        *,
        espec: EspecificacaoVideo,
        registro: Registro,
        idioma: str | None,
        pasta_modelos: Path,
        rodada_id: int | None,
        post_id: int | None,
        transcritor: renderizador.Transcritor | None,
    ) -> renderizador.Entrega: ...


@dataclass(frozen=True)
class ResultadoRodada:
    ok: bool
    mensagem: str
    rodada_id: int | None = None
    post_id: int | None = None
    pasta_saida: Path | None = None  # caminho desta máquina (linha de comando)
    pasta_relativa: str | None = None  # para a tela: relativo à pasta de dados, nunca absoluto


def pasta_para_tela(pasta: Path, dados: Path, relativa_na_saida: str) -> str:
    """Relativo à pasta de dados; se a pasta de saída do perfil estiver fora dela, relativo
    a essa pasta de saída. Sempre com "/", nunca com letra de unidade."""
    try:
        return pasta.resolve().relative_to(dados.resolve()).as_posix()
    except ValueError:
        return relativa_na_saida


class _Etapas:
    def __init__(self, con: sqlite3.Connection, registro: Registro, rodada_id: int) -> None:
        self.con, self.registro, self.rodada_id = con, registro, rodada_id

    def pular(self, nome: str, motivo: str, post_id: int | None = None) -> None:
        agora = agora_iso()
        self.con.execute(
            "INSERT INTO etapa_execucao"
            " (rodada_id, post_id, etapa, iniciada_em, terminada_em, estado, erro)"
            " VALUES (?, ?, ?, ?, ?, 'pulada', ?)",
            (self.rodada_id, post_id, nome, agora, agora, motivo),
        )
        self.registro.registrar(
            "etapa",
            f"Etapa pulada: {motivo}",
            etapa=nome,
            rodada_id=self.rodada_id,
            post_id=post_id,
        )

    @contextmanager
    def executar(self, nome: str, post_id: int | None = None) -> Iterator[None]:
        cur = self.con.execute(
            "INSERT INTO etapa_execucao (rodada_id, post_id, etapa, iniciada_em, estado)"
            " VALUES (?, ?, ?, ?, 'em_andamento')",
            (self.rodada_id, post_id, nome, agora_iso()),
        )
        etapa_id = cur.lastrowid
        self.registro.registrar(
            "etapa", "Etapa iniciada.", etapa=nome, rodada_id=self.rodada_id, post_id=post_id
        )
        try:
            yield
        except BaseException as e:
            self.con.execute(
                "UPDATE etapa_execucao SET terminada_em = ?, estado = 'falhou', erro = ?"
                " WHERE id = ?",
                (agora_iso(), str(e)[:1000], etapa_id),
            )
            raise
        self.con.execute(
            "UPDATE etapa_execucao SET terminada_em = ?, estado = 'ok' WHERE id = ?",
            (agora_iso(), etapa_id),
        )
        self.registro.registrar(
            "etapa", "Etapa concluída.", etapa=nome, rodada_id=self.rodada_id, post_id=post_id
        )


def _gravar_decisoes(
    con: sqlite3.Connection,
    rodada_id: int,
    post_id: int,
    conceito: Conceito,
    plano: PlanoEdicao | None,
) -> None:
    raciocinio = conceito.raciocinio.model_dump_json()
    itens: list[tuple[str, str, str]] = [
        ("formato", conceito.formato.valor, conceito.formato.motivo),
        (
            "fonte_material",
            conceito.fonte_material,
            "Única origem disponível nesta versão (pasta).",
        ),
        ("tema", conceito.tema, conceito.raciocinio.motivo_da_escolha),
        ("gancho", conceito.gancho.valor, conceito.gancho.motivo),
        ("horario", conceito.horario_sugerido.valor, conceito.horario_sugerido.motivo),
        ("capa", conceito.capa.valor, conceito.capa.motivo),
        *[("clipe", str(c.clipe_id), c.motivo) for c in conceito.clipes_escolhidos],
        *[("elemento_autoral", e.tipo, e.descricao) for e in conceito.elementos_autorais],
    ]
    if conceito.som is not None:
        itens.append(("som", conceito.som.nome or "a escolher no app", conceito.som.motivo))
    if plano is not None:
        itens += [
            (
                "ritmo",
                f"{len(plano.trechos)} trecho(s), {plano.duracao_s:.1f} s",
                plano.motivos.ritmo,
            ),
            ("enquadramento", plano.trechos[0].enquadramento.modo, plano.motivos.enquadramento),
            ("textos", f"{len(plano.textos)} texto(s)", plano.motivos.textos),
            (
                "legendas",
                plano.legendas.modo if plano.legendas.ativas else "desligadas",
                plano.motivos.legendas,
            ),
        ]
    for campo, escolha, motivo in itens:
        con.execute(
            "INSERT INTO decisao"
            " (rodada_id, post_id, campo, escolha, motivo, raciocinio_json, criada_em)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                rodada_id,
                post_id,
                campo,
                escolha,
                motivo,
                raciocinio if plano is None else None,
                agora_iso(),
            ),
        )


def codigo_idioma(texto: str | None) -> str | None:
    """ "pt-BR" → "pt"; "português" → None (o Whisper detecta). PROVISÓRIO."""
    if not texto:
        return None
    base = texto.strip().split("-")[0].split("_")[0].lower()
    return base if len(base) == 2 and base.isalpha() else None


def transcritor_de_edicao(
    perfil: Perfil, dados: Path, *, rodada_id: int | None, post_id: int | None
) -> renderizador.Transcritor:
    """Cadeia de legenda para o renderizador, com os modelos escolhidos em maquina.json."""
    cfg = maquina.carregar(dados)

    def _transcrever(wav: Path) -> Resultado[Transcricao]:
        return transcrever(
            wav,
            idioma=codigo_idioma(perfil.config.identidade.idioma_saida),
            registro=perfil.registro,
            pasta_modelos=pasta_modelos(dados),
            modelo_gpu=cfg.whisper_modelo_gpu,
            modelo_cpu=cfg.whisper_modelo_cpu,
            rodada_id=rodada_id,
            post_id=post_id,
        )

    return _transcrever


def transcritor_de_clipes(perfil: Perfil, dados: Path) -> Callable[[Path], str | None]:
    """Transcreve o clipe original para a ficha; sem serviço de legenda, devolve None."""
    par = localizar_ffmpeg()
    cfg = maquina.carregar(dados)
    idioma = codigo_idioma(perfil.config.conteudo.idioma_origem)

    def _transcrever(caminho: Path) -> str | None:
        if par is None:
            perfil.registro.registrar(
                "servico",
                "O programa de vídeo não está instalado; os clipes ficam sem transcrição.",
                etapa="selecao",
            )
            return None
        with tempfile.TemporaryDirectory() as tmp:
            try:
                wav = extrair_audio_wav(caminho, Path(tmp) / "clipe.wav", par[0])
                r = transcrever(
                    wav,
                    idioma=idioma,
                    registro=perfil.registro,
                    pasta_modelos=pasta_modelos(dados),
                    modelo_gpu=cfg.whisper_modelo_gpu,
                    modelo_cpu=cfg.whisper_modelo_cpu,
                    etapa="selecao",
                )
            except (ErroFfmpeg, TodosFalharam) as e:
                perfil.registro.registrar(
                    "servico",
                    f"O clipe “{caminho.name}” ficou sem transcrição.",
                    etapa="selecao",
                    detalhe={"erro": f"{type(e).__name__}: {e}"},
                )
                return None
        return r.valor.texto() or None

    return _transcrever


def _mensagem_amigavel(e: Exception) -> str:
    if isinstance(e, ErroAgente):
        return e.mensagem_amigavel
    if isinstance(e, (SemMaterial, FfmpegAusente, renderizador.ErroRender)):
        return str(e)
    if isinstance(e, renderizador.PlanoInvalido):
        return "O roteiro de edição não bateu com os clipes: " + "; ".join(e.problemas)
    return MENSAGEM_ERRO_GENERICA


def gerar(
    perfil: Perfil,
    provedor: ProvedorAgente,
    dados: Path,
    *,
    origem: Origem = "manual",
    plataforma: Plataforma | None = None,
    renderizar: Renderizador | None = None,
    transcrever_clipe: Callable[[Path], str | None] | None = None,
) -> ResultadoRodada:
    plataforma = plataforma or obter(perfil.config.plataforma)
    render: Renderizador = renderizar or renderizador.renderizar
    transcrever_clipe = transcrever_clipe or transcritor_de_clipes(perfil, dados)
    registro = perfil.registro
    with perfil.trava(), perfil.conectar() as con:
        cur = con.execute(
            "INSERT INTO rodada (iniciada_em, origem, estado, videos_pedidos)"
            " VALUES (?, ?, 'em_andamento', 1)",
            (agora_iso(), origem),
        )
        rodada_id = int(cur.lastrowid or 0)
        registro.registrar(
            "rodada", "Criação do post iniciada.", rodada_id=rodada_id, detalhe={"origem": origem}
        )
        etapas = _Etapas(con, registro, rodada_id)
        post_id: int | None = None
        pasta: Path | None = None
        try:
            etapas.pular("estudo", "o estudo do dia entra numa versão futura (passo 6)")
            with etapas.executar("selecao"):
                fichas = fichas_disponiveis(
                    perfil,
                    dados,
                    con,
                    transcrever=transcrever_clipe,
                    ffprobe=(localizar_ffmpeg() or (None, None))[1],
                )
                if not fichas:
                    raise SemMaterial("Nenhum vídeo disponível nas pastas do perfil.")
            post_id = int(
                con.execute(
                    "INSERT INTO post (rodada_id, numero_na_rodada, criado_em, estado, plataforma)"
                    " VALUES (?, 1, ?, 'gerando', ?)",
                    (rodada_id, agora_iso(), plataforma.nome),
                ).lastrowid
                or 0
            )
            with etapas.executar("conceito", post_id):
                conceito = decidir_conceito(
                    perfil,
                    provedor,
                    con,
                    fichas,
                    plataforma,
                    rodada_id=rodada_id,
                    post_id=post_id,
                    nivel=nivel_configurado(dados, "conceito"),
                )
                _gravar_decisoes(con, rodada_id, post_id, conceito, None)
                registro.registrar(
                    "decisao",
                    f"Ideia do post: {conceito.conceito}",
                    etapa="conceito",
                    rodada_id=rodada_id,
                    post_id=post_id,
                    detalhe=conceito.model_dump(mode="json"),
                )
            escolhidas: list[FichaClipe] = [f for f in fichas if f.id in conceito.ids_escolhidos()]
            with etapas.executar("plano", post_id):
                plano = roteirizar(
                    perfil,
                    provedor,
                    con,
                    conceito,
                    escolhidas,
                    plataforma,
                    rodada_id=rodada_id,
                    post_id=post_id,
                    nivel=nivel_configurado(dados, "plano"),
                )
                _gravar_decisoes(con, rodada_id, post_id, conceito, plano)
                registro.registrar(
                    "decisao",
                    f"Roteiro de edição: {len(plano.trechos)} trecho(s), {plano.duracao_s:.1f} s.",
                    etapa="plano",
                    rodada_id=rodada_id,
                    post_id=post_id,
                    detalhe=plano.model_dump(mode="json"),
                )
            pasta, pasta_relativa = pacote.nova_pasta_do_post(dados, perfil.slug)
            with etapas.executar("edicao", post_id):
                entrega = render(
                    plano,
                    caminhos_dos_clipes(escolhidas, dados),
                    pasta,
                    espec=plataforma.video,
                    registro=registro,
                    idioma=codigo_idioma(perfil.config.identidade.idioma_saida),
                    pasta_modelos=pasta_modelos(dados),
                    rodada_id=rodada_id,
                    post_id=post_id,
                    transcritor=transcritor_de_edicao(
                        perfil, dados, rodada_id=rodada_id, post_id=post_id
                    ),
                )
            etapas.pular(
                "revisor", "o revisor independente entra numa versão futura (passo 8)", post_id
            )
            etapas.pular(
                "verificacoes",
                "as checagens automáticas entram numa versão futura (passo 8)",
                post_id,
            )
            with etapas.executar("pacote", post_id):
                pacote.escrever_pacote(pasta, perfil, plataforma, conceito, plano, entrega)
                pacote.gravar_post_pronto(con, post_id, conceito, plano, entrega, pasta_relativa)
            con.execute(
                "UPDATE rodada SET terminada_em = ?, estado = 'concluida', videos_entregues = 1"
                " WHERE id = ?",
                (agora_iso(), rodada_id),
            )
            registro.registrar(
                "rodada",
                "Post pronto para revisão.",
                rodada_id=rodada_id,
                post_id=post_id,
                detalhe={"pasta_saida": pasta_relativa},
            )
            return ResultadoRodada(
                True,
                "Post pronto para revisão.",
                rodada_id,
                post_id,
                pasta,
                pasta_para_tela(pasta, dados, pasta_relativa),
            )
        except Exception as e:
            mensagem = _mensagem_amigavel(e)
            registro.erro(
                f"A criação do post falhou: {mensagem}", e, rodada_id=rodada_id, post_id=post_id
            )
            if post_id is not None:
                con.execute("UPDATE post SET estado = 'falhou' WHERE id = ?", (post_id,))
            con.execute(
                "UPDATE rodada SET terminada_em = ?, estado = 'falhou', observacao = ?"
                " WHERE id = ?",
                (agora_iso(), mensagem, rodada_id),
            )
            return ResultadoRodada(False, mensagem, rodada_id, post_id, pasta)


def gerar_com_conexao(perfil: Perfil, dados: Path, *, origem: Origem = "manual") -> ResultadoRodada:
    """Usa o agente conectado no app. Levanta AgenteNaoConectado antes de abrir a rodada."""
    from autora.agente import conexao

    return gerar(perfil, conexao.provedor_atual(dados), dados, origem=origem)


def _ignorado(*_: Any) -> None:  # pragma: no cover - mantém o import de Any usado em tipos
    return None
