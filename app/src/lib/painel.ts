import type { PrioridadeSubprefeitura } from '../api/tipos';

export const LEGENDA_FONTE =
  'Fonte: camada Ouro do pipeline Passo Seguro (vw_prioridades), com dados do SP156 e do Infosiga de jun a set/2026. Relatos do app são simulados nesta versão.';

/**
 * Do maior para o menor `indice_prioridade`. Quem não tem índice (pipeline sem os campos novos)
 * vai depois e mantém a ordem que a API mandou (a ordenação do JS é estável).
 */
export function ordenarPorIndice(linhas: PrioridadeSubprefeitura[]): PrioridadeSubprefeitura[] {
  return [...linhas].sort((a, b) => {
    const ia = a.indice_prioridade;
    const ib = b.indice_prioridade;
    if (ia == null && ib == null) return 0;
    if (ia == null) return 1;
    if (ib == null) return -1;
    return ib - ia;
  });
}
