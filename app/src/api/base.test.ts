import { describe, expect, it } from 'vitest';
import { NAO_E_PAGINA_DO_APP, ehRotaPublicaDaApi, resolverBase } from './base';

const ORIGEM = 'https://passoseguro.exemplo.invalid';
const u = (caminho: string, origem = ORIGEM) => new URL(caminho, origem);

describe('resolverBase', () => {
  it('resolve um caminho relativo contra a origem do app', () => {
    expect(resolverBase('/api', ORIGEM).href).toBe(`${ORIGEM}/api`);
  });

  it('mantém uma base absoluta como está', () => {
    expect(resolverBase('http://localhost:4010', ORIGEM).origin).toBe('http://localhost:4010');
  });
});

describe('ehRotaPublicaDaApi', () => {
  it('com base relativa /api, reconhece os dados públicos sob /api', () => {
    expect(ehRotaPublicaDaApi(u('/api/painel'), '/api', ORIGEM)).toBe(true);
    expect(ehRotaPublicaDaApi(u('/api/relatos/proximos?lat=-23.5&lon=-46.6&raio_m=500'), '/api', ORIGEM)).toBe(true);
  });

  it('com base relativa, não confunde com o mesmo caminho sem o prefixo', () => {
    expect(ehRotaPublicaDaApi(u('/painel'), '/api', ORIGEM)).toBe(false);
    expect(ehRotaPublicaDaApi(u('/relatos/proximos'), '/api', ORIGEM)).toBe(false);
  });

  it('não guarda dados pessoais nem outros caminhos da API', () => {
    expect(ehRotaPublicaDaApi(u('/api/meus-relatos'), '/api', ORIGEM)).toBe(false);
    expect(ehRotaPublicaDaApi(u('/api/relatos'), '/api', ORIGEM)).toBe(false);
    expect(ehRotaPublicaDaApi(u('/api/painel/outro'), '/api', ORIGEM)).toBe(false);
  });

  it('aceita base relativa com barra no fim', () => {
    expect(ehRotaPublicaDaApi(u('/api/painel'), '/api/', ORIGEM)).toBe(true);
  });

  it('com base absoluta (mock em desenvolvimento), compara a origem', () => {
    const base = 'http://localhost:4010';
    expect(ehRotaPublicaDaApi(u('/painel', base), base, ORIGEM)).toBe(true);
    expect(ehRotaPublicaDaApi(u('/painel', 'http://outro.invalid'), base, ORIGEM)).toBe(false);
  });

  it('com base relativa, outra origem nunca é a API', () => {
    expect(ehRotaPublicaDaApi(u('/api/painel', 'https://outro.invalid'), '/api', ORIGEM)).toBe(false);
  });
});

describe('NAO_E_PAGINA_DO_APP', () => {
  const eServidor = (caminho: string) => NAO_E_PAGINA_DO_APP.some((re) => re.test(caminho));

  it('deixa /api e /metrics para o servidor', () => {
    expect(eServidor('/api/fotos/x.jpg')).toBe(true);
    expect(eServidor('/api')).toBe(true);
    expect(eServidor('/metrics/api')).toBe(true);
  });

  it('não pega páginas do app com nome parecido', () => {
    expect(eServidor('/apipa')).toBe(false);
    expect(eServidor('/meus-relatos')).toBe(false);
    expect(eServidor('/')).toBe(false);
  });
});
