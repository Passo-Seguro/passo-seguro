import { Link } from 'react-router';

/** Sem rede: o relato ficou na fila do aparelho. */
export function EtapaGuardado({ onOutro }: { onOutro: () => void }) {
  return (
    <>
      <p className="selos">
        Situação do seu relato:{' '}
        <span className="selo selo-fila">
          <span aria-hidden="true">⏳</span> Aguardando envio
        </span>
      </p>
      <p>
        Você está sem internet, então guardamos a foto, o local e o texto <strong>neste aparelho</strong>. Quando a
        conexão voltar, enviamos sozinhos, sem você precisar fazer nada.
      </p>
      <p>Você pode ver os relatos que estão esperando em “Meus relatos”.</p>

      <div className="acoes">
        <Link to="/meus-relatos" className="botao botao-primario">
          Ver meus relatos
        </Link>
        <button type="button" className="botao botao-secundario" onClick={onOutro}>
          Reportar outro problema
        </button>
        <Link to="/" className="botao botao-secundario">
          Voltar ao mapa
        </Link>
      </div>
    </>
  );
}
