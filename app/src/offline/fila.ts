// Fila offline de relatos (IndexedDB). Este módulo roda na página E no service worker
// (Background Sync), então não pode usar `window` nem `document`.
//
// Ciclo de um item:  aguardando → enviando → enviado (e é apagado)
//                    aguardando → aguardando (falha de rede/servidor: espera crescente)
//                    aguardando → falhou (o servidor recusou o relato: 4xx)
//
// Regra de não duplicar: o item só passa a "enviado" DEPOIS do 201. Duas execuções ao mesmo tempo
// (evento online + Background Sync + outra aba) são impedidas por trava (Web Locks, quando existe)
// e por uma execução única por contexto.
//
// Limite conhecido: se o servidor criar o relato mas a resposta se perder (queda no meio), a próxima
// tentativa cria outro. O contrato (rc2) não tem chave de idempotência; ver o PR.
import { openDB, type DBSchema, type IDBPDatabase } from 'idb';
import { ApiError, criarRelato } from '../api/cliente';
import { gerarUuid } from '../lib/uuid';

export type EstadoItem = 'aguardando' | 'enviando' | 'enviado' | 'falhou';

/**
 * A foto guardada como bytes + tipo, e não como Blob: é a forma mais portátil no IndexedDB
 * (o Safari/iOS já teve problemas guardando Blob).
 */
export interface FotoGuardada {
  dados: ArrayBuffer;
  tipo: string;
}

export function fotoComoBlob(foto: FotoGuardada): Blob {
  return new Blob([foto.dados], { type: foto.tipo });
}

export interface ItemFila {
  idLocal: string;
  /** A foto já comprimida. Some depois do envio. */
  foto: FotoGuardada | null;
  lat: number;
  lon: number;
  descricao: string;
  autorId: string;
  criadoEm: string;
  estado: EstadoItem;
  tentativas: number;
  /** Instante (ms desde 1970) a partir do qual pode tentar de novo. */
  proximaTentativaEm: number;
  ultimoErro?: string;
  relatoId?: string;
}

export interface NovoItem {
  foto: Blob;
  lat: number;
  lon: number;
  descricao: string;
  autorId: string;
}

interface Banco extends DBSchema {
  itens: { key: string; value: ItemFila; indexes: { estado: EstadoItem } };
}

const NOME_BANCO = 'passo-seguro-fila';
const NOME_TRAVA = 'passo-seguro-fila';
export const TAG_SYNC = 'enviar-fila';
export const MAX_TENTATIVAS = 12;
const ESPERA_BASE_MS = 5_000;
const ESPERA_MAXIMA_MS = 5 * 60_000;

let bancoAberto: Promise<IDBPDatabase<Banco>> | null = null;

function banco(): Promise<IDBPDatabase<Banco>> {
  bancoAberto ??= openDB<Banco>(NOME_BANCO, 1, {
    upgrade(db) {
      db.createObjectStore('itens', { keyPath: 'idLocal' }).createIndex('estado', 'estado');
    },
  });
  return bancoAberto;
}

/** Só para os testes: fecha a conexão para poder trocar o banco falso. */
export async function _fecharBancoParaTestes(): Promise<void> {
  if (bancoAberto) (await bancoAberto).close();
  bancoAberto = null;
}

/** Espera crescente: 5 s, 10 s, 20 s… até 5 min. */
export function esperaMs(tentativas: number): number {
  if (tentativas <= 0) return 0;
  return Math.min(ESPERA_BASE_MS * 2 ** (tentativas - 1), ESPERA_MAXIMA_MS);
}

// ---------- avisos de mudança (a tela atualiza sozinha) ----------

const CANAL = 'passo-seguro-fila';
export const EVENTO_MUDOU = 'fila:mudou';

export function notificarMudanca(): void {
  try {
    if (typeof BroadcastChannel !== 'undefined') {
      const canal = new BroadcastChannel(CANAL);
      canal.postMessage('mudou');
      canal.close();
    }
    globalThis.dispatchEvent?.(new Event(EVENTO_MUDOU));
  } catch {
    /* aviso é só conveniência */
  }
}

/** Escuta mudanças feitas aqui, em outra aba ou no service worker. */
export function aoMudar(chamar: () => void): () => void {
  const canal = typeof BroadcastChannel !== 'undefined' ? new BroadcastChannel(CANAL) : null;
  if (canal) canal.onmessage = chamar;
  globalThis.addEventListener?.(EVENTO_MUDOU, chamar);
  return () => {
    canal?.close();
    globalThis.removeEventListener?.(EVENTO_MUDOU, chamar);
  };
}

// ---------- operações ----------

export async function enfileirar(novo: NovoItem, agora = Date.now()): Promise<ItemFila> {
  const item: ItemFila = {
    ...novo,
    foto: { dados: await novo.foto.arrayBuffer(), tipo: novo.foto.type || 'image/jpeg' },
    idLocal: gerarUuid(),
    criadoEm: new Date(agora).toISOString(),
    estado: 'aguardando',
    tentativas: 0,
    proximaTentativaEm: 0,
  };
  await (await banco()).put('itens', item);
  notificarMudanca();
  await pedirSincronizacao();
  return item;
}

/** Itens que a pessoa precisa ver: ainda não enviados. Mais antigos primeiro. */
export async function listarPendentes(): Promise<ItemFila[]> {
  const todos = await (await banco()).getAll('itens');
  return todos.filter((i) => i.estado !== 'enviado').sort((a, b) => a.criadoEm.localeCompare(b.criadoEm));
}

