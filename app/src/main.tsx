import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router';
import { registerSW } from 'virtual:pwa-register';
import { App } from './App';
import { iniciarAgendador } from './offline/agendador';
import './estilos.css';

// Service worker: cache do shell, funcionamento offline e Background Sync. Só em build de produção.
if (import.meta.env.PROD) registerSW({ immediate: true });

// Reenvia os relatos guardados quando a conexão voltar.
iniciarAgendador();

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
);
