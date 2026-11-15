import { useEffect, useState } from 'react';
import { obterPainel } from '../api/cliente';
import type { PrioridadeSubprefeitura } from '../api/tipos';

export type PainelDoMapa =
  | { fase: 'desligado' }
  | { fase: 'carregando' }
  | { fase: 'indisponivel' } // o pipeline ainda não exportou (404)
  | { fase: 'erro' }
  | { fase: 'ok'; linhas: PrioridadeSubprefeitura[] };

/**
 * Painel de prioridades para a camada de subprefeituras do mapa. Só busca quando a camada é
 * ligada, e guarda o resultado enquanto a tela está aberta (desligar e ligar de novo não rebusca).
 */
export function usePainelDoMapa(ligado: boolean) {
  const [linhas, setLinhas] = useState<PrioridadeSubprefeitura[] | null>(null);
  const [falha, setFalha] = useState<'indisponivel' | 'erro' | null>(null);
  const [tentativa, setTentativa] = useState(0);

  useEffect(() => {
    if (!ligado || linhas || falha) return;
    const controlador = new AbortController();
    obterPainel(controlador.signal)
      .then((recebidas) => {
        if (recebidas === null || recebidas.length === 0) setFalha('indisponivel');
        else setLinhas(recebidas);
      })
      .catch((e) => {
        if (controlador.signal.aborted) return;
        console.warn('Falha ao carregar o painel para o mapa', e);
        setFalha('erro');
      });
    return () => controlador.abort();
  }, [ligado, linhas, falha, tentativa]);

  // "carregando" não é guardado: é o que sobra quando está ligado e ainda não veio nada.
  const painel: PainelDoMapa = !ligado
    ? { fase: 'desligado' }
    : linhas
      ? { fase: 'ok', linhas }
      : falha
        ? { fase: falha }
        : { fase: 'carregando' };

  return {
    painel,
    tentarDeNovo: () => {
      setFalha(null);
      setTentativa((t) => t + 1);
    },
  };
}