export async function descartar(idLocal: string): Promise<void> {
  await (await banco()).delete('itens', idLocal);
  notificarMudanca();
}

/** "Tentar agora": zera a espera e as tentativas de um item e processa a fila. */
export async function tentarAgora(idLocal: string): Promise<Resultado> {
  const db = await banco();
  const item = await db.get('itens', idLocal);
  if (item && item.estado !== 'enviado') {
    await db.put('itens', { ...item, estado: 'aguardando', tentativas: 0, proximaTentativaEm: 0, ultimoErro: undefined });
    notificarMudanca();
  }
  return processarFila(Date.now, { ignorarEspera: true });
}

/** Pede ao navegador um Background Sync (Chromium). Nos outros, o evento `online` cobre. */
export async function pedirSincronizacao(): Promise<void> {
  try {
    const registro = (await navigator.serviceWorker?.ready) as
      | (ServiceWorkerRegistration & { sync?: { register(tag: string): Promise<void> } })
      | undefined;
    await registro?.sync?.register(TAG_SYNC);
  } catch {
    /* sem service worker ou sem suporte: ok */
  }
}

// ---------- envio ----------

export interface Resultado {
  enviados: number;
  /** Itens que continuam esperando (falha temporária ou ainda dentro do tempo de espera). */
  aguardando: number;
  falhos: number;
  /** A rede caiu durante a rodada: o Background Sync deve tentar de novo mais tarde. */
  semRede: boolean;
  /** Outra execução (outra aba ou o service worker) já estava processando. */
  ocupado: boolean;
}

const VAZIO: Resultado = { enviados: 0, aguardando: 0, falhos: 0, semRede: false, ocupado: false };

let emAndamento: Promise<Resultado> | null = null;

export interface OpcoesProcessar {
  /** A conexão acabou de voltar (evento online ou Background Sync): tenta já, sem esperar o tempo de espera. */
  ignorarEspera?: boolean;
}

/** Envia o que estiver pendente e vencido. Chamadas simultâneas compartilham a mesma execução. */
export function processarFila(agora: () => number = Date.now, opcoes: OpcoesProcessar = {}): Promise<Resultado> {
  emAndamento ??= comTrava(() => rodar(agora, opcoes)).finally(() => {
    emAndamento = null;
  });
  return emAndamento;
}

async function comTrava(trabalho: () => Promise<Resultado>): Promise<Resultado> {
  const travas = (globalThis as { navigator?: { locks?: LockManager } }).navigator?.locks;
  if (!travas) return trabalho();
  const resultado = await travas.request(
    NOME_TRAVA,
    { ifAvailable: true },
    async (trava: Lock | null) => (trava ? trabalho() : null),
  );
  return resultado ?? { ...VAZIO, ocupado: true };
}

function falhaTemporaria(e: unknown): boolean {
  if (!(e instanceof ApiError)) return true;
  return e.status === 0 || e.status === 408 || e.status === 429 || e.status >= 500;
}

async function rodar(agora: () => number, opcoes: OpcoesProcessar): Promise<Resultado> {
  const db = await banco();
  const resultado: Resultado = { ...VAZIO };

  // Com a trava na mão, "enviando" é sobra de uma execução interrompida: volta para a fila.
  for (const item of await db.getAll('itens')) {
    if (item.estado === 'enviado') await db.delete('itens', item.idLocal);
    else if (item.estado === 'enviando') await db.put('itens', { ...item, estado: 'aguardando' });
  }

  const pendentes = (await db.getAll('itens'))
    .filter((i) => i.estado === 'aguardando')
    .sort((a, b) => a.criadoEm.localeCompare(b.criadoEm));

  for (const item of pendentes) {
    if (!opcoes.ignorarEspera && item.proximaTentativaEm > agora()) {
      resultado.aguardando++;
      continue;
    }
    if (resultado.semRede) {
      resultado.aguardando++;
      continue;
    }
    if (!item.foto) {
      await db.put('itens', { ...item, estado: 'falhou', ultimoErro: 'A foto não está mais guardada.' });
      resultado.falhos++;
      continue;
    }

    await db.put('itens', { ...item, estado: 'enviando' });
    notificarMudanca();
    try {
      const criado = await criarRelato({
        foto: fotoComoBlob(item.foto),
        lat: item.lat,
        lon: item.lon,
        descricao: item.descricao,
        autorId: item.autorId,
      });
      // Só agora, com o 201 na mão, o item vale como enviado.
      await db.put('itens', { ...item, foto: null, estado: 'enviado', relatoId: criado.id });
      await db.delete('itens', item.idLocal);
      resultado.enviados++;
    } catch (e) {
      const tentativas = item.tentativas + 1;
      const mensagem = e instanceof Error ? e.message : 'Erro desconhecido';
      if (falhaTemporaria(e) && tentativas < MAX_TENTATIVAS) {
        await db.put('itens', {
          ...item,
          estado: 'aguardando',
          tentativas,
          proximaTentativaEm: agora() + esperaMs(tentativas),
          ultimoErro: mensagem,
        });
        resultado.aguardando++;
        if (e instanceof ApiError && e.semRede) resultado.semRede = true;
      } else {
        await db.put('itens', { ...item, estado: 'falhou', tentativas, ultimoErro: mensagem });
        resultado.falhos++;
      }
    }
    notificarMudanca();
  }
  return resultado;
}
