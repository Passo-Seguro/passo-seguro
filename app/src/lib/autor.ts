import { gravarLocal, lerLocal } from './armazenamento';
import { gerarUuid } from './uuid';

export { gerarUuid };

const CHAVE = 'passo-seguro.autor-id';
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

/** Id anônimo do aparelho: gerado na primeira abertura e guardado no aparelho. Não identifica a pessoa. */
export function obterAutorId(): string {
  const guardado = lerLocal(CHAVE);
  if (guardado && UUID.test(guardado)) return guardado;
  const novo = gerarUuid();
  gravarLocal(CHAVE, novo);
  return novo;
}
