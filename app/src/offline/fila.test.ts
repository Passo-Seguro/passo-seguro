import { afterEach, describe, expect, it, vi } from 'vitest';
import { simularApi, simularSemRede } from '../test/api-falsa';
import { iniciarAgendador } from './agendador';
import {
  MAX_TENTATIVAS,
  descartar,
  enfileirar,
  esperaMs,
  listarPendentes,
  processarFila,
  tentarAgora,
  type NovoItem,
} from './fila';

const ID = '0b6f6a3e-1c1d-4a52-8f0e-6a2d9c1e7b01';
const AUTOR = '3f2b8c1e-7d4a-4e90-9b15-6a0c2d8e4f71';
const criado = { metodo: 'POST' as const, caminho: '/relatos', status: 201, corpo: { id: ID, categoria: 'buraco', confianca: 0.9, status: 'novo' } };

const relato = (extra: Partial<NovoItem> = {}): NovoItem => ({
  foto: new Blob([new Uint8Array(2048)], { type: 'image/jpeg' }),
  lat: -23.5505,
  lon: -46.6333,
  descricao: 'Buraco na frente do 120',
  autorId: AUTOR,
  ...extra,
});

afterEach(() => vi.unstubAllGlobals());

describe('fila offline', () => {
  it('guarda o relato com foto, coordenadas e descrição, como "aguardando"', async () => {
    await enfileirar(relato());
    const [item] = await listarPendentes();
    expect(item.estado).toBe('aguardando');
    expect(item.lat).toBe(-23.5505);
    expect(item.descricao).toBe('Buraco na frente do 120');
    expect(item.foto?.dados.byteLength).toBe(2048);
    expect(item.foto?.tipo).toBe('image/jpeg');
    expect(item.autorId).toBe(AUTOR);
  });

  it('envia e só depois do 201 tira o item da fila', async () => {
    const { chamadas } = simularApi([criado]);
    await enfileirar(relato());

    const r = await processarFila();

    expect(r).toMatchObject({ enviados: 1, aguardando: 0, falhos: 0, semRede: false });
    expect(chamadas.filter((c) => c.metodo === 'POST')).toHaveLength(1);
    expect(await listarPendentes()).toHaveLength(0);
  });

  it('durante o envio o item continua guardado (com a foto), marcado "enviando"', async () => {
    let liberar!: () => void;
    const segurar = new Promise<void>((ok) => (liberar = ok));
    let visto: Awaited<ReturnType<typeof listarPendentes>> = [];
    vi.stubGlobal('fetch', async () => {
      visto = await listarPendentes();
      await segurar;
      return new Response(JSON.stringify(criado.corpo), { status: 201, headers: { 'Content-Type': 'application/json' } });
    });
    await enfileirar(relato());

    const execucao = processarFila();
    await vi.waitFor(() => expect(visto).toHaveLength(1));
    expect(visto[0].estado).toBe('enviando');
    expect(visto[0].foto?.dados.byteLength).toBe(2048);
    liberar();
    await execucao;
    expect(await listarPendentes()).toHaveLength(0);
  });

  it('não duplica: execuções simultâneas (online + sync + outra aba) enviam uma vez só', async () => {
    const { chamadas } = simularApi([criado]);
    await enfileirar(relato());

    const [a, b, c] = await Promise.all([processarFila(), processarFila(), processarFila()]);

    expect(chamadas.filter((x) => x.metodo === 'POST')).toHaveLength(1);
    expect(a).toBe(b);
    expect(b).toBe(c);
  });

  it('não reenvia um relato já enviado ao processar de novo', async () => {
    const { chamadas } = simularApi([criado]);
    await enfileirar(relato());
    await processarFila();
    await processarFila();
    expect(chamadas.filter((x) => x.metodo === 'POST')).toHaveLength(1);
  });

  it('sem rede: continua na fila, conta a tentativa e espera de forma crescente', async () => {
    const t0 = 1_000_000;
    const falso = simularSemRede();
    await enfileirar(relato());

    const r1 = await processarFila(() => t0);
    expect(r1).toMatchObject({ enviados: 0, aguardando: 1, semRede: true });
    let [item] = await listarPendentes();
    expect(item.tentativas).toBe(1);
    expect(item.proximaTentativaEm).toBe(t0 + 5_000);

    // Antes da hora, nem tenta.
    await processarFila(() => t0 + 1_000);
    expect(falso).toHaveBeenCalledTimes(1);

    // Passada a espera, tenta de novo e a espera dobra.
    await processarFila(() => t0 + 6_000);
    expect(falso).toHaveBeenCalledTimes(2);
    [item] = await listarPendentes();
    expect(item.tentativas).toBe(2);
    expect(item.proximaTentativaEm).toBe(t0 + 6_000 + 10_000);
  });

  it('a espera cresce até 5 minutos', () => {
    expect([1, 2, 3, 4, 5, 6, 7, 8].map(esperaMs)).toEqual([5, 10, 20, 40, 80, 160, 300, 300].map((s) => s * 1000));
  });

  it('quando a conexão volta, o relato sobe', async () => {
    simularSemRede();
    await enfileirar(relato());
    await processarFila(() => 0);

    const { chamadas } = simularApi([criado]);
    const r = await processarFila(() => 60_000);

    expect(r.enviados).toBe(1);
    expect(chamadas.filter((c) => c.metodo === 'POST')).toHaveLength(1);
    expect(await listarPendentes()).toHaveLength(0);
  });

  it('erro 5xx também espera e tenta de novo', async () => {
    simularApi([{ metodo: 'POST', caminho: '/relatos', status: 503, corpo: { codigo: 'x', mensagem: 'fora' } }]);
    await enfileirar(relato());
    const r = await processarFila(() => 0);
    expect(r).toMatchObject({ aguardando: 1, falhos: 0 });
    expect((await listarPendentes())[0].estado).toBe('aguardando');
  });

  it('recusa definitiva do servidor (422) vira "falhou" e não fica tentando', async () => {
    const { chamadas } = simularApi([
      { metodo: 'POST', caminho: '/relatos', status: 422, corpo: { codigo: 'fora_da_area', mensagem: 'Fora de SP' } },
    ]);
    await enfileirar(relato());

    const r = await processarFila(() => 0);
    expect(r.falhos).toBe(1);
    const [item] = await listarPendentes();
    expect(item.estado).toBe('falhou');
    expect(item.ultimoErro).toBe('Fora de SP');

    await processarFila(() => 10 * 60_000);
    expect(chamadas.filter((c) => c.metodo === 'POST')).toHaveLength(1);
  });

  it('depois de muitas tentativas desiste e avisa', async () => {
    simularSemRede();
    await enfileirar(relato());
    let agora = 0;
    for (let i = 0; i < MAX_TENTATIVAS; i++) {
      await processarFila(() => agora);
      agora += 10 * 60_000;
    }
    expect((await listarPendentes())[0].estado).toBe('falhou');
  });

  it('um item "enviando" sobrado de uma execução interrompida volta para a fila e sobe uma vez', async () => {
    const { chamadas } = simularApi([criado]);
    const item = await enfileirar(relato());
    const { openDB } = await import('idb');
    const db = await openDB('passo-seguro-fila', 1);
    await db.put('itens', { ...item, estado: 'enviando' });
    db.close();

    const r = await processarFila();
    expect(r.enviados).toBe(1);
    expect(chamadas.filter((c) => c.metodo === 'POST')).toHaveLength(1);
  });

  it('"Tentar agora" ignora a espera', async () => {
    simularSemRede();
    const item = await enfileirar(relato());
    await processarFila(); // falha agora: próxima tentativa só daqui a 5 s
    expect((await listarPendentes())[0].proximaTentativaEm).toBeGreaterThan(Date.now());

    simularApi([criado]);
    const r = await tentarAgora(item.idLocal);
    expect(r.enviados).toBe(1);
  });

  it('descartar remove o item', async () => {
    const item = await enfileirar(relato());
    await descartar(item.idLocal);
    expect(await listarPendentes()).toHaveLength(0);
  });

  it('envia na ordem em que foram feitos e para na primeira falha de rede', async () => {
    const falso = simularSemRede();
    await enfileirar(relato({ descricao: 'primeiro' }), 1_000);
    await enfileirar(relato({ descricao: 'segundo' }), 2_000);
    const r = await processarFila(() => 0);
    expect(falso).toHaveBeenCalledTimes(1); // não insiste no segundo com a rede fora
    expect(r.aguardando).toBe(2);
  });
});

