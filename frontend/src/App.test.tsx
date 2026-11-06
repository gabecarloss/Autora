import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { App } from "./App";

const respostas: Record<string, unknown> = {
  "/api/sistema": { estado: "pausado", modo: "automatico", pausado: true },
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

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) =>
      Promise.resolve(new Response(JSON.stringify(respostas[url]), { status: 200 })),
    ),
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
  expect(screen.getByLabelText("Código de acesso da assinatura")).toHaveAttribute(
    "type",
    "password",
  );
  expect(await screen.findByText("Estudo do dia")).toBeInTheDocument();
});
