import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { App } from "./App";

const respostas: Record<string, unknown> = {
  "/api/sistema": {
    estado: "pausado",
    modo: "automatico",
    pausado: true,
    pasta_dados: "C:\\Exemplo\\dados",
    origem_pasta_dados: "variavel",
  },
  "/api/perfis": [],
  "/api/agente": {
    tipo: "nenhuma",
    conectado_em: null,
    ultima_verificacao: null,
    ultimo_resultado: null,
    ultimo_erro: null,
    programa_instalado: true,
    versao_programa: "x",
    niveis: {
      estudo: "automatico",
      conceito: "automatico",
      plano: "automatico",
      revisor: "automatico",
      verificacoes: "automatico",
      indexacao: "automatico",
      teste: "automatico",
    },
  },
};

const criacaoOciosa = {
  estado: "ocioso",
  mensagem: null,
  pasta_saida: null,
  iniciado_em: null,
  terminado_em: null,
};

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      const chave = init?.method === "POST" ? `POST ${url}` : url;
      const corpo = respostas[chave] ?? respostas[url];
      return Promise.resolve(new Response(JSON.stringify(corpo), { status: 200 }));
    }),
  );
});

afterEach(() => vi.unstubAllGlobals());

function montar(rota: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[rota]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("barra lateral tem os itens do briefing e mostra o estado do sistema", async () => {
  montar("/perfis");
  for (const item of ["Perfis", "Custo", "Técnico", "Configurações globais"]) {
    expect(screen.getByRole("link", { name: item })).toBeInTheDocument();
  }
  expect(await screen.findByText("Sistema: Pausado")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Ligar" })).toBeInTheDocument();
});

test("configurações globais mostram a conexão do agente", async () => {
  montar("/configuracoes");
  expect(await screen.findByText(/ainda não está conectado/)).toBeInTheDocument();
  // A assinatura é o caminho principal (decisão de 06/11/2026): vem marcada por padrão.
  expect(screen.getByRole("radio", { name: /Assinatura Claude/ })).toBeChecked();
  expect(screen.getByRole("radio", { name: /Chave de acesso/ })).not.toBeChecked();
  expect(screen.getByLabelText("Código de acesso da assinatura")).toHaveAttribute(
    "type",
    "password",
  );
  expect(await screen.findByText("Estudo do dia")).toBeInTheDocument();
});

test("configurações globais mostram a pasta de dados em uso e de onde veio", async () => {
  montar("/configuracoes");
  expect(await screen.findByText("C:\\Exemplo\\dados")).toBeInTheDocument();
  expect(screen.getByText(/variável de ambiente AUTORA_DADOS/)).toBeInTheDocument();
});

test("lista de perfis tem o botão Criar agora e mostra o estado da criação", async () => {
  respostas["/api/perfis"] = [
    { slug: "humor", nome: "Humor", pausado: false, estado: "ok", criacao: criacaoOciosa },
    {
      slug: "pets",
      nome: "Pets",
      pausado: false,
      estado: "ok",
      criacao: { ...criacaoOciosa, estado: "pronto", pasta_saida: "2026-11-06/1" },
    },
  ];
  respostas["POST /api/perfis/humor/criar-agora"] = { ...criacaoOciosa, estado: "criando" };
  montar("/perfis");
  const botoes = await screen.findAllByRole("button", { name: "Criar agora" });
  expect(botoes).toHaveLength(2);
  const [primeiro] = botoes;
  if (!primeiro) throw new Error("sem botão");
  expect(screen.getByText(/Pronto: 2026-11-06\/1/)).toBeInTheDocument();
  fireEvent.click(primeiro);
  await waitFor(() =>
    expect(fetch).toHaveBeenCalledWith(
      "/api/perfis/humor/criar-agora",
      expect.objectContaining({ method: "POST" }),
    ),
  );
  respostas["/api/perfis"] = [];
});
