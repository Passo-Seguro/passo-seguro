import { describe, expect, it } from 'vitest';
import { carregarPoligonos, estiloDaFaixa, indexarPorNome, OPACIDADE_FAIXA } from './subprefeituras';

// As 32 chaves que o `GET /painel` devolve (vw_prioridades, normalizadas: maiúsculas e sem acento).
const NOMES_DO_PAINEL = [
  'ARICANDUVA-FORMOSA-CARRAO', 'BUTANTA', 'CAMPO LIMPO', 'CAPELA DO SOCORRO', 'CASA VERDE-LIMAO-CACHOEIRINHA',
  'CIDADE ADEMAR', 'CIDADE TIRADENTES', 'ERMELINO MATARAZZO', 'FREGUESIA-BRASILANDIA', 'GUAIANASES', 'IPIRANGA',
  'ITAIM PAULISTA', 'ITAQUERA', 'JABAQUARA', 'JACANA-TREMEMBE', 'LAPA', 'M BOI MIRIM', 'MOOCA', 'PARELHEIROS',
  'PENHA', 'PERUS-ANHANGUERA', 'PINHEIROS', 'PIRITUBA-JARAGUA', 'SANTANA-TUCURUVI', 'SANTO AMARO', 'SAO MATEUS',
  'SAO MIGUEL', 'SAPOPEMBA', 'SE', 'VILA MARIA-VILA GUILHERME', 'VILA MARIANA', 'VILA PRUDENTE',
];

function pontos(g: { type: string; coordinates: unknown }): number[][][] {
  // Normaliza Polygon e MultiPolygon para uma lista de anéis.
  const poligonos = (g.type === 'Polygon' ? [g.coordinates] : g.coordinates) as number[][][][];
  return poligonos.flat();
}

describe('polígonos das subprefeituras', () => {
  it('são as 32 do painel, cada uma uma vez, com a mesma chave', async () => {
    const nomes = (await carregarPoligonos()).map((p) => p.properties.subprefeitura);
    expect(nomes).toHaveLength(32);
    expect(new Set(nomes).size).toBe(32);
    expect([...nomes].sort()).toEqual([...NOMES_DO_PAINEL].sort());
  });

  it('têm anéis fechados e ficam dentro do município de São Paulo', async () => {
    for (const p of await carregarPoligonos()) {
      for (const anel of pontos(p.geometry)) {
        expect(anel.length, p.properties.subprefeitura).toBeGreaterThanOrEqual(4);
        expect(anel[0], p.properties.subprefeitura).toEqual(anel.at(-1));
        for (const [lon, lat] of anel) {
          expect(lon).toBeGreaterThan(-46.9);
          expect(lon).toBeLessThan(-46.3);
          expect(lat).toBeGreaterThan(-24.1);
          expect(lat).toBeLessThan(-23.3);
        }
      }
    }
  });

  it('só carregam a chave do painel (nada de dado extra no arquivo)', async () => {
    for (const p of await carregarPoligonos()) expect(Object.keys(p.properties)).toEqual(['subprefeitura']);
  });
});

describe('estilo por faixa', () => {
  it('escurece conforme a prioridade e deixa só o contorno tracejado sem dados', () => {
    expect(OPACIDADE_FAIXA.alta).toBeGreaterThan(OPACIDADE_FAIXA.media);
    expect(OPACIDADE_FAIXA.media).toBeGreaterThan(OPACIDADE_FAIXA.baixa);
    expect(estiloDaFaixa('alta').fillOpacity).toBe(OPACIDADE_FAIXA.alta);
    expect(estiloDaFaixa('baixa').fillOpacity).toBe(OPACIDADE_FAIXA.baixa);
    const semDados = estiloDaFaixa(undefined);
    expect(semDados.fillOpacity).toBe(0);
    expect(semDados.dashArray).toBeDefined();
  });

  it('indexa o painel pelo nome da subprefeitura', () => {
    const mapa = indexarPorNome([
      { subprefeitura: 'SE', prioridade: 'alta', relatos_abertos: 1, relatos_por_categoria: { buraco: 0, piso_danificado: 0, obstaculo: 0, veiculo_na_calcada: 0 }, tempo_medio_ate_reparo_dias: null, atualizado_em: '2026-11-09T10:00:00-03:00' },
    ]);
    expect(mapa.get('SE')?.prioridade).toBe('alta');
    expect(mapa.get('LAPA')).toBeUndefined();
  });
});
