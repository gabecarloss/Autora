"""Adaptador do TikTok (seção 2): especificação do vídeo e post.md. Som e Display API
entram nos passos 6 e 10. Só os pontos de montagem (app, cli, api) importam este pacote."""

from __future__ import annotations

from autora.plataformas.base import EspecificacaoVideo, PacotePost, registrar
from autora.plataformas.tiktok.post_md import gerar_post_md


class TikTok:
    nome = "tiktok"
    nome_amigavel = "TikTok"
    video = EspecificacaoVideo(
        largura=1080, altura=1920, fps=30, codec="h264", musica_embutida=False
    )

    def gerar_post_md(self, pacote: PacotePost) -> str:
        return gerar_post_md(pacote, self.nome_amigavel)


def registrar_padrao() -> None:
    registrar(TikTok())
