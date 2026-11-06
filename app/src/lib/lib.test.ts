import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { CATEGORIAS, INFO_STATUS, infoPrioridade, rotuloCategoria } from './dominio';
import { ALVO_BYTES, dimensoesAlvo, melhorQualidade } from './imagem';
import { gerarUuid, obterAutorId } from './autor';

describe('classes do contrato', () => {
  it('CATEGORIAS tem os mesmos nomes, na mesma ordem, de contratos/classes.yaml', () => {
    const yaml = readFileSync(resolve(process.cwd(), '../contratos/classes.yaml'), 'utf8');
    const nomes = [...yaml.matchAll(/^\s+nome:\s*(\w+)\s*$/gm)].map((m) => m[1]);
    expect(CATEGORIAS).toEqual(nomes);
  });

  it('todas as classes têm rótulo em português', () => {
    expect(rotuloCategoria('buraco')).toBe('Buraco');
    expect(rotuloCategoria('veiculo_na_calcada')).toBe('Veículo na calçada');
    expect(rotuloCategoria(null)).toMatch(/sem classificação/);
  });
});

describe('status e prioridade', () => {
  it('novo, encaminhado e resolvido formam a linha do tempo 0, 1, 2', () => {
    expect(INFO_STATUS.novo.etapa).toBe(0);
    expect(INFO_STATUS.encaminhado.etapa).toBe(1);
    expect(INFO_STATUS.resolvido.etapa).toBe(2);
  });

  it('prioridade sempre tem rótulo e símbolo, até quando é nula', () => {
    for (const p of ['alta', 'media', 'baixa', null] as const) {
      const info = infoPrioridade(p);
      expect(info.rotulo).not.toBe('');
      expect(info.simbolo).not.toBe('');
    }
  });
});

describe('compressão da foto', () => {
  it('reduz o lado maior para 1280 px mantendo a proporção', () => {
    expect(dimensoesAlvo(4000, 3000)).toEqual({ largura: 1280, altura: 960 });
    expect(dimensoesAlvo(3000, 4000)).toEqual({ largura: 960, altura: 1280 });
  });

  it('não amplia fotos pequenas', () => {
    expect(dimensoesAlvo(800, 600)).toEqual({ largura: 800, altura: 600 });
  });

  it('escolhe a maior qualidade que cabe no alvo', async () => {
    // tamanho proporcional à qualidade: 500 KB em q=1 (cabe no alvo de 300 KB até q=0,6)
    const codificar = vi.fn(async (q: number) => new Blob([new Uint8Array(Math.round(q * 500 * 1024))]));
    const blob = await melhorQualidade(codificar, ALVO_BYTES);
    expect(blob).not.toBeNull();
    expect(blob!.size).toBeLessThanOrEqual(ALVO_BYTES);
    expect(blob!.size).toBeGreaterThan(ALVO_BYTES * 0.85); // aproveita o orçamento
  });

  it('devolve null se nem a qualidade mínima cabe', async () => {
    const codificar = async () => new Blob([new Uint8Array(ALVO_BYTES * 2)]);
    expect(await melhorQualidade(codificar)).toBeNull();
  });

  it('devolve já na primeira tentativa se a foto é pequena', async () => {
    const codificar = vi.fn(async () => new Blob([new Uint8Array(1024)]));
    await melhorQualidade(codificar);
    expect(codificar).toHaveBeenCalledTimes(1);
  });
});

describe('id anônimo', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('gera um UUID v4 e guarda no aparelho', () => {
    const id = obterAutorId();
    expect(id).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
    expect(obterAutorId()).toBe(id);
    expect(window.localStorage.getItem('passo-seguro.autor-id')).toBe(id);
  });

  it('funciona em HTTP (sem crypto.randomUUID), como no teste pela rede local', () => {
    const real = globalThis.crypto;
    vi.stubGlobal('crypto', { getRandomValues: (a: Uint8Array) => real.getRandomValues(a) });
    expect(gerarUuid()).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
  });

  it('troca um valor corrompido por um novo UUID', () => {
    window.localStorage.setItem('passo-seguro.autor-id', 'lixo');
    expect(obterAutorId()).not.toBe('lixo');
  });
});
