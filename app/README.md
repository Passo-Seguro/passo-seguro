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
(a API libera CORS pela variável `CORS_ORIGINS`).

| Comando | O que faz |
|---|---|
| `npm run dev` | servidor de desenvolvimento |
| `npm run build` | confere os tipos e gera `dist/` |
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

## Estrutura

```
src/
  api/        cliente tipado (openapi-fetch) e schema.d.ts gerado
  components/ mapa, seletor de local, selos, aviso de privacidade
  hooks/      busca de relatos por perto
  lib/        domínio (rótulos em português), id anônimo, compressão da foto, GPS
  pages/      Mapa, Reportar (etapas em pages/reportar/), Meus relatos, Privacidade
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
docker build -t passo-seguro-app --build-arg VITE_API_URL=https://api.exemplo.invalid app/
docker run --rm -p 8080:8080 passo-seguro-app     # http://localhost:8080
```

Build em duas etapas (Node → nginx sem privilégios, usuário 101, porta 8080). `VITE_API_URL` é só um
endereço público e entra no JavaScript no build; a imagem não tem segredo nenhum.
