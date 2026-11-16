import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useEffect } from 'react';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { simularApi, simularSemRede } from '../test/api-falsa';
import { Mapa } from './Mapa';

// O Leaflet não desenha em jsdom: o mapa é trocado por um componente que só avisa "a área mudou".
vi.mock('../components/MapaRelatos', () => ({
  MapaRelatos: ({
    onAreaMudou,
    subprefeituras,
  }: {
    onAreaMudou: (c: { lat: number; lon: number }, raio: number) => void;
    subprefeituras?: unknown[] | null;
  }) => {
    useEffect(() => onAreaMudou({ lat: -23.5505, lon: -46.6333 }, 800), [onAreaMudou]);
    return <div data-testid="mapa" data-subprefeituras={subprefeituras ? subprefeituras.length : 'nenhuma'} />;
  },
}));

const proximos = [
  { id: '0b6f6a3e-1c1d-4a52-8f0e-6a2d9c1e7b01', lat: -23.551, lon: -46.633, categoria: 'buraco', status: 'novo', prioridade: null, confirmacoes: 0 },
  { id: '7a2e5b90-4f13-4c68-b0d7-3c8a1e6f9d55', lat: -23.55, lon: -46.634, categoria: 'piso_danificado', status: 'encaminhado', prioridade: 'alta', confirmacoes: 4 },
  { id: 'e3a85c17-2d4b-4f90-8c61-9b0d6e7f1a44', lat: -23.552, lon: -46.631, categoria: null, status: 'novo', prioridade: null, confirmacoes: 1 },
];

