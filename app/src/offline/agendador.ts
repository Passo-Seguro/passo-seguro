import { processarFila } from './fila';

const INTERVALO_MS = 15_000;

/**
 * Faz a fila andar na página: ao abrir, quando a conexão volta (`online`), quando a aba volta a ficar
 * visível e a cada 15 s (cobre a espera crescente e navegadores sem Background Sync).
 * Devolve a função que desliga tudo.
 */
export function iniciarAgendador(): () => void {
  const rodar = (ignorarEspera = false) => {
    if (navigator.onLine) void processarFila(Date.now, { ignorarEspera }).catch((e) => console.warn('Fila offline', e));
  };
  // Conexão que acaba de voltar: tenta já, sem esperar o tempo de espera crescente.
  const aoVoltarARede = () => rodar(true);
  const aoVoltarAVisivel = () => {
    if (document.visibilityState === 'visible') rodar();
  };

  rodar();
  window.addEventListener('online', aoVoltarARede);
  document.addEventListener('visibilitychange', aoVoltarAVisivel);
  const intervalo = window.setInterval(() => rodar(), INTERVALO_MS);

  return () => {
    window.removeEventListener('online', aoVoltarARede);
    document.removeEventListener('visibilitychange', aoVoltarAVisivel);
    window.clearInterval(intervalo);
  };
}
