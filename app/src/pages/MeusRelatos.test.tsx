import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { obterAutorId } from '../lib/autor';
import { simularApi, simularSemRede } from '../test/api-falsa';
import { MeusRelatos } from './MeusRelatos';

const base = { foto_url: 'https://fotos.exemplo.invalid/a.jpg', criado_em: '2026-11-04T14:32:10-03:00' };

function abrir() {
  return render(
    <MemoryRouter>
      <MeusRelatos />
    </MemoryRouter>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe('Meus relatos', () => {
  it('lista cada relato com o status em linguagem simples e envia o X-Autor-Id', async () => {
    const { chamadas } = simularApi([
      {
        metodo: 'GET',
        caminho: '/meus-relatos',
        corpo: [
          { id: '0b6f6a3e-1c1d-4a52-8f0e-6a2d9c1e7b01', categoria: 'buraco', status: 'novo', ...base },
          { id: 'e3a85c17-2d4b-4f90-8c61-9b0d6e7f1a44', categoria: null, status: 'encaminhado', ...base },
          { id: '9c4d1f08-5e27-4a39-8b6e-0d2f7a3c1b66', categoria: 'piso_danificado', status: 'resolvido', ...base },
        ],
      },
    ]);
    abrir();

    expect(await screen.findByRole('heading', { level: 2, name: 'Buraco' })).toBeInTheDocument();
    expect(screen.getByText('Problema ainda sem classificação')).toBeInTheDocument();
    expect(screen.getByText('Recebido', { selector: '.selo' })).toBeInTheDocument();
    expect(screen.getByText('Encaminhado', { selector: '.selo' })).toBeInTheDocument();
    expect(screen.getByText('Resolvido', { selector: '.selo' })).toBeInTheDocument();
    expect(screen.getByText(/já enviamos o caso para a subprefeitura/i)).toBeInTheDocument();
    expect(screen.getAllByRole('img', { name: 'Foto do relato' })).toHaveLength(3);

    expect(chamadas).toHaveLength(1);
    expect(chamadas[0].cabecalhos.get('x-autor-id')).toBe(obterAutorId());
  });

  it('indica a etapa atual da linha do tempo também em texto', async () => {
    simularApi([
      { metodo: 'GET', caminho: '/meus-relatos', corpo: [{ id: '0b6f6a3e-1c1d-4a52-8f0e-6a2d9c1e7b01', categoria: 'buraco', status: 'encaminhado', ...base }] },
    ]);
    abrir();
    expect(await screen.findByText('(etapa atual)')).toBeInTheDocument();
    expect(screen.getByText('(concluída)')).toBeInTheDocument();
    expect(screen.getByText('(ainda não chegou)')).toBeInTheDocument();
  });

  it('mostra um convite quando ainda não há relatos', async () => {
    simularApi([{ metodo: 'GET', caminho: '/meus-relatos', corpo: [] }]);
    abrir();
    expect(await screen.findByText(/ainda não fez nenhum relato/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Reportar um problema' })).toHaveAttribute('href', '/reportar');
  });

  it('mostra erro amigável e tenta de novo', async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    simularSemRede();
    abrir();
    const alerta = await screen.findByRole('alert');
    expect(alerta).toHaveTextContent(/não consegui carregar seus relatos/i);

    simularApi([{ metodo: 'GET', caminho: '/meus-relatos', corpo: [] }]);
    await userEvent.click(screen.getByRole('button', { name: 'Tentar de novo' }));
    expect(await screen.findByText(/ainda não fez nenhum relato/i)).toBeInTheDocument();
  });

  it('troca a foto por um aviso quando ela não carrega', async () => {
    simularApi([
      { metodo: 'GET', caminho: '/meus-relatos', corpo: [{ id: '0b6f6a3e-1c1d-4a52-8f0e-6a2d9c1e7b01', categoria: 'buraco', status: 'novo', ...base }] },
    ]);
    abrir();
    const foto = await screen.findByRole('img', { name: 'Foto do relato' });
    foto.dispatchEvent(new Event('error'));
    expect(await screen.findByRole('img', { name: 'Foto indisponível no momento' })).toBeInTheDocument();
  });
});
