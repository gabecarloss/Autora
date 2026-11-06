"""post.md do TikTok (seção 2 do briefing): tudo que o usuário precisa na hora de postar.

Só este arquivo sabe como o TikTok trata som, capa e descrição. Texto em linguagem
direta, sem jargão; o custo não aparece aqui (seção 7.4).
"""

from __future__ import annotations

from autora.plataformas.base import PacotePost

_LEGENDAS = {
    "ok": "Legendas sincronizadas com a fala, geradas automaticamente.",
    "sem_fala": "O vídeo não tem fala; saiu sem legendas.",
    "indisponiveis": "As legendas não puderam ser geradas (o serviço de legenda falhou); "
    "o vídeo saiu sem legendas.",
    "desligadas": "O agente decidiu não usar legendas neste post.",
}


def _lista(itens: list[str]) -> str:
    return "\n".join(f"- {i}" for i in itens) if itens else "- (nenhum)"


def _secao_som(som: dict[str, object] | None) -> str:
    linhas = [
        "## Som",
        "",
        "A música NÃO está embutida no vídeo: adicione no app do TikTok na hora de postar.",
    ]
    if not som:
        linhas.append("- O agente não sugeriu som para este post. Escolha no app.")
        linhas.append("- Sincronia: sem sincronia (ritmo próprio do vídeo).")
        return "\n".join(linhas)
    nome = som.get("nome")
    fonte = som.get("fonte")
    linhas += [
        f"- Som: {nome if nome else 'a escolher no app (sugestão sem nome verificado)'}",
        f"- Onde foi localizado: {fonte if fonte else 'não localizado'}",
        f"- Função no vídeo: {som.get('funcao_no_video', '')}",
        f"- Volume: {som.get('volume', '')} · Cobertura: {som.get('cobertura', '')}",
        f"- Motivo: {som.get('motivo', '')}",
        "- Sincronia: sem sincronia (a análise do som entra em versão futura).",
    ]
    if not som.get("verificado"):
        linhas.append("- Atenção: sugestão não verificada; confirme se o som existe e combina.")
    return "\n".join(linhas)


def gerar_post_md(p: PacotePost, nome_plataforma: str = "TikTok") -> str:
    alternativas = _lista(p.alternativas_gancho)
    hashtags = " ".join(p.hashtags)
    elementos = _lista(
        [f"{e.get('tipo', '')}: {e.get('descricao', '')}" for e in p.elementos_autorais]
    )
    motivos = _lista([f"{campo}: {motivo}" for campo, motivo in p.motivos.items()])
    duracao = f"{p.duracao_s:.1f} s" if p.duracao_s is not None else "—"
    partes: list[str | None] = [
        f"# Post para o {nome_plataforma}" + (f" · {p.nome_perfil}" if p.nome_perfil else ""),
        "",
        f"Criado em {p.criado_em}." if p.criado_em else None,
        "",
        "## Gancho (título)",
        "",
        f"**{p.gancho}**",
        "",
        "Alternativas:",
        alternativas,
        "",
        "## Descrição",
        "",
        p.descricao,
        "",
        "## Hashtags",
        "",
        hashtags,
        "",
        "## Horário sugerido",
        "",
        f"- {p.horario_sugerido}",
        f"- Motivo: {p.motivo_horario}",
        "",
        _secao_som(p.som),
        "",
        "## Capa",
        "",
        f"- Quadro: segundo {p.capa_segundo:.1f} do vídeo final (ver capa.jpg)",
        f"- Texto: {p.capa_texto}",
        "",
        "## Como foi feito",
        "",
        f"- Formato: {p.formato}",
        f"- Tema: {p.tema}" if p.tema else None,
        f"- Ideia: {p.conceito}" if p.conceito else None,
        f"- Origem do material: {p.fonte_material}",
        f"- Voz: {p.voz or 'sem narração'}",
        f"- Estilo de edição: versão {p.versao_estilo if p.versao_estilo is not None else '—'}",
        f"- Duração: {duracao}",
        f"- Legendas: {_LEGENDAS.get(p.legendas, p.legendas)}",
        f"- Referência (adaptação): {p.referencia}" if p.referencia else None,
        f"- Confiança do agente: {p.confianca}" if p.confianca else None,
        "",
        "## Elementos autorais",
        "",
        elementos,
        "",
        "## Motivo de cada escolha",
        "",
        motivos,
    ]
    if p.nao_sei:
        partes += ["", "## O que o agente não sabe ainda", "", _lista(p.nao_sei)]
    if p.avisos:
        partes += ["", "## Avisos", "", _lista(p.avisos)]
    texto = "\n".join(linha for linha in partes if linha is not None)
    # Linhas vazias que vieram de campos ausentes não devem virar parágrafos duplos.
    while "\n\n\n" in texto:
        texto = texto.replace("\n\n\n", "\n\n")
    return texto.strip() + "\n"
