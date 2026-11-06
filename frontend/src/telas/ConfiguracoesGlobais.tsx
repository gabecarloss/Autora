import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { ConexaoAgente } from "../componentes/ConexaoAgente";
import { NiveisAgente } from "../componentes/NiveisAgente";

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

export function ConfiguracoesGlobais() {
  return (
    <section>
      <h1>Configurações globais</h1>
      <p className="explicacao">Valem para todos os perfis.</p>
      <ConexaoAgente />
      <NiveisAgente />
      <ModoCriacao />
    </section>
  );
}
