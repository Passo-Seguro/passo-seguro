import { vi } from 'vitest';

export interface Rota {
  metodo: 'GET' | 'POST' | 'PATCH';
  /** Trecho do caminho, por exemplo '/meus-relatos'. */
  caminho: string;
  status?: number;
  corpo: unknown;
}

export interface ChamadaRegistrada {
  metodo: string;
  url: URL;
  cabecalhos: Headers;
  corpoTexto: string;
}

/** Troca o `fetch` global por uma API falsa e guarda as chamadas feitas. */
export function simularApi(rotas: Rota[]) {
  const chamadas: ChamadaRegistrada[] = [];
  const falso = vi.fn(async (entrada: Request | string | URL) => {
    const requisicao = entrada instanceof Request ? entrada : new Request(String(entrada));
    const url = new URL(requisicao.url);
    let corpoTexto = '';
    try {
      corpoTexto = await requisicao.clone().text();
    } catch {
      /* corpo não textual */
    }
    chamadas.push({ metodo: requisicao.method, url, cabecalhos: requisicao.headers, corpoTexto });
    const rota = rotas.find((r) => r.metodo === requisicao.method && url.pathname.includes(r.caminho));
    if (!rota) return new Response(JSON.stringify({ codigo: 'nao_encontrado', mensagem: 'sem rota' }), { status: 404 });
    return new Response(JSON.stringify(rota.corpo), {
      status: rota.status ?? 200,
      headers: { 'Content-Type': 'application/json' },
    });
  });
  vi.stubGlobal('fetch', falso);
  return { chamadas, fetch: falso };
}

export function simularSemRede() {
  const falso = vi.fn(async () => {
    throw new TypeError('Failed to fetch');
  });
  vi.stubGlobal('fetch', falso);
  return falso;
}
