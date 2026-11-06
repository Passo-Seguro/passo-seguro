import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { obterAutorId } from '../lib/autor';
import { simularApi, type Rota } from '../test/api-falsa';
import { Reportar } from './Reportar';

// O Leaflet não desenha em jsdom: o seletor de mapa é trocado por um botão que "toca no mapa".
vi.mock('../components/SeletorLocal', () => ({
  SeletorLocal: ({ onEscolher }: { onEscolher: (p: { lat: number; lon: number }) => void }) => (
    <button type="button" onClick={() => onEscolher({ lat: -23.5505, lon: -46.6333 })}>
      Tocar no mapa (teste)
    </button>
  ),
}));

vi.mock('../lib/imagem', async (original) => ({
  ...(await original<typeof import('../lib/imagem')>()),
  comprimirImagem: vi.fn(async () => ({ blob: new Blob([new Uint8Array(210 * 1024)], { type: 'image/jpeg' }), largura: 1280, altura: 960 })),
}));

const gps = vi.hoisted(() => ({ obterLocalizacao: vi.fn() }));
vi.mock('../lib/localizacao', async (original) => ({
  ...(await original<typeof import('../lib/localizacao')>()),
  obterLocalizacao: gps.obterLocalizacao,
}));

const ID = '0b6f6a3e-1c1d-4a52-8f0e-6a2d9c1e7b01';
const criado = (categoria: string | null): Rota => ({
  metodo: 'POST',
  caminho: '/relatos',
  status: 201,
  corpo: { id: ID, categoria, confianca: categoria ? 0.94 : null, status: 'novo' },
});
const patchOk: Rota = { metodo: 'PATCH', caminho: `/relatos/${ID}`, corpo: { id: ID, categoria: 'piso_danificado', status: 'novo' } };

async function ate(passo: 'detalhes') {
  const user = userEvent.setup();
  render(
    <MemoryRouter>
      <Reportar />
    </MemoryRouter>,
  );
  await user.upload(
    screen.getByLabelText('Escolher foto da galeria'),
    new File(['x'], 'rua.jpg', { type: 'image/jpeg' }),
  );
  expect(await screen.findByText('Foto pronta (210 KB)')).toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Continuar' }));
  await waitFor(() => expect(screen.getByRole('button', { name: 'Continuar' })).toBeEnabled());
  await user.click(screen.getByRole('button', { name: 'Continuar' }));
  expect(passo).toBe('detalhes');
  expect(await screen.findByRole('heading', { level: 1, name: /Passo 3 de 3/ })).toBeInTheDocument();
  return user;
}

beforeEach(() => {
  URL.createObjectURL = vi.fn(() => 'blob:foto-teste');
  URL.revokeObjectURL = vi.fn();
  gps.obterLocalizacao.mockResolvedValue({ lat: -23.5505, lon: -46.6333 });
});
afterEach(() => vi.unstubAllGlobals());

