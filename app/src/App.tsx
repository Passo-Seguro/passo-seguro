import { NavLink, Route, Routes } from 'react-router';
import { AvisoPrivacidade } from './components/AvisoPrivacidade';
import { Mapa } from './pages/Mapa';
import { MeusRelatos } from './pages/MeusRelatos';
import { Privacidade } from './pages/Privacidade';
import { Reportar } from './pages/Reportar';

function NaoEncontrada() {
  return (
    <section className="pagina">
      <h1>Página não encontrada</h1>
      <p>Esse endereço não existe no Passo Seguro.</p>
      <NavLink to="/" className="botao botao-primario">
        Voltar ao mapa
      </NavLink>
    </section>
  );
}

export function App() {
  return (
    <div className="app">
      <a href="#conteudo" className="pular-para-conteudo">
        Pular para o conteúdo
      </a>
      <header className="topo">
        <p className="marca">
          <span aria-hidden="true">📍</span> Passo Seguro
        </p>
      </header>

      <main id="conteudo">
        <AvisoPrivacidade />
        <Routes>
          <Route path="/" element={<Mapa />} />
          <Route path="/reportar" element={<Reportar />} />
          <Route path="/meus-relatos" element={<MeusRelatos />} />
          <Route path="/privacidade" element={<Privacidade />} />
          <Route path="*" element={<NaoEncontrada />} />
        </Routes>
      </main>

      <nav className="menu" aria-label="Principal">
        <NavLink to="/" end>
          <span aria-hidden="true">🗺</span> Mapa
        </NavLink>
        <NavLink to="/meus-relatos">
          <span aria-hidden="true">📋</span> Meus relatos
        </NavLink>
        <NavLink to="/privacidade">
          <span aria-hidden="true">🔒</span> Privacidade
        </NavLink>
      </nav>
    </div>
  );
}
