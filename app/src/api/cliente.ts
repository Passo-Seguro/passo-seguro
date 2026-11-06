import createClient from 'openapi-fetch';
import type { paths } from './schema';
import type {
  Categoria,
  Erro,
  PrioridadeSubprefeitura,
  RelatoCriado,
  RelatoProximo,
  RelatoResumo,
  RespostaAssistente,
} from './tipos';

/** Endereço da API (variável de build VITE_API_URL; por padrão, o mock do Prism). */
export const API_URL: string = (import.meta.env.VITE_API_URL ?? 'http://localhost:4010').replace(/\/+$/, '');

// `fetch` é resolvido a cada chamada (e não na criação do cliente) para os testes poderem trocá-lo.
const cliente = createClient<paths>({
  baseUrl: API_URL,
  fetch: (requisicao) => globalThis.fetch(requisicao),
});

/** Falha de uma chamada à API. `status` 0 significa que nem chegou ao servidor (sem rede). */
export class ApiError extends Error {
  readonly status: number;
  readonly codigo: string;

  constructor(status: number, codigo: string, mensagem: string) {
    super(mensagem);
    this.name = 'ApiError';
    this.status = status;
    this.codigo = codigo;
  }

  get semRede(): boolean {
    return this.status === 0;
  }
}

function comoErroDaApi(resposta: Response, corpo: unknown): ApiError {
  const erro = (corpo ?? {}) as Partial<Erro>;
  return new ApiError(
    resposta.status,
    typeof erro.codigo === 'string' ? erro.codigo : `http_${resposta.status}`,
    typeof erro.mensagem === 'string' ? erro.mensagem : `Erro ${resposta.status}`,
  );
}

async function executar<T>(chamada: () => Promise<{ data?: T; error?: unknown; response: Response }>): Promise<T> {
  let resultado;
  try {
    resultado = await chamada();
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') throw e;
    throw new ApiError(0, 'sem_rede', 'Não foi possível falar com o servidor.');
  }
  if (resultado.error !== undefined || resultado.data === undefined) {
    throw comoErroDaApi(resultado.response, resultado.error);
  }
  return resultado.data;
}

export interface NovoRelatoApp {
  foto: Blob;
  lat: number;
  lon: number;
  descricao?: string;
  autorId: string;
}

/** POST /relatos (multipart). A foto já deve vir comprimida. */
export function criarRelato(novo: NovoRelatoApp, sinal?: AbortSignal): Promise<RelatoCriado> {
  const dados = new FormData();
  dados.append('foto', novo.foto, 'foto.jpg');
  dados.append('lat', String(novo.lat));
  dados.append('lon', String(novo.lon));
  dados.append('fonte', 'app');
  dados.append('autor_id', novo.autorId);
  const descricao = novo.descricao?.trim();
  if (descricao) dados.append('descricao', descricao);

  return executar(() =>
    cliente.POST('/relatos', {
      // O corpo real é o FormData acima; o objeto só satisfaz o tipo gerado (foto é "binary").
      body: { foto: '', lat: novo.lat, lon: novo.lon, fonte: 'app' },
      bodySerializer: () => dados,
      signal: sinal,
    }),
  );
}

/** PATCH /relatos/{id} no modo app: só a categoria, com o X-Autor-Id do autor. */
export function corrigirCategoria(id: string, categoria: Categoria, autorId: string): Promise<unknown> {
  return executar(() =>
    cliente.PATCH('/relatos/{id}', {
      params: { path: { id } },
      body: { categoria },
      headers: { 'X-Autor-Id': autorId },
    }),
  );
}

/** GET /relatos/proximos (mapa público; coordenadas já vêm arredondadas). */
export function listarRelatosProximos(
  consulta: { lat: number; lon: number; raioM: number },
  sinal?: AbortSignal,
): Promise<RelatoProximo[]> {
  return executar(() =>
    cliente.GET('/relatos/proximos', {
      params: { query: { lat: consulta.lat, lon: consulta.lon, raio_m: consulta.raioM } },
      signal: sinal,
    }),
  );
}

/** POST /assistente. Quando o assistente cai, a API ainda responde 200 com `recusou: true`. */
export function perguntarAoAssistente(pergunta: string, sinal?: AbortSignal): Promise<RespostaAssistente> {
  return executar(() => cliente.POST('/assistente', { body: { pergunta }, signal: sinal }));
}

/** GET /painel. Devolve `null` quando o pipeline ainda não exportou nada (404). */
export async function obterPainel(sinal?: AbortSignal): Promise<PrioridadeSubprefeitura[] | null> {
  try {
    return await executar(() => cliente.GET('/painel', { signal: sinal }));
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

/** GET /meus-relatos (X-Autor-Id no cabeçalho). */
export function listarMeusRelatos(autorId: string, sinal?: AbortSignal): Promise<RelatoResumo[]> {
  return executar(() =>
    cliente.GET('/meus-relatos', {
      params: { header: { 'X-Autor-Id': autorId } },
      signal: sinal,
    }),
  );
}
