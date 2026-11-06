import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { ConexaoAgente } from "../componentes/ConexaoAgente";
import { NiveisAgente } from "../componentes/NiveisAgente";
import { PASTA_DADOS } from "../textos";

function ModoCriacao() {
  const qc = useQueryClient();
  const sistema = useQuery({ queryKey: ["sistema"], queryFn: api.sistema });
  const mudar = useMutation({
    mutationFn: api.definirModo,
    onSuccess: (novo) => qc.setQueryData(["sistema"], novo),
  });
  const modo = sistema.data?.modo;

  return (
    <div className="cartao">
      <h2>Criação de posts</h2>
      <p className="explicacao">
        Na criação automática, cada perfil cria os posts todo dia no horário dele. Na manual, nada
        roda sozinho: você entra no perfil e pede “Criar agora”. Para parar por um tempo sem mudar
        nada, use “Pausar” na barra lateral.
      </p>
      {modo && (
        <fieldset disabled={mudar.isPending}>
          <legend>Modo</legend>
          <label className="opcao">
            <input
              type="radio"
              name="modo"
              checked={modo === "automatico"}
              onChange={() => mudar.mutate("automatico")}
            />
            Automática
          </label>
          <label className="opcao">
            <input
              type="radio"
              name="modo"
              checked={modo === "manual"}
              onChange={() => mudar.mutate("manual")}
            />
            Manual
          </label>
        </fieldset>
      )}
    </div>
  );
}

function PastaDados() {
  const sistema = useQuery({ queryKey: ["sistema"], queryFn: api.sistema });
  const s = sistema.data;
  return (
    <div className="cartao">
      <h2>{PASTA_DADOS.titulo}</h2>
      <p className="explicacao">{PASTA_DADOS.explicacao}</p>
      {sistema.isLoading && <p>Carregando…</p>}
      {sistema.isError && <p className="alerta">{sistema.error.message}</p>}
      {s && (
        <p>
          <code>{s.pasta_dados}</code>
          <span className="detalhe"> {PASTA_DADOS.origem[s.origem_pasta_dados]}</span>
        </p>
      )}
    </div>
  );
}

export function ConfiguracoesGlobais() {
  return (
    <section>
      <h1>Configurações globais</h1>
      <p className="explicacao">Valem para todos os perfis.</p>
      <ConexaoAgente />
      <NiveisAgente />
      <ModoCriacao />
      <PastaDados />
    </section>
  );
}
