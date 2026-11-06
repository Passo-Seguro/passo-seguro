/** Três marcas decorativas (o "Passo X de 3" já está no título, lido pelo leitor de tela). */
export function Passos({ atual }: { atual: 1 | 2 | 3 }) {
  return (
    <div className="passos" aria-hidden="true">
      {[1, 2, 3].map((n) => (
        <span key={n} className={n < atual ? 'passo passo-feito' : n === atual ? 'passo passo-atual' : 'passo'} />
      ))}
    </div>
  );
}
