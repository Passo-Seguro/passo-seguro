import type { Feature, FeatureCollection, MultiPolygon, Polygon } from 'geojson';
import type { Prioridade, PrioridadeSubprefeitura } from '../api/tipos';

/** Cada polígono carrega só a chave que o `GET /painel` usa (`subprefeitura`, em maiúsculas e sem acento). */
export type PoligonoSubprefeitura = Feature<Polygon | MultiPolygon, { subprefeitura: string }>;

/** Fonte dos limites, para a legenda do mapa. */
export const ATRIBUICAO_GEOSAMPA = 'Limites: GeoSampa / SMUL, Prefeitura de São Paulo';

/**
 * Os polígonos ficam num arquivo à parte (cerca de 200 KB): só baixa quem liga a camada.
 * Gerado por `npm run gen:geo` (ver `scripts/gerar-geojson-subprefeituras.mjs`).
 */
export async function carregarPoligonos(): Promise<PoligonoSubprefeitura[]> {
  const modulo = await import('../geo/subprefeituras.json');
  return (modulo.default as unknown as FeatureCollection<Polygon | MultiPolygon, { subprefeitura: string }>).features;
}

export function indexarPorNome(linhas: PrioridadeSubprefeitura[]): Map<string, PrioridadeSubprefeitura> {
  return new Map(linhas.map((l) => [l.subprefeitura, l]));
}

export interface EstiloFaixa {
  color: string;
  weight: number;
  opacity: number;
  fillColor: string;
  fillOpacity: number;
  dashArray?: string;
}

/**
 * Quanto mais prioritária, mais escuro o preenchimento. A cor sozinha nunca diz a prioridade:
 * o balão e a legenda trazem o texto. Tons de tinta (e não o vermelho/azul dos marcadores) para
 * o preenchimento não brigar com os pinos de relato que ficam por cima.
 */
const ESTILO_PADRAO: Omit<EstiloFaixa, 'fillOpacity'> = {
  color: '#0b2a3c',
  weight: 1.5,
  opacity: 0.85,
  fillColor: '#0b2a3c',
};

export const OPACIDADE_FAIXA: Record<Prioridade, number> = { alta: 0.5, media: 0.3, baixa: 0.12 };

/** Subprefeitura sem linha no painel: só o contorno tracejado, sem preenchimento. */
export function estiloDaFaixa(prioridade: Prioridade | null | undefined): EstiloFaixa {
  if (!prioridade) return { ...ESTILO_PADRAO, fillOpacity: 0, dashArray: '4 4' };
  return { ...ESTILO_PADRAO, fillOpacity: OPACIDADE_FAIXA[prioridade] };
}
