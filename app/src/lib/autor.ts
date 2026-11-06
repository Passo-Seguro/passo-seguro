import { gravarLocal, lerLocal } from './armazenamento';

const CHAVE = 'passo-seguro.autor-id';
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

/**
 * UUID v4. `crypto.randomUUID()` só existe em contexto seguro (HTTPS ou localhost); em HTTP pela
 * rede local (teste no celular) cai no `getRandomValues`, que existe em qualquer contexto.
 */
export function gerarUuid(): string {
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID();
  const b = crypto.getRandomValues(new Uint8Array(16));
  b[6] = (b[6] & 0x0f) | 0x40;
  b[8] = (b[8] & 0x3f) | 0x80;
  const h = Array.from(b, (x) => x.toString(16).padStart(2, '0')).join('');
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

/** Id anônimo do aparelho: gerado na primeira abertura e guardado no aparelho. Não identifica a pessoa. */
export function obterAutorId(): string {
  const guardado = lerLocal(CHAVE);
  if (guardado && UUID.test(guardado)) return guardado;
  const novo = gerarUuid();
  gravarLocal(CHAVE, novo);
  return novo;
}
