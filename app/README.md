# App (PWA) do Passo Seguro

React + TypeScript + Vite. Mapa com Leaflet e OpenStreetMap. Os tipos da API são gerados do
[`openapi.yaml`](../openapi.yaml), então o app não inventa campos fora do contrato.

## Como rodar

```bash
# 1. Mock da API (outro terminal, na raiz do repositório): http://localhost:4010
scripts/mock.sh

# 2. App
cd app
cp .env.example .env.local     # opcional; o padrão já aponta para o mock
npm ci
npm run dev                    # http://localhost:5173 (e o IP da sua rede, para o celular)
```

`VITE_API_URL` define a API (padrão: `http://localhost:4010`). Para a API real, use o endereço dela
(a API libera CORS pela variável `CORS_ORIGINS`). Na imagem Docker o valor é `/api` (caminho relativo,
mesmo domínio; veja a seção Docker).

| Comando | O que faz |
|---|---|
| `npm run dev` | servidor de desenvolvimento |
| `npm run build` | confere os tipos (app e service worker) e gera `dist/` com o PWA |
| `npm run preview` | serve o build de produção em http://localhost:4173 (o service worker só roda no build) |
| `npm run gen:icones` | regera os ícones do PWA a partir de `public/favicon.svg` |
| `npm test` | vitest + testing-library |
| `npm run lint` | ESLint (inclui regras de acessibilidade: jsx-a11y) |
| `npm run gen:api` | gera `src/api/schema.d.ts` a partir de `../openapi.yaml` |
| `npm run check:api` | falha se `schema.d.ts` estiver diferente do contrato |

Depois de mudar o `openapi.yaml`, rode `npm run gen:api` e commite o `schema.d.ts`.

## Testar no celular pela rede local

1. Celular e computador na mesma rede Wi-Fi. Abra `http://<IP-do-computador>:5173`.
2. Use no `.env.local` o IP do computador na API: `VITE_API_URL=http://<IP-do-computador>:4010`.

Limitação do navegador: em **HTTP** que não seja `localhost`, o GPS, o service worker e a instalação como
PWA ficam bloqueados. O app continua funcionando (o local é marcado tocando no mapa), mas para testar GPS
e instalação use HTTPS: um túnel (por exemplo `cloudflared tunnel --url http://localhost:5173`) ou, no
Android com depuração USB, `adb reverse tcp:5173 tcp:5173` e `adb reverse tcp:4010 tcp:4010` e abrir
`http://localhost:5173` no celular.

## PWA e offline

- **Instalável**: manifesto completo (nome, `theme_color`, `display: standalone`, ícones 192/512 e *maskable*, atalhos
  "Reportar problema" e "Meus relatos") e `apple-touch-icon` para iOS. Só funciona em HTTPS ou `localhost`.
- **Service worker** (`src/sw.ts`, Workbox `injectManifest`): cache do shell, então qualquer tela abre sem rede;
  ladrilhos do OSM já vistos (7 dias) e só os dados **públicos** da API (`/relatos/proximos`, `/painel`) ficam em cache.
  Nada pessoal (`/meus-relatos`) é guardado.
- **Fila offline** (`src/offline/fila.ts`, IndexedDB com `idb`): sem rede, o relato (foto comprimida, coordenadas,
  descrição e id anônimo) vai para a fila e aparece em "Meus relatos" como *Aguardando envio*. Reenvio automático:
  evento `online` (tenta já), ao voltar para a aba, a cada 15 s e Background Sync (Chromium, funciona até com o app
  fechado). Falhas de rede/5xx esperam 5 s, 10 s, 20 s… até 5 min; recusa do servidor (4xx) vira "Não foi possível
  enviar", com "Tentar agora" e "Descartar".
- **Sem duplicar**: o item só passa a "enviado" depois do 201; execuções simultâneas (online + sync + outra aba) são
  serializadas por Web Locks e por uma execução única por contexto. **Limite conhecido:** se o servidor criar o relato e a
  resposta se perder, a nova tentativa cria outro, pois o contrato rc2 não tem chave de idempotência
  (proposta: aceitar um `Idempotency-Key`/`id` gerado no aparelho em `POST /relatos`).
- A foto fica no IndexedDB como `ArrayBuffer` + tipo (mais portátil que `Blob` no Safari/iOS).

