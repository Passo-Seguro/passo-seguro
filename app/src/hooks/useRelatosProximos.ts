import { useCallback, useEffect, useRef, useState } from 'react';
import { listarRelatosProximos } from '../api/cliente';
import type { RelatoProximo } from '../api/tipos';
import type { Ponto } from '../lib/localizacao';

interface Estado {
  itens: RelatoProximo[];
  carregando: boolean;
  erro: boolean;
}

const ESPERA_MS = 350;

/** Busca os relatos da área visível, esperando o mapa parar de mexer e cancelando buscas antigas. */
export function useRelatosProximos() {
  const [estado, setEstado] = useState<Estado>({ itens: [], carregando: true, erro: false });
  const ultimaConsulta = useRef<{ centro: Ponto; raioM: number } | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const controlador = useRef<AbortController>(undefined);

  const executar = useCallback(async (centro: Ponto, raioM: number) => {
    controlador.current?.abort();
    const atual = new AbortController();
    controlador.current = atual;
    setEstado((e) => ({ ...e, carregando: true, erro: false }));
    try {
      const itens = await listarRelatosProximos({ lat: centro.lat, lon: centro.lon, raioM }, atual.signal);
      setEstado({ itens, carregando: false, erro: false });
    } catch (e) {
      if (atual.signal.aborted) return;
      console.warn('Falha ao buscar relatos próximos', e);
      setEstado((anterior) => ({ ...anterior, carregando: false, erro: true }));
    }
  }, []);

  const buscar = useCallback(
    (centro: Ponto, raioM: number) => {
      ultimaConsulta.current = { centro, raioM };
      clearTimeout(timer.current);
      timer.current = setTimeout(() => void executar(centro, raioM), ESPERA_MS);
    },
    [executar],
  );

  const tentarDeNovo = useCallback(() => {
    const c = ultimaConsulta.current;
    if (c) void executar(c.centro, c.raioM);
  }, [executar]);

  useEffect(
    () => () => {
      clearTimeout(timer.current);
      controlador.current?.abort();
    },
    [],
  );

  return { ...estado, buscar, tentarDeNovo };
}
