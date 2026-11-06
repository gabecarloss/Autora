import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { NavLink } from "react-router-dom";
import { api } from "../api";
import { ESTADO_SISTEMA } from "../textos";

const ITENS = [
  { para: "/perfis", rotulo: "Perfis" },
  { para: "/custo", rotulo: "Custo" },
  { para: "/tecnico", rotulo: "Técnico" },
  { para: "/configuracoes", rotulo: "Configurações globais" },
];

export function BarraLateral() {
  const qc = useQueryClient();
  const sistema = useQuery({ queryKey: ["sistema"], queryFn: api.sistema });
  const alternar = useMutation({
    mutationFn: () => (sistema.data?.pausado ? api.ligar() : api.pausar()),
    onSuccess: (novo) => qc.setQueryData(["sistema"], novo),
  });

  const estado = sistema.data?.estado;

  return (
    <nav className="barra-lateral" aria-label="Navegação principal">
      <div className="marca">Autora</div>
      <ul>
        {ITENS.map((i) => (
          <li key={i.para}>
            <NavLink to={i.para}>{i.rotulo}</NavLink>
          </li>
        ))}
      </ul>
      <div className="estado-sistema" aria-live="polite">
        {estado ? (
          <>
            <span className={`indicador indicador-${estado}`} aria-hidden="true" />
            <span>Sistema: {ESTADO_SISTEMA[estado]}</span>
            <button
              type="button"
              onClick={() => alternar.mutate()}
              disabled={alternar.isPending}
              title={
                sistema.data?.pausado
                  ? "Volta ao horário normal. O que ficou parado não é recuperado."
                  : "Suspende a criação automática e o estudo do dia. Nenhuma configuração muda. O botão “Criar agora” de cada perfil continua funcionando."
              }
            >
              {sistema.data?.pausado ? "Ligar" : "Pausar"}
            </button>
          </>
        ) : (
          <span>{sistema.isError ? "Sem conexão com o app" : "Carregando…"}</span>
        )}
      </div>
    </nav>
  );
}
