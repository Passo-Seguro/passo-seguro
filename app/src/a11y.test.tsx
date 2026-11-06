// Acessibilidade automática (jest-axe) nas telas principais. O jsdom não calcula cores, então o
// contraste (regra color-contrast) é conferido no Lighthouse; aqui valem rótulos, papéis ARIA,
// ordem de títulos, nomes de botões e links, idioma etc.
import { render } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { axe } from 'jest-axe';
import { useEffect } from 'react';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { App } from './App';
import { simularApi } from './test/api-falsa';

vi.mock('./components/MapaRelatos', () => ({
  MapaRelatos: ({ onAreaMudou }: { onAreaMudou: (c: { lat: number; lon: number }, raio: number) => void }) => {
    useEffect(() => onAreaMudou({ lat: -23.55, lon: -46.63 }, 800), [onAreaMudou]);
    return <div role="region" aria-label="Mapa dos problemas (teste)" />;
  },
}));
vi.mock('./components/SeletorLocal', () => ({
  SeletorLocal: () => <div role="region" aria-label="Mapa para marcar o local (teste)" />,
}));
vi.mock('./lib/localizacao', async (original) => ({
  ...(await original<typeof import('./lib/localizacao')>()),
  obterLocalizacao: vi.fn(() => new Promise(() => {})),
}));

const ID = '0b6f6a3e-1c1d-4a52-8f0e-6a2d9c1e7b01';
const foto = 'https://fotos.exemplo.invalid/a.jpg';

function api() {
  return simularApi([
    {
      metodo: 'GET',
      caminho: '/relatos/proximos',
      corpo: [
        { id: ID, lat: -23.551, lon: -46.633, categoria: 'buraco', status: 'novo', prioridade: null, confirmacoes: 0 },
        { id: 'e3a85c17-2d4b-4f90-8c61-9b0d6e7f1a44', lat: -23.55, lon: -46.634, categoria: 'piso_danificado', status: 'encaminhado', prioridade: 'alta', confirmacoes: 4 },
      ],
    },
    {
      metodo: 'GET',
      caminho: '/meus-relatos',
      corpo: [
        { id: ID, criado_em: '2026-11-04T14:32:10-03:00', categoria: 'buraco', status: 'novo', foto_url: foto },
        { id: 'e3a85c17-2d4b-4f90-8c61-9b0d6e7f1a44', criado_em: '2026-11-02T09:12:30-03:00', categoria: null, status: 'encaminhado', foto_url: foto },
        { id: '9c4d1f08-5e27-4a39-8b6e-0d2f7a3c1b66', criado_em: '2026-10-28T17:45:00-03:00', categoria: 'veiculo_na_calcada', status: 'resolvido', foto_url: foto },
      ],
    },
    {
      metodo: 'GET',
      caminho: '/painel',
      corpo: [
        { subprefeitura: 'Sé', prioridade: 'alta', relatos_abertos: 69, relatos_por_categoria: { buraco: 12, piso_danificado: 31, obstaculo: 9, veiculo_na_calcada: 17 }, tempo_medio_ate_reparo_dias: 41.5, atualizado_em: '2026-11-04T06:00:00-03:00' },
        { subprefeitura: 'Pinheiros', prioridade: 'media', relatos_abertos: 38, relatos_por_categoria: { buraco: 5, piso_danificado: 14, obstaculo: 11, veiculo_na_calcada: 8 }, tempo_medio_ate_reparo_dias: null, atualizado_em: '2026-11-04T06:00:00-03:00' },
      ],
    },
    {
      metodo: 'POST',
      caminho: '/assistente',
      corpo: {
        resposta: 'Em geral, o cuidado com o piso da calçada é de quem é dono do imóvel em frente.',
        fontes: [{ titulo: 'Cartilha (exemplo)', url: 'https://documentos.exemplo.invalid/cartilha.pdf' }],
        confianca: 0.86,
        recusou: false,
      },
    },
  ]);
}

async function auditar(rota: string, antes?: () => Promise<void>) {
  api();
  const { container, findByRole } = render(
    <MemoryRouter initialEntries={[rota]}>
      <App />
    </MemoryRouter>,
  );
  await findByRole('heading', { level: 1 });
  await antes?.();
  const resultado = await axe(container, { rules: { 'color-contrast': { enabled: false } } });
  expect(resultado.violations).toEqual([]);
}

afterEach(() => vi.unstubAllGlobals());

describe('acessibilidade (axe)', () => {
  it('o axe de fato acusa problemas (botão sem nome, imagem sem alt)', async () => {
    const { container } = render(
      <div>
        <button type="button" />
        {/* eslint-disable-next-line jsx-a11y/alt-text -- erro proposital: o teste confere que o axe o acusa */}
        <img src="x.png" />
      </div>,
    );
    const ids = (await axe(container)).violations.map((v) => v.id);
    expect(ids).toEqual(expect.arrayContaining(['button-name', 'image-alt']));
  });

  it('Mapa', () => auditar('/', async () => { await vi.waitFor(() => expect(document.querySelectorAll('.cartao').length).toBeGreaterThan(0)); }));
  it('Reportar: passo da foto', () => auditar('/reportar'));
  it('Meus relatos', () =>
    auditar('/meus-relatos', async () => {
      await vi.waitFor(() => expect(document.querySelectorAll('.cartao-relato').length).toBe(3));
    }));
  it('Pergunte', () => auditar('/pergunte'));
  it('Pergunte com uma resposta e fontes', () =>
    auditar('/pergunte', async () => {
      const user = userEvent.setup();
      await user.type(document.querySelector('input#pergunta')!, 'Quem conserta?');
      await user.click(document.querySelector('button[type="submit"]')!);
      await vi.waitFor(() => expect(document.querySelector('.fontes a')).not.toBeNull());
    }));
  it('Painel', () =>
    auditar('/painel', async () => {
      await vi.waitFor(() => expect(document.querySelectorAll('.cartao-painel').length).toBe(2));
    }));
  it('Privacidade', () => auditar('/privacidade'));
  it('Página não encontrada', () => auditar('/nao-existe'));
});
