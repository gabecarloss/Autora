"""Executa o roteiro de edição: duas passagens do ffmpeg, Whisper no meio, capa no fim.

1. inspeciona os clipes e confere o roteiro contra eles (problemas → PlanoInvalido);
2. passagem 1 → base.mp4 + base.wav (sem texto);
3. transcreve o áudio já cortado (legendas nascem na linha do tempo final); se o
   serviço de legenda falhar, o vídeo sai sem legendas e o aviso vai para o post.md;
4. gera o ASS (legendas + textos) e roda a passagem 2 → video.mp4;
5. confere o resultado (1080x1920, 30 fps, h264, aac, duração) → ErroRender se divergir;
6. capa.jpg do vídeo final.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Literal

from autora.edicao import filtros, legendas
from autora.edicao.capa import gerar_capa
from autora.edicao.ffmpeg import ErroFfmpeg, InfoVideo, executar, exigir_ffmpeg, inspecionar
from autora.edicao.fontes import preparar_pasta_fontes
from autora.edicao.plano import PlanoEdicao, verificar_contra_clipes
from autora.plataformas.base import EspecificacaoVideo
from autora.registro.log import Registro
from autora.servicos.cadeia import Resultado, TodosFalharam
from autora.servicos.transcricao import Palavra, Transcricao, limitar_ao_video, transcrever

EstadoLegendas = Literal["ok", "sem_fala", "indisponiveis", "desligadas"]
Transcritor = Callable[[Path], Resultado[Transcricao]]
TOLERANCIA_DURACAO_S = 0.15
ETAPA = "edicao"


class PlanoInvalido(ValueError):
    def __init__(self, problemas: list[str]) -> None:
        super().__init__("; ".join(problemas))
        self.problemas = problemas


class ErroRender(RuntimeError):
    pass


@dataclass
class Entrega:
    video: Path
    capa: Path
    duracao_s: float
    legendas: EstadoLegendas
    transcricao: Transcricao | None
    info: InfoVideo
    avisos: list[str] = field(default_factory=list)


def _conferir_saida(info: InfoVideo, esperado_s: float, espec: EspecificacaoVideo) -> None:
    problemas = []
    if (info.largura, info.altura) != (espec.largura, espec.altura):
        problemas.append(f"tamanho {info.largura}x{info.altura}")
    if info.fps != Fraction(espec.fps):
        problemas.append(f"{info.fps} fps")
    if info.codec_video != espec.codec:
        problemas.append(f"codec {info.codec_video}")
    if info.codec_audio != "aac":
        problemas.append(f"áudio {info.codec_audio}")
    if abs(info.duracao_s - esperado_s) > TOLERANCIA_DURACAO_S:
        problemas.append(f"duração {info.duracao_s:.2f} s (esperado {esperado_s:.2f} s)")
    if problemas:
        raise ErroRender("O vídeo final saiu diferente do esperado: " + ", ".join(problemas))


def renderizar(
    plano: PlanoEdicao,
    clipes: Mapping[int, Path],
    destino: Path,
    *,
    espec: EspecificacaoVideo,
    registro: Registro,
    idioma: str | None,
    pasta_modelos: Path,
    rodada_id: int | None = None,
    post_id: int | None = None,
    manter_trabalho: bool = False,
    transcritor: Transcritor | None = None,
) -> Entrega:
    ffmpeg, ffprobe = exigir_ffmpeg()
    destino.mkdir(parents=True, exist_ok=True)
    trabalho = destino / "trabalho"
    trabalho.mkdir(exist_ok=True)
    avisos: list[str] = []

    infos = {cid: inspecionar(caminho, ffprobe) for cid, caminho in clipes.items()}
    problemas = verificar_contra_clipes(plano, {cid: i.duracao_s for cid, i in infos.items()})
    if problemas:
        raise PlanoInvalido(problemas)

    # Passagem 1
    p1 = filtros.argumentos_passagem_1(plano, clipes, infos, espec)
    (trabalho / filtros.NOME_SCRIPT).write_text(p1.filtergraph, encoding="utf-8")
    try:
        executar([ffmpeg, *p1.args], cwd=trabalho)
    except ErroFfmpeg as e:
        registro.erro(
            "A montagem dos cortes falhou.",
            e,
            detalhe={"ffmpeg": e.saida_erro},
            etapa=ETAPA,
            rodada_id=rodada_id,
            post_id=post_id,
        )
        raise ErroRender("A montagem dos cortes do vídeo falhou.") from e
    registro.registrar(
        "etapa",
        "Cortes e enquadramento montados.",
        etapa=ETAPA,
        rodada_id=rodada_id,
        post_id=post_id,
    )

    # Transcrição do áudio já cortado
    transcricao: Transcricao | None = None
    estado: EstadoLegendas = "desligadas"
    palavras: tuple[Palavra, ...] = ()
    if plano.legendas.ativas:
        wav = trabalho / "whisper.wav"
        executar([ffmpeg, *filtros.argumentos_wav_para_whisper()], cwd=trabalho)
        try:
            if transcritor is not None:
                resultado = transcritor(wav)
            else:
                resultado = transcrever(
                    wav, idioma=idioma, registro=registro, pasta_modelos=pasta_modelos,
                    rodada_id=rodada_id, post_id=post_id,
                )  # fmt: skip
            transcricao = resultado.valor
            transcricao = Transcricao(
                limitar_ao_video(transcricao.palavras, plano.duracao_s),
                transcricao.idioma,
                transcricao.servico,
            )
            estado = "sem_fala" if transcricao.sem_fala else "ok"
            if estado == "sem_fala":
                avisos.append("O vídeo não tem fala reconhecível; saiu sem legendas.")
            palavras = transcricao.palavras
        except TodosFalharam as e:
            estado = "indisponiveis"
            avisos.append("As legendas não puderam ser geradas: o serviço de legenda falhou.")
            registro.erro(
                "Nenhum serviço de legenda funcionou; o vídeo sai sem legendas.",
                e,
                etapa=ETAPA,
                rodada_id=rodada_id,
                post_id=post_id,
            )

    # Passagem 2
    com_ass = legendas.tem_eventos(plano, palavras)
    if com_ass:
        (trabalho / filtros.ARQUIVO_ASS).write_text(
            legendas.gerar_ass(plano, palavras, espec), encoding="utf-8"
        )
        chaves: set[str] = {t.estilo.fonte for t in plano.textos} | {plano.legendas.estilo.fonte}
        _, faltando = preparar_pasta_fontes(trabalho, chaves)
        if faltando:
            avisos.append(
                f"Fontes não encontradas nesta máquina (usada a padrão): {', '.join(faltando)}."
            )
            registro.registrar(
                "etapa",
                "Algumas fontes não existem nesta máquina.",
                detalhe={"fontes": faltando},
                etapa=ETAPA,
                rodada_id=rodada_id,
                post_id=post_id,
            )
    try:
        executar(
            [ffmpeg, *filtros.argumentos_passagem_2(com_ass=com_ass, espec=espec)], cwd=trabalho
        )
    except ErroFfmpeg as e:
        registro.erro(
            "A finalização do vídeo falhou.",
            e,
            detalhe={"ffmpeg": e.saida_erro},
            etapa=ETAPA,
            rodada_id=rodada_id,
            post_id=post_id,
        )
        raise ErroRender("A finalização do vídeo (textos e legendas) falhou.") from e
    video = destino / "video.mp4"
    shutil.move(str(trabalho / filtros.VIDEO_FINAL), str(video))
    info = inspecionar(video, ffprobe)
    _conferir_saida(info, plano.duracao_s, espec)
    registro.registrar(
        "etapa",
        "Vídeo final codificado.",
        detalhe={"duracao_s": info.duracao_s, "legendas": estado},
        etapa=ETAPA,
        rodada_id=rodada_id,
        post_id=post_id,
    )

    capa = gerar_capa(video, plano.capa, trabalho, destino / "capa.jpg", espec, ffmpeg)
    if not manter_trabalho:
        shutil.rmtree(trabalho, ignore_errors=True)
    return Entrega(video, capa, info.duracao_s, estado, transcricao, info, avisos)
