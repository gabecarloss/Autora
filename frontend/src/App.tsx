import { Navigate, Route, Routes } from "react-router-dom";
import { BarraLateral } from "./componentes/BarraLateral";
import { ConfiguracoesGlobais } from "./telas/ConfiguracoesGlobais";
import { EmConstrucao } from "./telas/EmConstrucao";
import { Perfis } from "./telas/Perfis";

export function App() {
  return (
    <div className="app">
      <BarraLateral />
      <main className="conteudo">
        <Routes>
          <Route path="/" element={<Navigate to="/perfis" replace />} />
          <Route path="/perfis" element={<Perfis />} />
          <Route
            path="/custo"
            element={
              <EmConstrucao
                titulo="Custo"
                descricao="Quanto o agente gastou por perfil, por dia, semana e mês, com projeção."
              />
            }
          />
          <Route
            path="/tecnico"
            element={
              <EmConstrucao
                titulo="Técnico"
                descricao="Estado de cada perfil, a tela Bastidores e a comparação entre perfis."
              />
            }
          />
          <Route path="/configuracoes" element={<ConfiguracoesGlobais />} />
          <Route path="*" element={<Navigate to="/perfis" replace />} />
        </Routes>
      </main>
    </div>
  );
}
