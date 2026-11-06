import { useEffect, useState } from 'react';
import { aoMudar, listarPendentes, type ItemFila } from '../offline/fila';

/** Relatos guardados no aparelho que ainda não subiram. Atualiza sozinho quando a fila muda. */
export function useFila() {
  const [itens, setItens] = useState<ItemFila[]>([]);
  const [pronto, setPronto] = useState(false);

  useEffect(() => {
    let ativo = true;
    const carregar = () =>
      listarPendentes()
        .then((lista) => ativo && setItens(lista))
        .catch((e) => console.warn('Não consegui ler a fila offline', e))
        .finally(() => ativo && setPronto(true));

    void carregar();
    const parar = aoMudar(() => void carregar());
    return () => {
      ativo = false;
      parar();
    };
  }, []);

  return { itens, pronto };
}
