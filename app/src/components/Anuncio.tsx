/**
 * Região de aviso/erro lida pelo leitor de tela assim que o texto muda.
 * Fica sempre na página (vazia quando não há mensagem): regiões que nascem já com texto
 * nem sempre são anunciadas.
 */
export function Anuncio({ mensagem, tipo = 'erro' }: { mensagem: string | null; tipo?: 'erro' | 'info' }) {
  return (
    <div role="alert" className={mensagem ? `anuncio anuncio-${tipo}` : 'anuncio-vazio'}>
      {mensagem}
    </div>
  );
}
