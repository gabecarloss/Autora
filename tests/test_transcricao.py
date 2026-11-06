"""Serviço de legenda (Whisper) com reserva: cadeia simulada e, com marcador, real."""

from __future__ import annotations

from pathlib import Path

import pytest

from autora.registro.log import Registro
from autora.servicos import transcricao
from autora.servicos.cadeia import TodosFalharam
from autora.servicos.transcricao import Palavra, Transcricao, limitar_ao_video
from autora.util.tempo import hoje


def _falso(resposta: Transcricao | Exception):
    def _f(wav: Path, **kw: object) -> Transcricao:
        if isinstance(resposta, Exception):
            raise resposta
        return resposta

    return _f


FALA = Transcricao((Palavra("oi", 0.1, 0.4, 0.9),), "pt", "whisper-cpu")


def test_gpu_falha_e_processador_assume_com_frase_no_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chamadas: list[str] = []

    def whisper(wav: Path, *, dispositivo: str, **kw: object) -> Transcricao:
        chamadas.append(dispositivo)
        if dispositivo == "cuda":
            raise RuntimeError("sem cuBLAS")
        return FALA

    monkeypatch.setattr(transcricao, "ha_gpu", lambda: True)
    monkeypatch.setattr(transcricao, "transcrever_whisper", whisper)
    reg = Registro(tmp_path / "logs", "t")
    r = transcricao.transcrever(
        tmp_path / "a.wav", idioma="pt", registro=reg, pasta_modelos=tmp_path
    )
    assert r.valor == FALA and r.usado == "whisper-cpu" and r.reserva is True
    assert chamadas == ["cuda", "cpu"]
    msgs = [e["mensagem"] for e in reg.ler_dia(hoje())]
    assert (
        "O serviço de legendas (legendas pela placa de vídeo) falhou e o legendas pelo "
        "processador vai assumir." in msgs
    )


def test_sem_gpu_so_o_processador_e_tentado(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chamadas: list[str] = []

    def whisper(wav: Path, *, dispositivo: str, **kw: object) -> Transcricao:
        chamadas.append(dispositivo)
        return FALA

    monkeypatch.setattr(transcricao, "ha_gpu", lambda: False)
    monkeypatch.setattr(transcricao, "transcrever_whisper", whisper)
    r = transcricao.transcrever(
        tmp_path / "a.wav",
        idioma=None,
        registro=Registro(tmp_path / "logs", "t"),
        pasta_modelos=tmp_path,
    )
    assert chamadas == ["cpu"] and r.reserva is False


def test_todos_falham_levanta_todos_falharam(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(transcricao, "ha_gpu", lambda: False)
    monkeypatch.setattr(
        transcricao, "transcrever_whisper", _falso(RuntimeError("modelo não baixado"))
    )
    with pytest.raises(TodosFalharam):
        transcricao.transcrever(
            tmp_path / "a.wav",
            idioma=None,
            registro=Registro(tmp_path / "logs", "t"),
            pasta_modelos=tmp_path,
        )


def test_transcricao_sem_fala_e_texto() -> None:
    assert Transcricao((), None, "x").sem_fala is True
    t = Transcricao((Palavra("a", 0, 0.1, 1), Palavra("b", 0.2, 0.3, 1)), "pt", "x")
    assert t.sem_fala is False and t.texto() == "a b"


def test_limitar_ao_video_corta_e_garante_duracao_minima() -> None:
    palavras = [Palavra("a", 0.0, 0.0, 1), Palavra("b", 1.0, 2.5, 1), Palavra("c", 3.0, 3.5, 1)]
    saida = limitar_ao_video(palavras, 2.0)
    assert [p.texto for p in saida] == ["a", "b"]
    assert saida[0].fim_s == 0.15 and saida[1].fim_s == 2.0


def test_ha_gpu_nao_quebra_sem_biblioteca(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    original = builtins.__import__

    def sem_ctranslate(nome: str, *a: object, **k: object) -> object:
        if nome == "ctranslate2":
            raise ImportError(nome)
        return original(nome, *a, **k)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", sem_ctranslate)
    assert transcricao.ha_gpu() is False


@pytest.mark.whisper
@pytest.mark.ffmpeg
def test_whisper_real_transcreve_fala_de_teste(tmp_path: Path) -> None:
    from autora.edicao.ffmpeg import extrair_audio_wav
    from autora.edicao.sintetico import gerar_clipe_sintetico
    from tests.edicao.fala import PALAVRAS_ESPERADAS, gerar_fala_wav

    fala = gerar_fala_wav(tmp_path / "fala.wav")
    if fala is None:
        pytest.skip("sintetizador de voz do Windows indisponível")
    clipe = gerar_clipe_sintetico(tmp_path / "fala.mp4", duracao_s=6, audio_wav=fala)
    wav = extrair_audio_wav(clipe, tmp_path / "whisper.wav")
    t = transcricao.transcrever_whisper(
        wav, idioma="pt", modelo=transcricao.MODELO_CPU_PADRAO, dispositivo="cpu",
        compute_type="int8", pasta_modelos=tmp_path / "modelos",
    )  # fmt: skip
    texto = t.texto().lower()
    achadas = [p for p in PALAVRAS_ESPERADAS if p in texto]
    assert len(achadas) >= 2, texto
    assert all(p.fim_s > p.inicio_s for p in t.palavras)
