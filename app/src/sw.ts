/// <reference lib="webworker" />
// Service worker: cache do shell (funciona offline), mapa e API pública em cache, e Background Sync
// para esvaziar a fila de relatos mesmo com o app fechado.
import { clientsClaim } from 'workbox-core';
import { CacheableResponsePlugin } from 'workbox-cacheable-response';
import { ExpirationPlugin } from 'workbox-expiration';
import { cleanupOutdatedCaches, createHandlerBoundToURL, precacheAndRoute } from 'workbox-precaching';
import { NavigationRoute, registerRoute } from 'workbox-routing';
import { CacheFirst, NetworkFirst } from 'workbox-strategies';
import { API_URL } from './api/cliente';
import { TAG_SYNC, processarFila } from './offline/fila';

declare let self: ServiceWorkerGlobalScope;

// Atualiza sozinho: a versão nova assume assim que instala.
void self.skipWaiting();
clientsClaim();

// Shell do app (HTML, JS, CSS, ícones) gerado no build.
precacheAndRoute(self.__WB_MANIFEST);
cleanupOutdatedCaches();

// Qualquer página do app (ex.: /meus-relatos) abre offline com o index.html em cache.
registerRoute(new NavigationRoute(createHandlerBoundToURL('/index.html')));

// Mapa: ladrilhos do OpenStreetMap já vistos continuam disponíveis sem rede.
registerRoute(
  ({ url }) => url.hostname === 'tile.openstreetmap.org',
  new CacheFirst({
    cacheName: 'mapa-osm',
    plugins: [
      new CacheableResponsePlugin({ statuses: [0, 200] }),
      new ExpirationPlugin({ maxEntries: 300, maxAgeSeconds: 7 * 24 * 60 * 60 }),
    ],
  }),
);

// Só dados PÚBLICOS da API (mapa e painel). Nada pessoal (meus-relatos) fica em cache.
const origemDaApi = new URL(API_URL).origin;
registerRoute(
  ({ url, request }) =>
    request.method === 'GET' &&
    url.origin === origemDaApi &&
    (url.pathname === '/relatos/proximos' || url.pathname === '/painel'),
  new NetworkFirst({
    cacheName: 'api-publica',
    networkTimeoutSeconds: 4,
    plugins: [
      new CacheableResponsePlugin({ statuses: [200] }),
      new ExpirationPlugin({ maxEntries: 30, maxAgeSeconds: 24 * 60 * 60 }),
    ],
  }),
);

// Background Sync (Chromium): a conexão voltou, mesmo com o app fechado → envia a fila.
self.addEventListener('sync', (evento) => {
  const e = evento as ExtendableEvent & { tag: string };
  if (e.tag !== TAG_SYNC) return;
  e.waitUntil(
    processarFila(Date.now, { ignorarEspera: true }).then((r) => {
      // Falhar faz o navegador tentar de novo mais tarde.
      if (r.semRede || r.aguardando > 0) throw new Error('Ainda há relatos na fila');
    }),
  );
});
