"""Abre o Autora: servidor local + janela própria (pywebview).

`uv run autora-app`            abre a janela
`uv run autora-app --dev`      só o servidor, imprime o endereço de entrada (para o Vite)
"""

from __future__ import annotations

import argparse
import logging
import socket
import sys
import threading
import time

import uvicorn

from autora.api.main import criar_app
from autora.api.seguranca import novo_token
from autora.backup.backup import backup_diario
from autora.config.global_config import pasta_dados
from autora.plataformas.tiktok import registrar_padrao
from autora.registro.log import registro_global

PORTA_DEV = 8765


def _porta_livre() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def main() -> None:
    parser = argparse.ArgumentParser(prog="autora-app")
    parser.add_argument("--dev", action="store_true", help="modo desenvolvimento (sem janela)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    registrar_padrao()
    dados = pasta_dados()
    reg = registro_global(dados)
    reg.registrar("sistema", "App aberto.")
    backup_diario(dados)

    token = novo_token()
    porta = PORTA_DEV if args.dev else _porta_livre()
    app = criar_app(dados, token, desenvolvimento=args.dev)
    config = uvicorn.Config(app, host="127.0.0.1", port=porta, log_level="warning")
    servidor = uvicorn.Server(config)
    endereco = f"http://127.0.0.1:{porta}/entrar?s={token}"

    if args.dev:
        sys.stdout.write(f"Servidor de desenvolvimento. Entre por:\n{endereco}\n")
        sys.stdout.write(f"Com o Vite: http://localhost:5173/entrar?s={token}\n")
        sys.stdout.flush()
        servidor.run()
        return

    thread = threading.Thread(target=servidor.run, daemon=True)
    thread.start()
    for _ in range(100):
        if servidor.started:
            break
        time.sleep(0.05)

    import webview

    webview.create_window("Autora", endereco, width=1280, height=820, min_size=(900, 600))
    try:
        webview.start(private_mode=True)
    finally:
        servidor.should_exit = True
        thread.join(timeout=5)
        reg.registrar("sistema", "App fechado.")


if __name__ == "__main__":
    main()
