import type { ReactNode, SVGProps } from 'react';

// Ícones de traço (24x24), todos decorativos: o significado sempre vem junto em texto.
// `aria-hidden` e `focusable=false` evitam que leitor de tela e o IE/Edge antigo os anunciem.
function Base({ children, ...resto }: SVGProps<SVGSVGElement> & { children: ReactNode }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width="1.5em"
      height="1.5em"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      className="icone"
      {...resto}
    >
      {children}
    </svg>
  );
}

type P = SVGProps<SVGSVGElement>;

export const IconeMapa = (p: P) => (
  <Base {...p}>
    <path d="M9 4 3 6.5v13L9 17l6 3 6-2.5v-13L15 7 9 4Z" />
    <path d="M9 4v13M15 7v13" />
  </Base>
);

export const IconeRelatos = (p: P) => (
  <Base {...p}>
    <rect x="5" y="4" width="14" height="17" rx="2" />
    <path d="M9 4V3h6v1M9 11h6M9 15h4" />
  </Base>
);

export const IconeChat = (p: P) => (
  <Base {...p}>
    <path d="M4 5h16v11H11l-5 4v-4H4V5Z" />
    <path d="M8 9.5h8M8 12.5h5" />
  </Base>
);

export const IconePainel = (p: P) => (
  <Base {...p}>
    <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
  </Base>
);

export const IconeMais = (p: P) => (
  <Base strokeWidth="3" {...p}>
    <path d="M12 5v14M5 12h14" />
  </Base>
);

export const IconeCamera = (p: P) => (
  <Base {...p}>
    <path d="M4 8h3l1.5-2.5h7L17 8h3v11H4V8Z" />
    <circle cx="12" cy="13" r="3.5" />
  </Base>
);

export const IconeGaleria = (p: P) => (
  <Base {...p}>
    <rect x="3.5" y="4.5" width="17" height="15" rx="2" />
    <circle cx="9" cy="10" r="1.6" />
    <path d="m4 17 5-4.5 3.5 3 3-2.5 4.5 4" />
  </Base>
);

export const IconePino = (p: P) => (
  <Base {...p}>
    <path d="M12 21s-6.5-5.6-6.5-11a6.5 6.5 0 0 1 13 0c0 5.400-6.500 11-6.500 11Z" />
    <circle cx="12" cy="10" r="2.3" />
  </Base>
);

export const IconeMira = (p: P) => (
  <Base {...p}>
    <circle cx="12" cy="12" r="3" />
    <path d="M12 2v4M12 18v4M2 12h4M18 12h4" />
  </Base>
);

export const IconeRelogio = (p: P) => (
  <Base {...p}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M12 7.5V12l3 2" />
  </Base>
);

export const IconeCheck = (p: P) => (
  <Base strokeWidth="3" {...p}>
    <path d="m5 12.5 4.500 4.500L19 7.500" />
  </Base>
);

export const IconeSeta = (p: P) => (
  <Base strokeWidth="2.5" {...p}>
    <path d="M4 12h15m-6-6 6 6-6 6" />
  </Base>
);

export const IconeX = (p: P) => (
  <Base strokeWidth="3" {...p}>
    <path d="m6 6 12 12M18 6 6 18" />
  </Base>
);

export const IconeLupa = (p: P) => (
  <Base {...p}>
    <circle cx="11" cy="11" r="6.5" />
    <path d="m16 16 4.500 4.500" />
  </Base>
);

export const IconeEnvelope = (p: P) => (
  <Base {...p}>
    <rect x="3.500" y="5.500" width="17" height="13" rx="2" />
    <path d="m4 7 8 6 8-6" />
  </Base>
);

export const IconeLink = (p: P) => (
  <Base strokeWidth="2.5" {...p}>
    <path d="M14 4h6v6M20 4l-9 9M18 14v5H5V6h5" />
  </Base>
);

export const IconeEscudo = (p: P) => (
  <Base {...p}>
    <path d="M12 3 5 6v5.500c0 4.500 3 8 7 9.500 4-1.500 7-5 7-9.500V6l-7-3Z" />
    <path d="m9 12 2.200 2.200L15.500 10" />
  </Base>
);

/** Marca do Passo Seguro: pino de mapa com um visto, no azul do cabeçalho. */
export function Logo({ tamanho = 36 }: { tamanho?: number }) {
  return (
    <svg viewBox="0 0 48 48" width={tamanho} height={tamanho} aria-hidden="true" focusable="false">
      <rect width="48" height="48" rx="12" fill="#ffc93c" />
      <path d="M24 8c-6.900 0-12.500 5.400-12.500 12.200C11.500 29.800 24 41 24 41s12.500-11.200 12.500-20.800C36.500 13.400 30.900 8 24 8Z" fill="#0b2a3c" />
      <path d="m18.500 20.500 4 4 7.500-8" fill="none" stroke="#ffc93c" strokeWidth="3.600" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
