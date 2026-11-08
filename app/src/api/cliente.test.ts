import { afterEach, describe, expect, it, vi } from 'vitest';

// Com VITE_API_URL=/api (imagem de produção) o cliente deve chamar caminhos relativos ao domínio do
// app. No navegador `new Request('/api/painel')` resolve contra a página; o Node não, então o teste
// troca `Request` por uma versão que resolve contra a origem do app, como o navegador faria.
const ORIGEM = 'https://passoseguro.exemplo.invalid';

async function carregarClienteCom(urlDaApi: string) {
  vi.stubEnv('VITE_API_URL', urlDaApi);
  vi.resetModules();
  const RequestNativo = globalThis.Request;
  vi.stubGlobal(
    'Request',
    class RequestRelativo extends RequestNativo {
      constructor(entrada: RequestInfo | URL, init?: RequestInit) {
        super(typeof entrada === 'string' ? new URL(entrada, ORIGEM) : entrada, init);
      }
    },
  );
  const chamadas: URL[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (req: Request) => {
      chamadas.push(new URL(req.url));
      return new Response('[]', { status: 200, headers: { 'Content-Type': 'application/json' } });
    }),
  );
  const modulo = await import('./cliente');
  return { ...modulo, chamadas };
}

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.resetModules();
});

describe('cliente da API com base relativa', () => {
  it('API_URL guarda o caminho /api, sem barra no fim', async () => {
    const { API_URL } = await carregarClienteCom('/api/');
    expect(API_URL).toBe('/api');
  });

  it('GET /painel vira /api/painel no mesmo domínio', async () => {
    const { obterPainel, chamadas } = await carregarClienteCom('/api');
    await obterPainel();
    expect(chamadas).toHaveLength(1);
    expect(chamadas[0]?.href).toBe(`${ORIGEM}/api/painel`);
  });

  it('GET /relatos/proximos leva a consulta depois do prefixo /api', async () => {
    const { listarRelatosProximos, chamadas } = await carregarClienteCom('/api');
    await listarRelatosProximos({ lat: -23.55, lon: -46.63, raioM: 500 });
    const url = chamadas[0];
    expect(url?.pathname).toBe('/api/relatos/proximos');
    expect(url?.searchParams.get('lat')).toBe('-23.55');
    expect(url?.searchParams.get('lon')).toBe('-46.63');
    expect(url?.searchParams.get('raio_m')).toBe('500');
  });

  it('com base absoluta (mock), continua chamando o endereço completo', async () => {
    const { obterPainel, chamadas } = await carregarClienteCom('http://localhost:4010');
    await obterPainel();
    expect(chamadas[0]?.href).toBe('http://localhost:4010/painel');
  });
});
