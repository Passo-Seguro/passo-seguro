import 'fake-indexeddb/auto';
import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { IDBFactory } from 'fake-indexeddb';
import { afterEach, beforeEach } from 'vitest';
import { _fecharBancoParaTestes } from '../offline/fila';

// Cada teste começa com um IndexedDB vazio.
beforeEach(async () => {
  await _fecharBancoParaTestes();
  globalThis.indexedDB = new IDBFactory();
});

afterEach(() => {
  cleanup();
  window.localStorage.clear();
});
