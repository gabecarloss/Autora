import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { api } from "../api";

function sugerirNomeInterno(nome: string): string {
  return nome
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 40);
}

export function Perfis() {
  const qc = useQueryClient();
  const perfis = useQuery({ queryKey: ["perfis"], queryFn: api.perfis });
  const [nome, setNome] = useState("");
  const criar = useMutation({
    mutationFn: () => api.criarPerfil(sugerirNomeInterno(nome), nome.trim()),
    onSuccess: () => {
      setNome("");
      void qc.invalidateQueries({ queryKey: ["perfis"] });
    },
  });

  function enviar(e: FormEvent) {
    e.preventDefault();
    if (sugerirNomeInterno(nome)) criar.mutate();
  }

  return (
    <section>
      <h1>Perfis</h1>
      <p className="explicacao">
        Cada perfil é uma conta, operada por um agente próprio que estuda o nicho, cria os posts e
        aprende com os resultados. Perfis não compartilham memória.
      </p>

      {perfis.isLoading && <p>Carregando…</p>}
      {perfis.data && perfis.data.length === 0 && <p>Nenhum perfil ainda.</p>}
      {perfis.data && perfis.data.length > 0 && (
        <ul className="lista-perfis">
          {perfis.data.map((p) => (
            <li key={p.slug}>
              <strong>{p.nome}</strong>
              {p.estado === "problema" && (
                <span className="alerta"> · a configuração deste perfil está com problema</span>
              )}
              {p.pausado && <span> · pausado</span>}
            </li>
          ))}
        </ul>
      )}

      <form className="cartao" onSubmit={enviar}>
        <h2>Novo perfil</h2>
        <p className="explicacao">
          Por enquanto só o nome. As demais perguntas (nicho, idioma, pastas, quantidade de posts)
          entram com a tela de boas-vindas do perfil.
        </p>
        <label>
          Nome
          <input value={nome} onChange={(e) => setNome(e.target.value)} maxLength={80} />
        </label>
        <button type="submit" disabled={!sugerirNomeInterno(nome) || criar.isPending}>
          Criar perfil
        </button>
        {criar.isError && <p className="alerta">{criar.error.message}</p>}
      </form>
    </section>
  );
}
