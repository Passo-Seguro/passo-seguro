import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { simularApi, simularSemRede } from '../test/api-falsa';
import { LEGENDA_FONTE } from '../lib/painel';
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

const indicadores = (indice: number, atropelamentos: number, calcada: number) => ({
  reclamacoes_calcada_sp156: calcada,
  reclamacoes_guia_sarjeta_sp156: 10,
  atropelamentos_pedestres: atropelamentos,
  pedestres_mortos: 1,
  indice_prioridade: indice,
});

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

  it('sem os campos novos, a tela fica como antes: sem indicadores, mas com a legenda e a data', async () => {
    simularApi([{ metodo: 'GET', caminho: '/painel', corpo: painel }]);
    abrir();
    await screen.findByRole('heading', { name: 'Sé' });
    expect(screen.queryByText('Índice de prioridade')).not.toBeInTheDocument();
    expect(screen.queryByText('Atropelamentos de pedestres')).not.toBeInTheDocument();
    expect(screen.queryByText('Reclamações de calçada')).not.toBeInTheDocument();
    expect(screen.getByText(LEGENDA_FONTE)).toBeInTheDocument();
    expect(screen.getByText(/Dados atualizados em .*2026/)).toBeInTheDocument();
  });

  it('com os campos novos, mostra prioridade, índice, atropelamentos de pedestres e reclamações de calçada', async () => {
    simularApi([
      { metodo: 'GET', caminho: '/painel', corpo: [{ ...painel[0], ...indicadores(0.972, 1289, 2820) }, painel[1]] },
    ]);
    abrir();
    const se = (await screen.findByRole('heading', { name: 'Sé' })).closest('li')!;
    expect(within(se).getByText('Prioridade alta')).toBeInTheDocument();
    expect(within(se).getByText('Índice de prioridade').nextElementSibling).toHaveTextContent('0,972');
    expect(within(se).getByText('Atropelamentos de pedestres').nextElementSibling).toHaveTextContent('1.289');
    expect(within(se).getByText('Reclamações de calçada').nextElementSibling).toHaveTextContent('2.820');
    // Pinheiros não trouxe os campos novos: continua só com o que já tinha.
    const pinheiros = screen.getByRole('heading', { name: 'Pinheiros' }).closest('li')!;
    expect(within(pinheiros).queryByText('Índice de prioridade')).not.toBeInTheDocument();
  });

  it('mostra só os indicadores que vieram', async () => {
    simularApi([{ metodo: 'GET', caminho: '/painel', corpo: [{ ...painel[0], atropelamentos_pedestres: 0 }] }]);
    abrir();
    const se = (await screen.findByRole('heading', { name: 'Sé' })).closest('li')!;
    expect(within(se).getByText('Atropelamentos de pedestres').nextElementSibling).toHaveTextContent('0');
    expect(within(se).queryByText('Índice de prioridade')).not.toBeInTheDocument();
    expect(within(se).queryByText('Reclamações de calçada')).not.toBeInTheDocument();
  });

  it('ordena pelo índice, do maior para o menor, e deixa quem não tem índice no fim', async () => {
    const linha = (nome: string, extra: object) => ({ ...painel[1], subprefeitura: nome, ...extra });
    simularApi([
      {
        metodo: 'GET',
        caminho: '/painel',
        corpo: [
          linha('Sem índice', {}),
          linha('Meio', indicadores(0.5, 10, 10)),
          linha('Topo', indicadores(0.9, 10, 10)),
          linha('Piso', indicadores(0, 10, 10)),
        ],
      },
    ]);
    abrir();
    await screen.findByRole('heading', { name: 'Topo' });
    const nomes = screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent);
    expect(nomes).toEqual(['Topo', 'Meio', 'Piso', 'Sem índice']);
  });

  it('a legenda da fonte é fixa e diz que os relatos do app são simulados', async () => {
    simularApi([{ metodo: 'GET', caminho: '/painel', corpo: painel }]);
    abrir();
    await screen.findByRole('heading', { name: 'Sé' });
    expect(LEGENDA_FONTE).toBe(
      'Fonte: camada Ouro do pipeline Passo Seguro (vw_prioridades), com dados do SP156 e do Infosiga de jun a set/2026. Relatos do app são simulados nesta versão.',
    );
    expect(screen.getByText(LEGENDA_FONTE)).toBeInTheDocument();
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