function abrir() {
  return render(
    <MemoryRouter>
      <Mapa />
    </MemoryRouter>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe('Mapa', () => {
  it('lista os relatos por perto fora do mapa, com prioridade em texto e símbolo', async () => {
    const { chamadas } = simularApi([{ metodo: 'GET', caminho: '/relatos/proximos', corpo: proximos }]);
    abrir();

    expect(await screen.findByText(/3 problemas nesta região/)).toBeInTheDocument();
    expect(screen.getAllByRole('listitem').length).toBeGreaterThanOrEqual(3);
    expect(screen.getByText('Prioridade alta', { selector: '.selo' })).toBeInTheDocument();
    expect(screen.getAllByText('Ainda sem prioridade', { selector: '.selo' })).toHaveLength(2);
    expect(screen.getByText('Problema ainda sem classificação')).toBeInTheDocument();
    expect(screen.getByText('4 pessoas confirmaram')).toBeInTheDocument();

    expect(chamadas[0].url.searchParams.get('lat')).toBe('-23.5505');
    expect(chamadas[0].url.searchParams.get('raio_m')).toBe('800');
  });

  it('tem o botão "Reportar problema" sempre à mão', async () => {
    simularApi([{ metodo: 'GET', caminho: '/relatos/proximos', corpo: [] }]);
    abrir();
    const botao = screen.getByRole('link', { name: /Reportar problema/ });
    expect(botao).toHaveAttribute('href', '/reportar');
    expect(await screen.findByText('Nenhum problema registrado nesta região ainda.')).toBeInTheDocument();
  });

  it('se a API cair, avisa com calma e deixa tentar de novo', async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    simularSemRede();
    abrir();
    const mensagem = await screen.findByText(/o resto do app continua funcionando/i);
    expect(mensagem.closest('[role="alert"]')).not.toBeNull(); // anunciado por leitor de tela

    simularApi([{ metodo: 'GET', caminho: '/relatos/proximos', corpo: proximos }]);
    await userEvent.click(screen.getByRole('button', { name: 'Tentar de novo' }));
    expect(await screen.findByText(/3 problemas nesta região/)).toBeInTheDocument();
  });

  describe('camada de subprefeituras', () => {
    const linha = (subprefeitura: string, prioridade: string) => ({
      subprefeitura,
      prioridade,
      relatos_abertos: 3,
      relatos_por_categoria: { buraco: 1, piso_danificado: 1, obstaculo: 1, veiculo_na_calcada: 0 },
      tempo_medio_ate_reparo_dias: null,
      atualizado_em: '2026-11-09T10:00:00-03:00',
    });
    const painel = [linha('SE', 'alta'), linha('LAPA', 'baixa')];
    const semRelatos = { metodo: 'GET' as const, caminho: '/relatos/proximos', corpo: [] };
    const ligar = () => screen.getByRole('checkbox', { name: 'Mostrar prioridade por subprefeitura' });

    it('começa desligada e não pede o painel enquanto ninguém liga', async () => {
      const { chamadas } = simularApi([semRelatos, { metodo: 'GET', caminho: '/painel', corpo: painel }]);
      abrir();
      await screen.findByText('Nenhum problema registrado nesta região ainda.');
      expect(ligar()).not.toBeChecked();
      expect(screen.getByTestId('mapa')).toHaveAttribute('data-subprefeituras', 'nenhuma');
      expect(chamadas.some((c) => c.url.pathname.includes('/painel'))).toBe(false);
    });

    it('ao ligar, busca o painel uma vez, entrega ao mapa e mostra a legenda com texto', async () => {
      const { chamadas } = simularApi([semRelatos, { metodo: 'GET', caminho: '/painel', corpo: painel }]);
      abrir();
      await userEvent.click(ligar());

      expect(await screen.findByRole('list', { name: 'Como ler as subprefeituras do mapa' })).toBeInTheDocument();
      expect(screen.getByText(/mais prioritárias/)).toBeInTheDocument();
      expect(screen.getByText(/sem dados no painel/)).toBeInTheDocument();
      expect(screen.getByText(/GeoSampa/)).toBeInTheDocument();
      expect(screen.getByRole('link', { name: 'painel' })).toHaveAttribute('href', '/painel');
      expect(screen.getByTestId('mapa')).toHaveAttribute('data-subprefeituras', '2');

      // Desligar tira a camada; ligar de novo reaproveita o painel já carregado.
      await userEvent.click(ligar());
      expect(screen.getByTestId('mapa')).toHaveAttribute('data-subprefeituras', 'nenhuma');
      await userEvent.click(ligar());
      expect(screen.getByTestId('mapa')).toHaveAttribute('data-subprefeituras', '2');
      expect(chamadas.filter((c) => c.url.pathname.includes('/painel'))).toHaveLength(1);
    });

    it('sem dados no painel (404), avisa com calma e o mapa segue sem a camada', async () => {
      simularApi([
        semRelatos,
        { metodo: 'GET', caminho: '/painel', status: 404, corpo: { codigo: 'painel_indisponivel', mensagem: 'sem arquivo' } },
      ]);
      abrir();
      await userEvent.click(ligar());
      expect(await screen.findByText(/painel de prioridades ainda não tem dados/)).toBeInTheDocument();
      expect(screen.getByTestId('mapa')).toHaveAttribute('data-subprefeituras', 'nenhuma');
    });

    it('se o painel falhar, avisa (role=alert) e deixa tentar de novo', async () => {
      vi.spyOn(console, 'warn').mockImplementation(() => {});
      simularApi([
        semRelatos,
        { metodo: 'GET', caminho: '/painel', status: 503, corpo: { codigo: 'painel_invalido', mensagem: 'arquivo inválido' } },
      ]);
      abrir();
      await userEvent.click(ligar());
      const aviso = await screen.findByText(/Não consegui carregar as subprefeituras agora/);
      expect(aviso.closest('[role="alert"]')).not.toBeNull();

      simularApi([semRelatos, { metodo: 'GET', caminho: '/painel', corpo: painel }]);
      await userEvent.click(screen.getByRole('button', { name: 'Tentar de novo' }));
      expect(await screen.findByRole('list', { name: 'Como ler as subprefeituras do mapa' })).toBeInTheDocument();
    });
  });
});