## Acessibilidade

jsx-a11y no lint, jest-axe nas telas (`src/a11y.test.tsx`) e Lighthouse. Resumo das decisões: `lang="pt-BR"`, link
"Pular para o conteúdo", foco movido para o `h1` a cada tela/etapa, foco visível (anel duplo), alvos de toque de pelo
menos 44 px, mapa com lista equivalente, erros e avisos em regiões `role="alert"`/`role="status"`, prioridade e status
sempre com símbolo + texto, `prefers-reduced-motion`.

## Estrutura

```
src/
  api/        cliente tipado (openapi-fetch) e schema.d.ts gerado
  components/ mapa, seletor de local, selos, aviso de privacidade
  hooks/      busca de relatos por perto, fila offline, estado da conexão
  offline/    fila em IndexedDB e agendador de reenvio
  sw.ts       service worker
  lib/        domínio (rótulos em português), id anônimo, compressão da foto, GPS
  pages/      Mapa, Reportar (etapas em pages/reportar/), Meus relatos, Pergunte, Painel, Privacidade
  test/       API falsa e setup dos testes
```

## Decisões que valem saber

- **Id anônimo**: `crypto.randomUUID()` guardado no aparelho (com alternativa quando o navegador só
  oferece `getRandomValues`, caso do HTTP em rede local). Vai como `autor_id` no relato e no cabeçalho
  `X-Autor-Id`. Nunca é mostrado na tela.
- **Foto**: reduzida no navegador para JPEG com lado maior de 1280 px e cerca de 300 KB (busca binária da
  qualidade; se não couber, reduz as dimensões). Respeita a rotação do EXIF.
- **Prioridade nunca só por cor**: marcadores e selos levam símbolo e texto (▲ Alta, ◆ Média, ● Baixa, ○ Nova).
- **A lista de relatos por perto existe fora do mapa**, para leitor de tela e teclado.
- **Rótulos das classes** (`src/lib/dominio.ts`) são `Record<Categoria, …>`: se o enum do contrato mudar, o
  build quebra. Um teste compara a lista com `contratos/classes.yaml`.

## Docker

```bash
docker build -t passo-seguro-app app/
docker run --rm -p 8080:8080 \
  -e API_UPSTREAM=http://host.docker.internal:8000 -e METRICS_TOKEN=token-ficticio \
  passo-seguro-app                                # http://localhost:8080
```

Build em duas etapas (Node → nginx sem privilégios, usuário 101, porta 8080). A imagem não tem segredo
nenhum e serve qualquer domínio: o app chama a API pelo **caminho relativo `/api`** (`VITE_API_URL=/api`,
o padrão do Dockerfile) e o nginx repassa para a API.

O nginx é um modelo ([`nginx.conf.template`](./nginx.conf.template)): na partida a imagem troca só duas
variáveis de **execução** e grava `conf.d/default.conf`.

| Variável | Para quê |
|---|---|
| `API_UPSTREAM` | Obrigatória. Endereço interno da API, sem barra no fim (em produção, `http://ca-passoseguro-api`). O contêiner não sobe sem ela. |
| `METRICS_TOKEN` | Segredo da raspagem. Vazia = `/metrics/api` responde sempre 401. Só aceita `A-Za-z0-9._~+/=-`. |

Rotas do nginx:

| Rota | Comportamento |
|---|---|
| `/api/*` | Proxy para `API_UPSTREAM` sem o prefixo `/api` (ex.: `/api/painel` → `/painel`). Corpo até 11 MB (a API aceita 10 MiB de foto). |
| `/api/metrics` | 404: as métricas nunca saem por `/api`. |
| `/metrics/api` | Só com `Authorization: Bearer <METRICS_TOKEN>`; sem ele, 401. Com ele, repassa para `/metrics` da API. |
| `/healthz` | 200 sem log, para as sondas. |
| resto | PWA (`index.html` para rotas do app), com os cabeçalhos de `seguranca.inc`. |

O log de acesso sai em JSON **sem query string** (as consultas por perto levam coordenadas), sem `Referer`.
O log de erro do nginx imprime a requisição inteira e não dá para filtrar, por isso fica no nível `crit`;
falhas de upstream (502/504) aparecem no log de acesso.