describe('agendador', () => {
  it('"online" ignora a espera crescente: a rede voltou, tenta já', async () => {
    simularSemRede();
    await enfileirar(relato());
    await processarFila(); // falha agora: próxima tentativa só daqui a 5 s
    const { chamadas } = simularApi([criado]);

    const parar = iniciarAgendador(); // ao abrir, respeita a espera
    await new Promise((r) => setTimeout(r, 50));
    expect(chamadas.filter((c) => c.metodo === 'POST')).toHaveLength(0);

    window.dispatchEvent(new Event('online'));
    try {
      await vi.waitFor(() => expect(chamadas.filter((c) => c.metodo === 'POST')).toHaveLength(1));
    } finally {
      parar();
    }
    expect(await listarPendentes()).toHaveLength(0);
  });

  it('quando o evento "online" dispara, processa a fila', async () => {
    const { chamadas } = simularApi([criado]);
    await enfileirar(relato());
    const parar = iniciarAgendador();
    try {
      await vi.waitFor(() => expect(chamadas.filter((c) => c.metodo === 'POST')).toHaveLength(1));
      // novo relato guardado enquanto estava sem rede; a conexão volta:
      await enfileirar(relato({ descricao: 'depois' }));
      window.dispatchEvent(new Event('online'));
      await vi.waitFor(() => expect(chamadas.filter((c) => c.metodo === 'POST')).toHaveLength(2));
    } finally {
      parar();
    }
  });
});
