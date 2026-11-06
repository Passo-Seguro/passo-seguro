import { useSyncExternalStore } from 'react';

function assinar(chamar: () => void) {
  window.addEventListener('online', chamar);
  window.addEventListener('offline', chamar);
  return () => {
    window.removeEventListener('online', chamar);
    window.removeEventListener('offline', chamar);
  };
}

/** `false` quando o aparelho está sem rede. */
export function useOnline(): boolean {
  return useSyncExternalStore(assinar, () => navigator.onLine, () => true);
}
