from __future__ import annotations

import json
import shutil
from collections.abc import Iterator
from fractions import Fraction
from pathlib import Path
from typing import Any

import keyring
import pytest
from keyring.backend import KeyringBackend

from autora.agente.provedor import Pedido, Resposta
from autora.biblioteca import ficha as ficha_mod
from autora.biblioteca.ficha import registrar_pasta
from autora.config import segredos
from autora.edicao.ffmpeg import InfoVideo, localizar_ffmpeg
from autora.perfil.perfil import Perfil
from autora.plataformas.tiktok import registrar_padrao


class CofreEmMemoria(KeyringBackend):
    """Substitui o Cofre de Credenciais do Windows nos testes."""

    priority = 1  # type: ignore[assignment]

    def __init__(self) -> None:
        super().__init__()
        self.itens: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self.itens.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self.itens[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        if (service, username) not in self.itens:
            raise keyring.errors.PasswordDeleteError(username)
        del self.itens[(service, username)]


@pytest.fixture(autouse=True)
def cofre() -> Iterator[CofreEmMemoria]:
    anterior = keyring.get_keyring()
    c = CofreEmMemoria()
    keyring.set_keyring(c)
    segredos._invalidar_cache()
    yield c
    keyring.set_keyring(anterior)
    segredos._invalidar_cache()


@pytest.fixture(autouse=True, scope="session")
def plataformas_registradas() -> None:
    registrar_padrao()


@pytest.fixture
def dados(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    raiz = tmp_path / "dados"
    raiz.mkdir()
    monkeypatch.setenv("AUTORA_DADOS", str(raiz))
    return raiz


RAIZ_REPO = Path(__file__).resolve().parents[1]


def secao_mandato_do_briefing() -> str:
    txt = (RAIZ_REPO / "BRIEFING.md").read_text(encoding="utf-8")
    ini = txt.index("### 3.1 O agente: mandato")
    fim = txt.index("\n---", ini)
    return txt[ini:fim].split("\n", 1)[1].strip("\n") + "\n"


# --- agente simulado -------------------------------------------------------------
class ProvedorFalso:
    """Agente simulado: respostas roteirizadas por etapa, na ordem em que foram
    programadas. Um item que é exceção é levantado no lugar de respondido."""

    nome = "falso"

    def __init__(
        self, erro: Exception | None = None, *, respostas: dict[str, list[Any]] | None = None
    ) -> None:
        self.erro = erro
        self.respostas: dict[str, list[Any]] = {k: list(v) for k, v in (respostas or {}).items()}
        self.pedidos: list[Pedido] = []

    def programar(self, etapa: str, *dados: Any) -> ProvedorFalso:
        self.respostas.setdefault(etapa, []).extend(dados)
        return self

    def chamar(self, pedido: Pedido) -> Resposta:
        self.pedidos.append(pedido)
        if self.erro:
            raise self.erro
        fila = self.respostas.get(pedido.etapa) or []
        dados = fila.pop(0) if fila else None
        if isinstance(dados, Exception):
            raise dados
        texto = json.dumps(dados, ensure_ascii=False) if dados is not None else "ok"
        return Resposta(texto, dados, "falso", 10, 5, 0, 0.01, 50)


@pytest.fixture
def provedor_falso() -> ProvedorFalso:
    return ProvedorFalso()


# --- respostas válidas de exemplo (dados de teste, não decisões criativas) ----------
def conceito_valido(ids: list[int]) -> dict[str, Any]:
    return {
        "raciocinio": {
            "sei_com_certeza": "O clipe mostra uma cena curta com uma virada no fim.",
            "estou_supondo": "Suponho que o público ri da expectativa quebrada; dá para checar "
            "nos comentários.",
            "o_melhor_criador_faria": "Cortaria direto na virada e colocaria um texto que muda "
            "o sentido.",
            "pode_dar_errado_e_como_percebo": "O texto pode entregar a piada cedo; a retenção "
            "nos 2 s iniciais mostra.",
            "motivo_da_escolha": "Material curto com virada pede texto narrativo e corte seco.",
        },
        "clipes_escolhidos": [
            {"clipe_id": i, "motivo": "Tem a virada mais clara entre os disponíveis."} for i in ids
        ],
        "formato": {
            "valor": "texto_narrativo",
            "motivo": "A graça precisa de um contexto que o clipe não dá sozinho.",
        },
        "descricao_formato": None,
        "fonte_material": "pasta",
        "tema": "expectativa quebrada",
        "conceito": "Um texto na tela cria uma expectativa séria e o clipe a derruba no corte "
        "final.",
        "gancho": {
            "valor": "ele jurou que dava certo",
            "motivo": "Cria expectativa específica sem entregar a virada.",
        },
        "alternativas_gancho": ["o plano era perfeito", "ninguém avisou ele"],
        "descricao_post": "quando a confiança é maior que o plano",
        "hashtags": ["#humor", "#deucerto", "#expectativa"],
        "horario_sugerido": {
            "valor": "não sei ainda",
            "motivo": "Sem estudo de horários ainda; conta nova sem métricas.",
        },
        "capa": {
            "valor": "DEU CERTO?",
            "motivo": "Pergunta curta que combina com a expectativa do gancho.",
        },
        "som": None,
        "elementos_autorais": [
            {
                "tipo": "narrativa_propria",
                "descricao": "Dois textos na tela que montam uma história antes da virada.",
                "como_verificar": "Roteiro com pelo menos dois textos de papel narrativa.",
            },
            {
                "tipo": "ritmo_proprio",
                "descricao": "Corte seco com aceleração no trecho de preparação.",
                "como_verificar": "Algum trecho com velocidade diferente de 1.",
            },
        ],
        "duracao_alvo_s": 4,
        "nao_sei": ["Não sei qual som está em alta esta semana."],
        "confianca": "media",
    }


def plano_valido(clipe_id: int, duracao_clipe_s: float = 3.0) -> dict[str, Any]:
    fim = round(min(duracao_clipe_s, 3.0), 3)
    return {
        "versao_esquema": 1,
        "versao_estilo": 1,
        "trechos": [
            {"clipe_id": clipe_id, "inicio_s": 0.0, "fim_s": fim, "velocidade": 1.0},
            {"clipe_id": clipe_id, "inicio_s": 0.0, "fim_s": fim, "velocidade": 2.0},
        ],
        "textos": [
            {
                "texto": "ele jurou que dava certo",
                "papel": "gancho",
                "inicio_s": 0.0,
                "fim_s": 1.5,
                "posicao": "topo",
            },
            {
                "texto": "passo 1: confiança",
                "papel": "narrativa",
                "inicio_s": 0.3,
                "fim_s": 2.0,
                "posicao": "centro",
            },
            {
                "texto": "passo 2: ...",
                "papel": "narrativa",
                "inicio_s": 2.0,
                "fim_s": 3.5,
                "posicao": "centro",
            },
        ],
        "legendas": {"ativas": True, "modo": "palavra", "posicao": "base"},
        "capa": {"segundo": 1.0, "texto": "DEU CERTO?"},
        "audio": {"manter_original": True, "volume": 1.0},
        "motivos": {
            "ritmo": "Trecho repetido acelerado para fechar a piada mais rápido.",
            "enquadramento": "Clipe vertical, recorte central sem perda.",
            "textos": "Texto de contexto no topo e narrativa no centro para não cobrir a ação.",
            "legendas": "Palavra por palavra porque a fala é curta e rápida.",
        },
    }


# --- ffmpeg real e clipes sintéticos -----------------------------------------------
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    if localizar_ffmpeg() is not None:
        return
    pular = pytest.mark.skip(reason="ffmpeg não encontrado nesta máquina")
    for item in items:
        if "ffmpeg" in item.keywords:
            item.add_marker(pular)


@pytest.fixture(scope="session")
def ffmpeg() -> tuple[Path, Path]:
    par = localizar_ffmpeg()
    if par is None:
        pytest.skip("ffmpeg não encontrado nesta máquina")
    return par


@pytest.fixture(scope="session")
def clipes_sinteticos(
    tmp_path_factory: pytest.TempPathFactory, ffmpeg: tuple[Path, Path]
) -> dict[str, Path]:
    """vertical 3 s 30 fps 48 kHz; horizontal 4 s 25 fps 44,1 kHz; mudo 2 s sem áudio."""
    from autora.edicao.sintetico import gerar_clipe_sintetico

    pasta = tmp_path_factory.mktemp("clipes")
    return {
        "vertical": gerar_clipe_sintetico(
            pasta / "vertical.mp4", largura=1080, altura=1920, duracao_s=3, fps=30
        ),
        "horizontal": gerar_clipe_sintetico(
            pasta / "horizontal.mp4",
            largura=1920,
            altura=1080,
            duracao_s=4,
            fps=25,
            taxa_audio=44100,
            frequencia_hz=660,
        ),
        "mudo": gerar_clipe_sintetico(
            pasta / "mudo.mp4", largura=1080, altura=1920, duracao_s=2, com_audio=False
        ),
    }


DESCRICOES_SINTETICAS = {
    "vertical.mp4": "Padrão de teste vertical com barras coloridas e um tom contínuo.",
    "horizontal.mp4": "Padrão de teste horizontal com contador de quadros e um tom mais agudo.",
    "mudo.mp4": "Padrão de teste vertical curto, sem som.",
}


@pytest.fixture
def perfil_sintetico(dados: Path, clipes_sinteticos: dict[str, Path], tmp_path: Path) -> Perfil:
    """Perfil "teste" com uma pasta de clipes sintéticos reais vinculada (precisa de ffmpeg)."""
    pasta = tmp_path / "biblioteca_sintetica"
    pasta.mkdir()
    for caminho in clipes_sinteticos.values():
        shutil.copy(caminho, pasta / caminho.name)
    (pasta / "descricoes.json").write_text(
        json.dumps(DESCRICOES_SINTETICAS, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    perfil = Perfil.criar(dados, "teste", "Perfil de teste")
    registrar_pasta(perfil, dados, pasta)
    return perfil


@pytest.fixture
def perfil_com_clipes_falsos(
    dados: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Perfil:
    """Perfil com três "vídeos" vazios e uma sondagem simulada: roda sem ffmpeg.

    a.mp4 vertical 3 s com áudio; b.mp4 horizontal 4 s com áudio; c.mp4 vertical 2 s mudo.
    """
    pasta = tmp_path / "biblioteca_falsa"
    pasta.mkdir()
    infos = {
        "a.mp4": InfoVideo(1080, 1920, Fraction(30), "h264", "yuv420p", "aac", 48000, 2, 3.0),
        "b.mp4": InfoVideo(1920, 1080, Fraction(25), "h264", "yuv420p", "aac", 44100, 2, 4.0),
        "c.mp4": InfoVideo(1080, 1920, Fraction(30), "h264", "yuv420p", None, None, None, 2.0),
    }
    for nome in infos:
        (pasta / nome).write_bytes(b"")
    (pasta / "descricoes.json").write_text(
        json.dumps({"a.mp4": "Cena A", "b.mp4": "Cena B", "c.mp4": "Cena C"}), encoding="utf-8"
    )
    monkeypatch.setattr(
        ficha_mod, "inspecionar", lambda caminho, ffprobe=None: infos[Path(caminho).name]
    )
    perfil = Perfil.criar(dados, "teste", "Perfil de teste")
    registrar_pasta(perfil, dados, pasta)
    return perfil
