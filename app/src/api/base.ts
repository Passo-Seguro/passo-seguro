/**
 * Ajudante PURO sobre o endereço-base da API, separado de `cliente.ts` para o service worker e os
 * testes usarem sem criar o cliente HTTP.
 *
 * A base pode ser absoluta (`http://localhost:4010`, o mock em desenvolvimento) ou um caminho
 * relativo (`/api`, a imagem de produção: o nginx do app repassa para a API no mesmo domínio).
 */

/** Resolve a base contra a origem do app. `new URL('/api')` sozinho lança; com a origem funciona. */
export function resolverBase(base: string, origem: string): URL {
  return new URL(base, origem);
}

/** Caminhos GET que o service worker guarda em cache (dados PÚBLICOS; nada pessoal). */
export const CAMINHOS_PUBLICOS = ['/relatos/proximos', '/painel'] as const;

/** Diz se `url` é uma chamada GET a um dado público da API cuja base é `base`. */
export function ehRotaPublicaDaApi(url: URL, base: string, origem: string): boolean {
  const b = resolverBase(base, origem);
  const prefixo = b.pathname.replace(/\/+$/, '');
  return url.origin === b.origin && CAMINHOS_PUBLICOS.some((caminho) => url.pathname === `${prefixo}${caminho}`);
}

/** Caminhos que pertencem ao servidor e NUNCA devem cair no index.html do service worker. */
export const NAO_E_PAGINA_DO_APP: RegExp[] = [/^\/api(\/|$)/, /^\/metrics(\/|$)/];
