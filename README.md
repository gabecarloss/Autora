# Autora

Agente local que transforma uma biblioteca de vídeos em conteúdo autoral para
TikTok (e outras redes no futuro). A fonte da verdade do projeto é o
[BRIEFING.md](BRIEFING.md).

## Requisitos (Windows)

```powershell
winget install astral-sh.uv Gyan.FFmpeg OpenJS.NodeJS.LTS
uv python install 3.11
```

## Instalar

```powershell
uv sync
uv run pre-commit install
cd frontend; npm ci; npm run build; cd ..
```

## Abrir o app

```powershell
uv run autora-app
```

A conexão com o agente (assinatura Claude ou chave da API) é feita dentro do app,
em **Configurações globais → Agente**.

## Linha de comando

```powershell
uv run autora perfil criar humor --nome "Humor"
uv run autora perfil listar
uv run autora backup --perfil humor
```

## Testes

```powershell
uv run pytest                 # unidade (agente simulado)
uv run pytest -m agente       # integração com o agente real (precisa de conexão no app)
uv run pre-commit run --all-files
cd frontend; npm test; npm run lint
```

## Dados

Os dados ficam fora do repositório, em `%USERPROFILE%\Autora` (ou na pasta da
variável `AUTORA_DADOS`). Segredos ficam só no Cofre de Credenciais do Windows.
