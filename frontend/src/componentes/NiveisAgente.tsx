import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Etapa, type Nivel } from "../api";
import { ETAPAS, NIVEIS } from "../textos";

export function NiveisAgente() {
  const qc = useQueryClient();
  const estado = useQuery({ queryKey: ["agente"], queryFn: api.agente });
  const salvar = useMutation({
    mutationFn: (mudanca: Partial<Record<Etapa, Nivel>>) => api.definirNiveis(mudanca),
    onSuccess: (novo) => qc.setQueryData(["agente"], novo),
  });

  const niveis = estado.data?.niveis;

  return (
    <div className="cartao">
      <h2>Nível do agente por etapa</h2>
      <p className="explicacao">
        Níveis mais altos pensam mais e gastam mais do limite da sua conta. O padrão é deixar o
        agente decidir; mude só se quiser economizar numa etapa ou caprichar em outra.
      </p>
      {niveis && (
        <table className="tabela">
          <tbody>
            {(Object.keys(ETAPAS) as Etapa[]).map((etapa) => (
              <tr key={etapa}>
                <th scope="row">
                  {ETAPAS[etapa].nome}
                  <div className="detalhe">{ETAPAS[etapa].explicacao}</div>
                </th>
                <td>
                  <select
                    aria-label={`Nível para ${ETAPAS[etapa].nome}`}
                    value={niveis[etapa]}
                    onChange={(ev) => salvar.mutate({ [etapa]: ev.target.value as Nivel })}
                    disabled={salvar.isPending}
                  >
                    {(Object.keys(NIVEIS) as Nivel[]).map((n) => (
                      <option key={n} value={n}>
                        {NIVEIS[n]}
                      </option>
                    ))}
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
