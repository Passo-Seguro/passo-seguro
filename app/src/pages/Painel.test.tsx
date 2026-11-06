import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { simularApi, simularSemRede } from '../test/api-falsa';
import { Painel } from './Painel';

const painel = [
  {
    subprefeitura: 'Sé',
    prioridade: 'alta',
    relatos_abertos: 69,
    relatos_por_categoria: { buraco: 12, piso_danificado: 31, obstaculo: 9, veiculo_na_calcada: 17 },
    tempo_medio_ate_reparo_dias: 41.5,
    atualizado_em: '2026-11-04T06:00:00-03:00',
  },
  {
    subprefeitura: 'Pinheiros',
    prioridade: 'media',
    relatos_abertos: 38,
    relatos_por_categoria: { buraco: 5, piso_danificado: 14, obstaculo: 11, veiculo_na_calcada: 8 },
    tempo_medio_ate_reparo_dias: null,
    atualizado_em: '2026-11-04T06:00:00-03:00',
  },
];

function abrir() {
  return render(
    <MemoryRouter>
      <Painel />
    </MemoryRouter>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe('Painel', () => {
  it('mostra um cartão por subprefeitura, com prioridade em texto, números e tabela por categoria', async () => {
    simularApi([{ metodo: 'GET', caminho: '/painel', corpo: painel }]);
    abrir();

    const se = (await screen.findByRole('heading', { name: 'Sé' })).closest('li')!;
    expect(within(se).getByText('Prioridade alta')).toBeInTheDocument();
    expect(within(se).getByText('69')).toBeInTheDocument();
    expect(within(se).getByText('relatos abertos')).toBeInTheDocument();
    const tabela = within(se).getByRole('table');
    expect(within(tabela).getByRole('row', { name: /Piso danificado 31/ })).toBeInTheDocument();
    expect(within(tabela).getByRole('row', { name: /Veículo na calçada 17/ })).toBeInTheDocument();
    expect(within(se).getByText('41,5 dias')).toBeInTheDocument();

    const pinheiros = screen.getByRole('heading', { name: 'Pinheiros' }).closest('li')!;
    expect(within(pinheiros).getByText('Prioridade média')).toBeInTheDocument();
    expect(within(pinheiros).getByText('ainda sem reparos registrados')).toBeInTheDocument();
    expect(screen.getByText(/Dados atualizados em/)).toBeInTheDocument();
  });

  it('mantém a ordem da API (maior prioridade primeiro)', async () => {
    simularApi([{ metodo: 'GET', caminho: '/painel', corpo: painel }]);
    abrir();
    await screen.findByRole('heading', { name: 'Sé' });
    const nomes = screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent);
    expect(nomes).toEqual(['Sé', 'Pinheiros']);
  });

  it('404: mostra "Ainda não há dados no painel" em vez de erro', async () => {
    simularApi([{ metodo: 'GET', caminho: '/painel', status: 404, corpo: { codigo: 'painel_indisponivel', mensagem: 'x' } }]);
    abrir();
    expect(await screen.findByText('Ainda não há dados no painel')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('lista vazia também vira "Ainda não há dados no painel"', async () => {
    simularApi([{ metodo: 'GET', caminho: '/painel', corpo: [] }]);
    abrir();
    expect(await screen.findByText('Ainda não há dados no painel')).toBeInTheDocument();
  });

  it('503 ou queda da API: mensagem amigável e "tentar de novo"', async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    simularApi([{ metodo: 'GET', caminho: '/painel', status: 503, corpo: { codigo: 'painel_invalido', mensagem: 'x' } }]);
    abrir();
    const msg = await screen.findByText(/Não consegui carregar o painel agora/);
    expect(msg.closest('[role="alert"]')).not.toBeNull();

    simularApi([{ metodo: 'GET', caminho: '/painel', corpo: painel }]);
    await userEvent.click(screen.getByRole('button', { name: 'Tentar de novo' }));
    expect(await screen.findByRole('heading', { name: 'Sé' })).toBeInTheDocument();
  });

  it('sem rede: mesma mensagem amigável', async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    simularSemRede();
    abrir();
    expect(await screen.findByText(/Não consegui carregar o painel agora/)).toBeInTheDocument();
  });
});
