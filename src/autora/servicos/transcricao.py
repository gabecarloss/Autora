"""Transcrição com Whisper local (seção 7.3), palavra por palavra, com reserva.

Cadeia: placa de vídeo (modelo grande) → processador (modelo pequeno). Se as duas
falharem, quem chama segue sem legendas (falha isolada). Sem fala não é falha.
`faster_whisper` e `ctranslate2` são importados dentro das funções: o app abre mesmo sem
eles, e a ausência vira falha da opção, não erro de importação.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Final, Literal

from autora.registro.log import Registro
from autora.servicos.cadeia import Opcao, Resultado, executar_com_reserva

# PROVISÓRIO: modelos padrão até medir qualidade e tempo com vídeo real.
MODELO_GPU_PADRAO: Final = "large-v3"
MODELO_CPU_PADRAO: Final = "small"
Dispositivo = Literal["cuda", "cpu"]


@dataclass(frozen=True)
class Palavra:
    texto: str
    inicio_s: float
    fim_s: float
    confianca: float


@dataclass(frozen=True)
class Transcricao:
    palavras: tuple[Palavra, ...]
    idioma: str | None
    servico: str

    @property
    def sem_fala(self) -> bool:
        return not self.palavras

    def texto(self) -> str:
        return " ".join(p.texto for p in self.palavras)


def pasta_modelos(dados: Path) -> Path:
    """Modelos ficam na pasta de dados (desta máquina), nunca dentro de um perfil."""
    return dados / "modelos" / "whisper"


def ha_gpu() -> bool:
    try:
        import ctranslate2
    except Exception:
        return False
    try:
        return int(ctranslate2.get_cuda_device_count()) > 0
    except Exception:
        return False


@lru_cache(maxsize=4)
def _modelo(nome: str, dispositivo: str, compute_type: str, pasta: str) -> Any:
    from faster_whisper import WhisperModel

    return WhisperModel(nome, device=dispositivo, compute_type=compute_type, download_root=pasta)


def transcrever_whisper(
    wav: Path,
    *,
    idioma: str | None,
    modelo: str,
    dispositivo: Dispositivo,
    compute_type: str,
    pasta_modelos: Path,
) -> Transcricao:
    pasta_modelos.mkdir(parents=True, exist_ok=True)
    m = _modelo(modelo, dispositivo, compute_type, str(pasta_modelos))
    segmentos, info = m.transcribe(
        str(wav),
        language=idioma,
        word_timestamps=True,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 300},
        beam_size=5,
        condition_on_previous_text=False,
    )
    palavras: list[Palavra] = []
    for seg in segmentos:  # gerador: a transcrição acontece aqui
        for w in seg.words or []:
            texto = str(w.word).strip()
            if texto:
                palavras.append(
                    Palavra(
                        texto,
                        round(float(w.start), 3),
                        round(float(w.end), 3),
                        float(w.probability),
                    )
                )
    return Transcricao(tuple(palavras), getattr(info, "language", None), f"whisper-{dispositivo}")


def transcrever(
    wav: Path,
    *,
    idioma: str | None,
    registro: Registro,
    pasta_modelos: Path,
    modelo_gpu: str = MODELO_GPU_PADRAO,
    modelo_cpu: str = MODELO_CPU_PADRAO,
    etapa: str | None = "edicao",
    rodada_id: int | None = None,
    post_id: int | None = None,
) -> Resultado[Transcricao]:
    """Cadeia principal → reserva. Levanta TodosFalharam se nada funcionar."""
    opcoes: list[Opcao[Transcricao]] = []
    if ha_gpu():
        opcoes.append(
            Opcao(
                "whisper-gpu",
                "legendas pela placa de vídeo",
                lambda: transcrever_whisper(
                    wav,
                    idioma=idioma,
                    modelo=modelo_gpu,
                    dispositivo="cuda",
                    compute_type="float16",
                    pasta_modelos=pasta_modelos,
                ),
            )
        )
    opcoes.append(
        Opcao(
            "whisper-cpu",
            "legendas pelo processador",
            lambda: transcrever_whisper(
                wav,
                idioma=idioma,
                modelo=modelo_cpu,
                dispositivo="cpu",
                compute_type="int8",
                pasta_modelos=pasta_modelos,
            ),
        )
    )
    return executar_com_reserva(
        "legendas", opcoes, registro, etapa=etapa, rodada_id=rodada_id, post_id=post_id
    )


def limitar_ao_video(palavras: Sequence[Palavra], duracao_s: float) -> tuple[Palavra, ...]:
    """Corta palavras fora do vídeo e garante fim > início (mínimo 0,15 s)."""
    saida: list[Palavra] = []
    for p in palavras:
        if p.inicio_s >= duracao_s:
            continue
        fim = min(max(p.fim_s, p.inicio_s + 0.15), duracao_s)
        saida.append(Palavra(p.texto, p.inicio_s, round(fim, 3), p.confianca))
    return tuple(saida)
