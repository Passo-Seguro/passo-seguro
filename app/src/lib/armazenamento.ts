// localStorage pode lançar exceção (modo privativo, dados bloqueados). Aqui nunca lança:
// se falhar, o valor fica só na memória até a página fechar.
const memoria = new Map<string, string>();

export function lerLocal(chave: string): string | null {
  try {
    const valor = window.localStorage.getItem(chave);
    if (valor !== null) return valor;
  } catch {
    /* usa a memória */
  }
  return memoria.get(chave) ?? null;
}

export function gravarLocal(chave: string, valor: string): void {
  memoria.set(chave, valor);
  try {
    window.localStorage.setItem(chave, valor);
  } catch {
    /* fica só na memória */
  }
}
