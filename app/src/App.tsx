import { Link, NavLink, Route, Routes } from 'react-router';
import { AvisoPrivacidade } from './components/AvisoPrivacidade';
import { useOnline } from './hooks/useOnline';
import { Mapa } from './pages/Mapa';
import { MeusRelatos } from './pages/MeusRelatos';
import { Painel } from './pages/Painel';
import { Pergunte } from './pages/Pergunte';
import { Privacidade } from './pages/Privacidade';
import { Reportar } from './pages/Reportar';

function NaoEncontrada() {
  return (
    <section className="pagina">
      <h1>Página não encontrada</h1>
      <p>Esse endereço não existe no Passo Seguro.</p>
      <Link to="/" className="botao botao-primario">
        Voltar ao mapa
      </Link>
    </section>
  );
}

export function App() {
  const online = useOnline();

  return (
    <div className="app">
      <a href="#conteudo" className="pular-para-conteudo">
        Pular para o conteúdo
      </a>
      <header className="topo">
        <p className="marca">
          <span aria-hidden="true">📍</span> Passo Seguro
        </p>
        <Link to="/privacidade" className="topo-link">
          Privacidade
        </Link>
      </header>

      <div role="status" className={online ? 'faixa-offline-vazia' : 'faixa-offline'}>
        {online ? '' : 'Você está sem internet. Os relatos que você fizer ficam guardados e são enviados quando a conexão voltar.'}
      </div>

      <main id="conteudo">
        <AvisoPrivacidade />
        <Routes>
          <Route path="/" element={<Mapa />} />
          <Route path="/reportar" element={<Reportar />} />
          <Route path="/meus-relatos" element={<MeusRelatos />} />
          <Route path="/pergunte" element={<Pergunte />} />
          <Route path="/painel" element={<Painel />} />
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
        <NavLink to="/pergunte">
          <span aria-hidden="true">💬</span> Pergunte
        </NavLink>
        <NavLink to="/painel">
          <span aria-hidden="true">📊</span> Painel
        </NavLink>
      </nav>
    </div>
  );
}
