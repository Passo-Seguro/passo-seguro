import { useEffect, useRef, type ReactNode } from 'react';

interface Props {
  titulo: string;
  /** Título curto da aba/leitor de tela, se diferente do h1. */
  tituloDocumento?: string;
  className?: string;
  children: ReactNode;
}

/**
 * Cada tela tem um único h1. Ao trocar de tela (ou de etapa) o foco vai para ele e o título
 * da aba é atualizado: quem usa leitor de tela ou teclado percebe a mudança.
 */
export function Pagina({ titulo, tituloDocumento, className, children }: Props) {
  const h1 = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    document.title = `${tituloDocumento ?? titulo} · Passo Seguro`;
    h1.current?.focus({ preventScroll: true });
  }, [titulo, tituloDocumento]);

  return (
    <section className={className ? `pagina ${className}` : 'pagina'}>
      <h1 ref={h1} tabIndex={-1}>
        {titulo}
      </h1>
      {children}
    </section>
  );
}
