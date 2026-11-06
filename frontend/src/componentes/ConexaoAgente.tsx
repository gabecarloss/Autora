import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { api, type EstadoAgente, type ResultadoTeste } from "../api";

function data(iso: string | null): string {
  return iso ? new Date(iso).toLocaleString("pt-BR") : "—";
}

function Resultado({ r }: { r: ResultadoTeste }) {
  return (
    <div className={r.ok ? "resultado ok" : "resultado alerta"} role="status">
      <p>{r.mensagem}</p>
      {r.resposta && <blockquote>{r.resposta}</blockquote>}
      {r.ok && (
        <p className="detalhe">
          Tempo: {((r.duracao_ms ?? 0) / 1000).toFixed(1)} s
          {r.custo_usd != null && <> · custo equivalente: US$ {r.custo_usd.toFixed(4)}</>}
        </p>
      )}
    </div>
  );
}

function Situacao({ e }: { e: EstadoAgente }) {
  if (e.tipo === "nenhuma") {
    return <p className="alerta">O agente ainda não está conectado. Nada é criado sem ele.</p>;
  }
  const como = e.tipo === "assinatura" ? "a assinatura Claude" : "a chave de acesso";
  return (
    <p>
      Conectado com {como} desde {data(e.conectado_em)}. Última verificação:{" "}
      {data(e.ultima_verificacao)}
      {e.ultimo_resultado === "falhou" && (
        <span className="alerta"> — falhou: {e.ultimo_erro}</span>
      )}
    </p>
  );
}

export function ConexaoAgente() {
  const qc = useQueryClient();
  const estado = useQuery({ queryKey: ["agente"], queryFn: api.agente });
  const [forma, setForma] = useState<"assinatura" | "chave">("assinatura");
  const [codigo, setCodigo] = useState("");
  const [resultado, setResultado] = useState<ResultadoTeste | null>(null);
  const [confirmandoSaida, setConfirmandoSaida] = useState(false);

  const atualizar = () => void qc.invalidateQueries({ queryKey: ["agente"] });

  const instalar = useMutation({ mutationFn: api.instalarAgente, onSuccess: atualizar });
  const abrirLogin = useMutation({ mutationFn: api.abrirLogin });
  const conectar = useMutation({
    mutationFn: () =>
      forma === "assinatura" ? api.conectarAssinatura(codigo) : api.conectarChave(codigo),
    onSuccess: (r) => {
      setResultado(r);
      setCodigo(""); // nunca fica guardado na tela
      atualizar();
    },
  });
  const testar = useMutation({
    mutationFn: api.testarAgente,
    onSuccess: (r) => {
      setResultado(r);
      atualizar();
    },
  });
  const desconectar = useMutation({
    mutationFn: api.desconectarAgente,
    onSuccess: () => {
      setConfirmandoSaida(false);
      setResultado(null);
      atualizar();
    },
  });

  function enviar(e: FormEvent) {
    e.preventDefault();
    if (codigo.trim()) conectar.mutate();
  }

  const e = estado.data;

  return (
    <div className="cartao">
      <h2>Agente</h2>
      <p className="explicacao">
        O agente é quem estuda, cria e revisa os posts. Ele precisa de uma conta Claude. O código de
        acesso fica guardado no cofre de senhas do Windows, nunca em arquivo.
      </p>

      {estado.isLoading && <p>Carregando…</p>}
      {e && <Situacao e={e} />}

      {e && e.tipo !== "nenhuma" && (
        <div className="acoes">
          <button type="button" onClick={() => testar.mutate()} disabled={testar.isPending}>
            {testar.isPending ? "Testando…" : "Testar conexão"}
          </button>
          {!confirmandoSaida ? (
            <button type="button" className="secundario" onClick={() => setConfirmandoSaida(true)}>
              Desconectar
            </button>
          ) : (
            <span className="confirmacao">
              Sem conexão, nenhum perfil cria posts até você conectar de novo.
              <button
                type="button"
                className="perigo"
                onClick={() => desconectar.mutate()}
                disabled={desconectar.isPending}
              >
                Desconectar mesmo assim
              </button>
              <button
                type="button"
                className="secundario"
                onClick={() => setConfirmandoSaida(false)}
              >
                Cancelar
              </button>
            </span>
          )}
        </div>
      )}

      {resultado && <Resultado r={resultado} />}

      <form onSubmit={enviar}>
        <fieldset>
          <legend>{e && e.tipo !== "nenhuma" ? "Trocar a conexão" : "Conectar"}</legend>
          <label className="opcao">
            <input
              type="radio"
              name="forma"
              checked={forma === "assinatura"}
              onChange={() => setForma("assinatura")}
            />
            Assinatura Claude (Pro ou Max) — recomendado
          </label>
          <label className="opcao">
            <input
              type="radio"
              name="forma"
              checked={forma === "chave"}
              onChange={() => setForma("chave")}
            />
            Chave de acesso da conta de desenvolvedor Claude — alternativa, cobrada por uso
          </label>
        </fieldset>

        {forma === "assinatura" && e && !e.programa_instalado && (
          <div className="passo">
            <p>
              Para usar a assinatura, o app precisa instalar o programa oficial do Claude
              (gratuito).
            </p>
            <button type="button" onClick={() => instalar.mutate()} disabled={instalar.isPending}>
              {instalar.isPending ? "Instalando…" : "Instalar"}
            </button>
            {instalar.isError && <p className="alerta">{instalar.error.message}</p>}
          </div>
        )}

        {forma === "assinatura" && e?.programa_instalado && (
          <ol className="passos">
            <li>
              <button
                type="button"
                className="secundario"
                onClick={() => abrirLogin.mutate()}
                disabled={abrirLogin.isPending}
              >
                Abrir login
              </button>{" "}
              Uma janela vai abrir e o navegador vai pedir para você entrar na sua conta Claude.
              {abrirLogin.isError && <span className="alerta"> {abrirLogin.error.message}</span>}
            </li>
            <li>
              Ao terminar, a janela mostra um código que começa com <code>sk-ant-</code>. Copie e
              cole abaixo.
            </li>
          </ol>
        )}

        {(forma === "chave" || e?.programa_instalado) && (
          <label>
            {forma === "assinatura" ? "Código de acesso da assinatura" : "Chave de acesso"}
            <input
              type="password"
              autoComplete="off"
              spellCheck={false}
              value={codigo}
              onChange={(ev) => setCodigo(ev.target.value)}
            />
          </label>
        )}
        {(forma === "chave" || e?.programa_instalado) && (
          <button type="submit" disabled={!codigo.trim() || conectar.isPending}>
            {conectar.isPending ? "Conectando e testando…" : "Conectar"}
          </button>
        )}
        <p className="detalhe">A conexão só é guardada depois que o agente responde ao teste.</p>
      </form>
    </div>
  );
}
