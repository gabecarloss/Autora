// Nomes da interface. Fonte: GLOSSARIO.md (seção 15.5 do briefing).
// A interface só usa estes nomes; nada de jargão técnico em texto visível.

import type { Criacao, Etapa, EstadoSistema, Nivel } from "./api";

export const ESTADO_SISTEMA: Record<EstadoSistema["estado"], string> = {
  ligado: "Ligado",
  pausado: "Pausado",
  manual: "Manual",
};

export const ETAPAS: Record<Etapa, { nome: string; explicacao: string }> = {
  estudo: {
    nome: "Estudo do dia",
    explicacao: "O agente pesquisa tendências, edição e estratégia do nicho.",
  },
  conceito: {
    nome: "Ideia do post",
    explicacao: "Escolhe formato, gancho, som e voz, e registra o motivo de cada escolha.",
  },
  plano: {
    nome: "Roteiro de edição",
    explicacao: "Descreve corte por corte o que o vídeo vai ter.",
  },
  revisor: {
    nome: "Revisor",
    explicacao: "Assiste como um espectador exigente, sem ter visto o roteiro.",
  },
  verificacoes: {
    nome: "Checagens",
    explicacao: "Confere se o post segue a missão do agente antes de ficar pronto.",
  },
  indexacao: {
    nome: "Organização da biblioteca",
    explicacao: "Analisa os vídeos da sua pasta. É a etapa de maior volume.",
  },
  teste: {
    nome: "Teste de conexão",
    explicacao: "Só confere se o agente está respondendo.",
  },
};

export const NIVEIS: Record<Nivel, string> = {
  automatico: "Deixar o agente decidir",
  rapido: "Rápido",
  equilibrado: "Equilibrado",
  maximo: "Máximo",
};

export const CRIAR_AGORA = "Criar agora";

export const CRIACAO: Record<Criacao["estado"], string> = {
  ocioso: "",
  criando: "Criando…",
  pronto: "Pronto",
  falhou: "Falhou",
};