describe('Reportar problema', () => {
  it('foto → GPS → envio → "É um buraco?" → confirma → agradecimento com o status', async () => {
    const { chamadas } = simularApi([criado('buraco')]);
    const user = await ate('detalhes');
    await user.type(screen.getByLabelText(/Quer contar mais/), 'Buraco na frente do 120');
    await user.click(screen.getByRole('button', { name: 'Enviar relato' }));

    expect(await screen.findByRole('heading', { level: 1, name: 'É um buraco?' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Sim, é isso' }));

    expect(await screen.findByRole('heading', { level: 1, name: /Obrigado/ })).toBeInTheDocument();
    expect(screen.getByText('Recebido')).toBeInTheDocument();
    expect(chamadas.map((c) => c.metodo)).toEqual(['POST']); // confirmar não gera PATCH
    expect(chamadas[0].url.pathname).toBe('/relatos');
  });

  it('corrige a classe entre as 4 e manda PATCH com o X-Autor-Id', async () => {
    const { chamadas } = simularApi([criado('buraco'), patchOk]);
    const user = await ate('detalhes');
    await user.click(screen.getByRole('button', { name: 'Enviar relato' }));
    await screen.findByRole('heading', { level: 1, name: 'É um buraco?' });

    await user.click(screen.getByRole('button', { name: 'Não, é outro problema' }));
    expect(screen.getAllByRole('radio')).toHaveLength(4);
    expect(screen.getByRole('radio', { name: /Piso danificado/ })).toBeInTheDocument();
    await user.click(screen.getByRole('radio', { name: /Piso danificado/ }));
    await user.click(screen.getByRole('button', { name: 'Confirmar' }));

    expect(await screen.findByRole('heading', { level: 1, name: /Obrigado/ })).toBeInTheDocument();
    const patch = chamadas.find((c) => c.metodo === 'PATCH')!;
    expect(patch.url.pathname).toBe(`/relatos/${ID}`);
    expect(patch.cabecalhos.get('x-autor-id')).toBe(obterAutorId());
    expect(JSON.parse(patch.corpoTexto)).toEqual({ categoria: 'piso_danificado' });
  });

  it('categoria nula: pergunta "Não consegui identificar, qual é o problema?" com as 4 opções', async () => {
    simularApi([criado(null), patchOk]);
    const user = await ate('detalhes');
    await user.click(screen.getByRole('button', { name: 'Enviar relato' }));

    expect(await screen.findByRole('group', { name: 'Não consegui identificar, qual é o problema?' })).toBeInTheDocument();
    expect(screen.getAllByRole('radio').map((r) => (r as HTMLInputElement).value)).toEqual([
      'buraco',
      'piso_danificado',
      'obstaculo',
      'veiculo_na_calcada',
    ]);
    expect(screen.getByRole('button', { name: 'Confirmar' })).toBeDisabled();
  });

  it('GPS negado: avisa e deixa marcar no mapa', async () => {
    const { ErroLocalizacao } = await import('../lib/localizacao');
    gps.obterLocalizacao.mockRejectedValue(new ErroLocalizacao('negado'));
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <Reportar />
      </MemoryRouter>,
    );
    await user.upload(screen.getByLabelText('Escolher foto da galeria'), new File(['x'], 'a.jpg', { type: 'image/jpeg' }));
    await user.click(await screen.findByRole('button', { name: 'Continuar' }));

    expect(await screen.findByText(/Toque no mapa no lugar do problema/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Continuar' })).toBeDisabled();
    await user.click(screen.getByRole('button', { name: 'Tocar no mapa (teste)' }));
    expect(screen.getByRole('button', { name: 'Continuar' })).toBeEnabled();
  });

  it('422 fora_da_area: volta para o mapa com o aviso', async () => {
    simularApi([
      {
        metodo: 'POST',
        caminho: '/relatos',
        status: 422,
        corpo: { codigo: 'fora_da_area', mensagem: 'Os dados enviados não são válidos.' },
      },
    ]);
    const user = await ate('detalhes');
    await user.click(screen.getByRole('button', { name: 'Enviar relato' }));

    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent('Você está fora de São Paulo; toque no mapa dentro da cidade.'),
    );
    expect(screen.getByRole('heading', { level: 1, name: /Passo 2 de 3/ })).toBeInTheDocument();
  });

  it('falha ao salvar a correção: mostra aviso e não perde o relato', async () => {
    simularApi([criado('buraco'), { metodo: 'PATCH', caminho: `/relatos/${ID}`, status: 403, corpo: { codigo: 'proibido', mensagem: 'x' } }]);
    const user = await ate('detalhes');
    await user.click(screen.getByRole('button', { name: 'Enviar relato' }));
    await screen.findByRole('heading', { level: 1, name: 'É um buraco?' });
    await user.click(screen.getByRole('button', { name: 'Não, é outro problema' }));
    await user.click(screen.getByRole('radio', { name: /Obstáculo/ }));
    await user.click(screen.getByRole('button', { name: 'Confirmar' }));

    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent(/Não consegui salvar sua resposta/));
    expect(screen.getByRole('button', { name: 'Confirmar' })).toBeEnabled();
  });
});
