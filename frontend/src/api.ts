// Acesso ao servidor local. A sessão vai no cookie (HttpOnly) definido em /entrar.

export type EstadoSistema = {
  estado: "ligado" | "pausado" | "manual";
  modo: "automatico" | "manual";
  pausado: boolean;
};

export type Etapa =
  "estudo" | "conceito" | "plano" | "revisor" | "verificacoes" | "indexacao" | "teste";

export type Nivel = "automatico" | "rapido" | "equilibrado" | "maximo";

export type EstadoAgente = {
  tipo: "nenhuma" | "assinatura" | "chave";
  conectado_em: string | null;
  ultima_verificacao: string | null;
  ultimo_resultado: "ok" | "falhou" | null;
  ultimo_erro: string | null;
  programa_instalado: boolean;
  versao_programa: string | null;
  niveis: Record<Etapa, Nivel>;
};

export type ResultadoTeste = {
  ok: boolean;
  mensagem: string;
  resposta: string | null;
  duracao_ms: number | null;
  custo_usd: number | null;
};

export type Criacao = {
  estado: "ocioso" | "criando" | "pronto" | "falhou";
  mensagem: string | null;
  pasta_saida: string | null;
  iniciado_em: string | null;
  terminado_em: string | null;
};

export type ResumoPerfil = {
  slug: string;
  nome: string;
  pausado: boolean;
  estado: "ok" | "problema";
  criacao: Criacao;
};

export class ErroServidor extends Error {
  constructor(
    public readonly status: number,
    mensagem: string,
  ) {
    super(mensagem);
  }
}

async function pedir<T>(caminho: string, metodo = "GET", corpo?: unknown): Promise<T> {
  const init: RequestInit = { method: metodo, credentials: "same-origin" };
  if (corpo !== undefined) {
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(corpo);
  }
  const r = await fetch(caminho, init);
  if (!r.ok) {
    let mensagem = "Algo deu errado. Tente de novo.";
    try {
      const j = (await r.json()) as { detail?: string; erro?: string };
      mensagem = j.detail ?? j.erro ?? mensagem;
    } catch {
      // resposta sem JSON: mantém a mensagem padrão
    }
    throw new ErroServidor(r.status, mensagem);
  }
  return (await r.json()) as T;
}

export const api = {
  sistema: () => pedir<EstadoSistema>("/api/sistema"),
  pausar: () => pedir<EstadoSistema>("/api/sistema/pausar", "POST"),
  ligar: () => pedir<EstadoSistema>("/api/sistema/ligar", "POST"),
  definirModo: (modo: EstadoSistema["modo"]) =>
    pedir<EstadoSistema>("/api/sistema/modo", "PUT", { modo }),

  agente: () => pedir<EstadoAgente>("/api/agente"),
  instalarAgente: () => pedir<EstadoAgente>("/api/agente/instalar", "POST"),
  abrirLogin: () => pedir<{ aberto: boolean }>("/api/agente/abrir-login", "POST"),
  conectarAssinatura: (token: string) =>
    pedir<ResultadoTeste>("/api/agente/conectar/assinatura", "POST", { token }),
  conectarChave: (chave: string) =>
    pedir<ResultadoTeste>("/api/agente/conectar/chave", "POST", { chave }),
  testarAgente: () => pedir<ResultadoTeste>("/api/agente/testar", "POST"),
  desconectarAgente: () =>
    pedir<EstadoAgente>("/api/agente/desconectar", "POST", { confirmar: true }),
  definirNiveis: (niveis: Partial<Record<Etapa, Nivel>>) =>
    pedir<EstadoAgente>("/api/agente/niveis", "PUT", { niveis }),

  perfis: () => pedir<ResumoPerfil[]>("/api/perfis"),
  criarPerfil: (slug: string, nome: string) =>
    pedir<ResumoPerfil>("/api/perfis", "POST", { slug, nome }),
  criarAgora: (slug: string) =>
    pedir<Criacao>(`/api/perfis/${encodeURIComponent(slug)}/criar-agora`, "POST"),
};
